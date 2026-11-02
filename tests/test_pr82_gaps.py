"""Regressions for the fixes retained after comparing PR82 with newer dev."""

import json
import ssl
import sys
from types import SimpleNamespace

import httpx
import pytest
from test_eval import saved_run, screening
from test_precedents import SPLIT, ruling

from preflight.api import service
from preflight.check import precedents
from preflight.eval import baseline, check_recall, claim_recall, registry, run
from preflight.eval.split import Split
from preflight.models import Store, VoiceTranscribe
from preflight.schema import StageRun
from preflight.sources.rulings import meta


@pytest.mark.parametrize("raises", [False, True])
def test_private_model_scope_closes_asr_and_shared_sdk(tmp_path, monkeypatch, raises):
    closed = []
    http = httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("unexpected network")))
    sdk = SimpleNamespace(close=lambda: closed.append("sdk"))
    model = SimpleNamespace(api=sdk)
    monkeypatch.setattr(service, "from_env", lambda store: SimpleNamespace(
        spark=model, sam=model, image=model, glimmer=None, transcribe=SimpleNamespace(http=http),
    ))
    try:
        with service.private_models(tmp_path):
            if raises:
                raise RuntimeError("synthetic failure")
    except RuntimeError:
        assert raises
    assert http.is_closed and closed == ["sdk"]


def test_transcription_uses_system_trust_with_verification(tmp_path, monkeypatch):
    original, calls = ssl.create_default_context, []
    def context(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(ssl, "create_default_context", context)
    client = VoiceTranscribe(Store(tmp_path), "synthetic")
    with client.http:
        assert calls and calls[0] == {}


@pytest.fixture
def pinned_source(tmp_path, monkeypatch):
    entries = [meta(ruling("A26-000001", "Acme Ltd")), meta(ruling("G26-000002", "Borealis plc")),
               meta(ruling("A22-000007", "Other Ltd"))]
    monkeypatch.setattr(precedents, "load_split", lambda _: SPLIT)
    monkeypatch.setattr(precedents, "load_ruling_index", lambda _: entries)
    monkeypatch.setattr(precedents, "load_rulings", lambda: pytest.fail("broad raw scan"), raising=False)
    monkeypatch.setattr(precedents, "cache_path", lambda _: tmp_path / "eligible.html", raising=False)
    monkeypatch.setattr(precedents, "parse_ruling", lambda *args: ruling("A22-000007", "Other Ltd"), raising=False)
    (tmp_path / "eligible.html").write_text("synthetic eligible page")
    return tmp_path, entries


def test_precedents_read_only_eligible_snapshot_pages(pinned_source):
    assert [r.ruling_id for r in precedents.load_precedents("synthetic").rulings] == ["A22-000007"]


@pytest.mark.parametrize("case", ["missing", "identity", "advertiser", "date", "content", "duplicate"])
def test_pinned_source_cannot_silently_drift(pinned_source, monkeypatch, case):
    folder, entries = pinned_source
    if case == "missing":
        (folder / "eligible.html").unlink()
    elif case == "duplicate":
        entries.append(entries[-1])
    else:
        update = {"ruling_id": "A22-000008"} if case == "identity" else {
            "advertiser": "Different Ltd"} if case == "advertiser" else {
            "date": "2025-01-01"} if case == "date" else {"assessment": "Changed content"}
        changed = ruling("A22-000007", "Other Ltd").model_copy(update=update)
        monkeypatch.setattr(precedents, "parse_ruling", lambda *args: changed)
    with pytest.raises(ValueError):
        precedents.load_precedents("synthetic")


def test_multi_image_rescore_preserves_original_media_and_cohort(tmp_path, monkeypatch):
    _, work = saved_run(tmp_path, monkeypatch)
    registry.write_rows(tmp_path / "runs/screen-1.csv", [
        {"item_id": "A24-1", "media": 2}, {"item_id": "T16", "media": 1},
    ])
    (work / "screen-1/screen-1-A24-1-reconstruction-1.json").write_text(screening("extra", [], {}).model_dump_json())
    monkeypatch.setattr(run, "load_split", lambda _: SimpleNamespace(dev=["T16", "A24-1", "new-dev"]))
    run.rescore("screen-1")
    assert len(list((tmp_path / "runs").glob("screen-1-rescored-*.csv"))) == 1


def test_failed_saved_screening_cannot_be_rescored(tmp_path, monkeypatch):
    _, work = saved_run(tmp_path, monkeypatch)
    path = work / "screen-1/screen-1-T16-ad.json"
    saved = json.loads(path.read_text())
    saved["stages"] = [StageRun(stage="check", status="failed").model_dump(mode="json")]
    path.write_text(json.dumps(saved))
    monkeypatch.setattr(run, "load_ground_truth", lambda *args: pytest.fail("failed cache reached labels"))
    with pytest.raises(SystemExit, match="incomplete"):
        run.rescore("screen-1")


def test_unknown_selection_is_rejected_before_revision_or_inputs(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["screen", "--only", "unknown"])
    monkeypatch.setattr(run, "revision", lambda *args: pytest.fail("invalid selection reached revision"))
    with pytest.raises(SystemExit, match="outside"):
        run.main()


def test_untracked_sources_mark_dev_revision_dirty(monkeypatch):
    monkeypatch.setattr(registry, "git", lambda *args: "abc" if args[0] == "rev-parse" else (
        "" if "--untracked-files=no" in args else "?? new_prompt.txt"
    ))
    assert registry.revision("dev") == "abc-dirty"


@pytest.mark.parametrize("module", [run, baseline, check_recall, claim_recall])
@pytest.mark.parametrize("selection", [["--only", "unknown"], ["--only"]])
def test_cli_selection_guards_precede_inputs_and_clients(monkeypatch, module, selection):
    monkeypatch.setattr(sys, "argv", ["evaluation", *selection])
    monkeypatch.setattr(module, "load_split", lambda version: Split(
        version=version, created="2026-11-02", frozen=True, dev=["D1"], test=["held-out"],
    ))
    def unexpected(*args, **kwargs):
        pytest.fail("invalid selection reached inputs or clients")
    for name in ("load_ground_truth", "from_env", "revision"):
        if hasattr(module, name):
            monkeypatch.setattr(module, name, unexpected)
    with pytest.raises(SystemExit):
        module.main()
