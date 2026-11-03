import csv
import json
import os
import socket
import sys

import httpx
import pytest
from dotenv import load_dotenv
from openai import OpenAI
from test_eval import screening, truth

from preflight.eval import registry as registry_module
from preflight.eval import triage
from preflight.eval.registry import snapshot_text, write_rows
from preflight.eval.split import Split
from preflight.models import Glimmer, Store
from preflight.schema import StageRun
from preflight.triage import MODELS, Decision, Result, baseten_client, units


@pytest.fixture
def cohort(tmp_path, monkeypatch):
    source_id = "screen-synthetic"
    folder = tmp_path / "saved"
    folder.mkdir()
    saved = screening(f"{source_id}-D1-reconstruction-1", ["Treats anxiety fast", "Orange flavour"], {})
    (folder / f"{saved.screening_id}.json").write_text(saved.model_dump_json(), encoding="utf-8")
    registry = tmp_path / "runs.csv"
    common = {"run_id": source_id, "split": "v2", "part": "dev", "stage": "screen", "model": "synthetic",
              "prompt": "synthetic", "snapshots": snapshot_text(saved.snapshots), "git_sha": "synthetic", "effort": ""}
    write_rows(registry, [common | {"metric": "ad_recall", "total": 1}])
    write_rows(tmp_path / "runs" / f"{source_id}.csv", [{"item_id": "D1", "media": 1, "label": "positive"}])
    monkeypatch.setattr(triage, "RUNS", registry)
    monkeypatch.setattr(registry_module, "RUNS", registry)
    monkeypatch.setattr(triage, "revision", lambda part: "synthetic")
    monkeypatch.setattr(triage, "RESULTS", tmp_path)
    monkeypatch.setattr(triage, "load_split", lambda _: Split(
        version="v2", created="2026-11-02", frozen=True, dev=["D1", "new-dev"], test=["held-out"],
    ))
    def labels(version, item):
        assert item == "D1", "held-out labels must never be opened"
        return truth(item, [("Treats anxiety fast", ["15.6.2"])])
    monkeypatch.setattr(triage, "load_ground_truth", labels)
    monkeypatch.setattr(triage, "git", lambda *args: "synthetic" if args[0] == "rev-parse" else "")
    return source_id, folder, saved, registry


def test_registered_original_cohort_is_preserved_when_dev_grows(cohort):
    run_id, folder, saved, _ = cohort
    inputs = triage.load_inputs(run_id, folder)
    assert list(inputs.screenings) == ["D1"]
    assert inputs.screenings["D1"] == [saved]


@pytest.mark.parametrize("case", ["test", "void", "missing", "foreign", "media", "snapshot", "incomplete"])
def test_input_guards_fail_before_labels_and_clients(cohort, monkeypatch, case):
    run_id, folder, saved, registry = cohort
    if case == "test":
        registry.write_text(registry.read_text().replace(",dev,", ",test,"), encoding="utf-8")
    elif case == "void":
        (registry.parent / "void.csv").write_text(f"run_id,reason\n{run_id},leak\n")
    elif case == "missing":
        (folder / f"{saved.screening_id}.json").unlink()
    elif case == "foreign":
        (folder / f"{run_id}-held-out-ad.json").write_text("do not open held-out content")
    elif case == "media":
        write_rows(registry.parent / "runs" / f"{run_id}.csv", [{"item_id": "D1", "media": 2, "label": "positive"}])
    elif case == "snapshot":
        registry.write_text(registry.read_text().replace("2026-10-31", "2026-11-02"), encoding="utf-8")
    else:
        changed = saved.model_copy(update={"stages": (StageRun(stage="check", status="failed"),)})
        (folder / f"{saved.screening_id}.json").write_text(changed.model_dump_json())
    monkeypatch.setattr(triage, "load_ground_truth", lambda *args: pytest.fail("guard opened labels"))
    with pytest.raises(ValueError):
        triage.load_inputs(run_id, folder)


def test_false_skips_and_visual_text_coverage_are_distinct(cohort):
    _, _, saved, _ = cohort
    ad = units([saved])
    labels = truth("D1", [("Treats anxiety fast", ["15.6.2"]), ("An unseen visual claim", ["15.1"])])
    row, skips = triage.measure("D1", ad, Result(tuple(Decision(u.id, False) for u in ad), MODELS[0], {}), labels)
    assert (row["claim_units"], row["claim_units_kept"], row["claims_in_units"], row["claims_kept"]) == (1, 0, 1, 0)
    assert len(skips) == 1 and skips[0]["source_id"] == "text-0"
    assert row["skipped_chars"] == row["chars"] == sum(len(u.text) for u in ad)


def test_cli_workflow_records_and_replays_without_network(cohort, tmp_path, monkeypatch, capsys):
    run_id, folder, _, registry = cohort
    cache = tmp_path / "cache"
    calls = []
    def provider(request):
        payload = json.loads(request.content)
        calls.append(payload)
        prompt = payload["messages"][0]["content"][0]["text"]
        ad = json.loads(prompt.split("Ad units:\n")[1])
        answer = {"units": [{"id": u["id"], "needs_review": n == 0} for n, u in enumerate(ad)]}
        return httpx.Response(200, json={
            "id": "synthetic", "object": "chat.completion", "created": 0, "model": MODELS[0],
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": json.dumps(answer)}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        })
    inputs = triage.load_inputs(run_id, folder)
    with OpenAI(api_key="synthetic", http_client=httpx.Client(transport=httpx.MockTransport(provider))) as api:
        report, _ = triage.evaluate(inputs, Glimmer(Store(cache), MODELS[0], api), tmp_path / "recorded")
    assert len(calls) == 1 and report["claim_unit_recall"] == 1 and report["skip_share"] == 0.5
    assert report["units_skipped_per_ad"] == 1 and report["gates_screening"] is False
    assert 0 < report["skipped_char_share"] < 1 and report["triage_tokens_per_ad"] == 30
    assert report["matches_full_pipeline_recall"] is True
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("replay used network"))
    out = tmp_path / "replay"
    monkeypatch.setattr(sys, "argv", ["triage", run_id, "--screenings", str(folder), "--replay",
                                     "--cache", str(cache), "--out", str(out), "--model", MODELS[0]])
    triage.main()
    replayed = json.loads((out / "report.json").read_text())
    assert replayed["cache_mode"] == "replay" and replayed["totals"] == report["totals"]
    assert json.loads((out / "false-skips.json").read_text()) == []
    with registry.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["run_id"] for r in rows if r["stage"] == "screen"] == [run_id]
    added = {r["metric"]: r for r in rows if r["stage"] == "triage"}
    assert {r["run_id"] for r in added.values()} == {json.loads(capsys.readouterr().out)["run_id"]}
    assert (added["claim_units_kept"]["hits"], added["claim_units_kept"]["total"]) == ("1", "1")
    assert (added["units_skipped"]["hits"], added["triage_tokens"]["hits"]) == ("1", "30")
    assert added["claim_units_kept"]["split"] == "v2" and added["claim_units_kept"]["part"] == "dev"


def test_check_inputs_does_not_read_labels_or_credentials(cohort, monkeypatch):
    run_id, folder, _, _ = cohort
    monkeypatch.setattr(sys, "argv", ["triage", run_id, "--screenings", str(folder), "--check-inputs"])
    monkeypatch.setattr(triage, "load_dotenv", lambda: pytest.fail("credentials opened"))
    monkeypatch.setattr(triage, "load_ground_truth", lambda *args: pytest.fail("labels opened"))
    triage.main()


def test_label_drift_fails_before_paid_request_or_output(cohort, tmp_path, monkeypatch):
    run_id, folder, _, _ = cohort
    inputs = triage.load_inputs(run_id, folder)
    monkeypatch.setattr(triage, "load_ground_truth", lambda *args: truth("D1", []))
    monkeypatch.setattr(triage, "classify", lambda *args: pytest.fail("label drift reached provider"))
    out = tmp_path / "output"
    with pytest.raises(ValueError, match="label"):
        triage.evaluate(inputs, None, out)
    assert not out.exists()


def test_existing_experiment_is_never_overwritten(cohort, tmp_path, monkeypatch):
    run_id, folder, _, _ = cohort
    inputs = triage.load_inputs(run_id, folder)
    out = tmp_path / "output"
    out.mkdir()
    (out / "report.json").write_text("original experiment")
    monkeypatch.setattr(triage, "classify", lambda *args: pytest.fail("overwrite reached provider"))
    with pytest.raises(FileExistsError):
        triage.evaluate(inputs, None, out)
    assert (out / "report.json").read_text() == "original experiment"


@pytest.mark.live
def test_synthetic_live_triage_workflow(cohort, tmp_path):
    """Hosted classification through source loading, matching and saved report."""
    load_dotenv()
    key = os.environ.get("BASETEN_API_KEY")
    if not key:
        pytest.skip("BASETEN_API_KEY is not configured")
    run_id, folder, _, registry = cohort
    before = registry.read_bytes()
    inputs = triage.load_inputs(run_id, folder)
    with baseten_client(key) as api:
        report, _ = triage.evaluate(inputs, Glimmer(Store(tmp_path / "live-cache"), MODELS[0], api), tmp_path / "live")
    assert report["totals"]["claim_units_kept"] == report["totals"]["claim_units"] == 1
    assert report["totals"]["fallback"] == 0 and report["gates_screening"] is False
    assert registry.read_bytes() == before
    print(json.dumps({"kind": "synthetic_live_workflow", "model": report["models_returned"],
                      "dataset_measurement": False, "totals": report["totals"]}))
