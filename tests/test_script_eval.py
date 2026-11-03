from types import SimpleNamespace

import pytest

from preflight.eval import scripts
from preflight.eval.reconstruct import Scene, ShotList
from preflight.eval.registry import snapshot_text
from preflight.eval.split import GroundTruth
from preflight.eval.triage import Inputs
from preflight.pipeline import SNAPSHOTS


def test_copy_exports_only_ad_words_and_preserves_a_source_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(scripts, "ROOT", tmp_path)
    monkeypatch.setattr(scripts, "OUT_DIR", tmp_path)
    source = tmp_path / "A24-000001"
    source.mkdir()
    shots = ShotList(format="video", scenes=[Scene(duration_seconds=4, image_prompt="NEVER EXPORT THIS IMAGE PROMPT",
                                                  voiceover="Spoken copy", on_screen_text=["Caption copy"])])
    (source / "shotlist.json").write_text(shots.model_dump_json())
    raw, hashes = scripts.script_copy("A24-000001")
    assert raw == b"VO: Spoken copy\nSUPER: Caption copy\n"
    assert "NEVER EXPORT" not in raw.decode()
    assert len(next(iter(hashes.values()))) == 64


def test_invalid_baseline_is_rejected_before_copy_labels_or_clients(monkeypatch):
    def reject(*args):
        raise ValueError("invalid original cohort")
    monkeypatch.setattr(scripts, "load_inputs", reject)
    monkeypatch.setattr(scripts, "script_copy", lambda *args: pytest.fail("read copy before cohort guard"))
    monkeypatch.setattr(scripts, "load_ground_truth", lambda *args: pytest.fail("read labels before cohort guard"))
    with pytest.raises(ValueError, match="invalid original cohort"):
        scripts.prepare("held-out")


def test_missing_copy_does_not_open_labels_or_construct_models(monkeypatch):
    check_stage = SimpleNamespace(stage="check", samples=scripts.check.SAMPLES)
    baseline = Inputs({"prompt": f"{scripts.claims.PROMPT_VERSION}+{scripts.check.PROMPT_VERSION}+vote3",
                       "snapshots": snapshot_text(SNAPSHOTS)},
                      {"D1": [SimpleNamespace(stages=[check_stage], claims=[1])]}, {}, {"D1": "positive"})
    monkeypatch.setattr(scripts, "load_inputs", lambda *args: baseline)
    def missing(*args):
        raise FileNotFoundError("missing original shot list")
    monkeypatch.setattr(scripts, "script_copy", missing)
    monkeypatch.setattr(scripts, "load_ground_truth", lambda *args: pytest.fail("read labels without copy"))
    monkeypatch.setattr(scripts, "from_env", lambda: pytest.fail("constructed clients without copy"))
    with pytest.raises(FileNotFoundError):
        scripts.prepare("screen-synthetic")


@pytest.mark.parametrize(("answered", "has_claims"), [(2, True), (3, True), (None, False)])
def test_valid_voting_baseline_allows_abstention_and_empty_claims(monkeypatch, answered, has_claims):
    from test_eval import truth

    baseline = Inputs({"prompt": f"{scripts.claims.PROMPT_VERSION}+{scripts.check.PROMPT_VERSION}+vote3",
                       "snapshots": snapshot_text(SNAPSHOTS)},
                      {"T1": [SimpleNamespace(stages=[SimpleNamespace(stage="check", samples=answered)],
                                              claims=[1] if has_claims else [])]}, {}, {"T1": "positive"})
    monkeypatch.setattr(scripts, "load_inputs", lambda *args: baseline)
    monkeypatch.setattr(scripts, "script_copy", lambda _: (b"VO: Treats anxiety\n", {}))
    monkeypatch.setattr(scripts, "load_ground_truth", lambda *args: truth("T1", [("Treats anxiety", ["15.6.2"])]))
    assert set(scripts.prepare("screen-synthetic")[1]) == {"T1"}


def test_textual_denominator_excludes_a_visual_only_claim():
    truth = GroundTruth(item_id="T1", kind="team", label="positive", outcome=None, written_by="synthetic",
                        checked_by=None, claims=[{"claim": "Treats anxiety", "rules": ["15.6.2"], "points": [1]},
                                                 {"claim": "White coat implies medical endorsement", "rules": ["12.1"],
                                                  "points": [2]}])
    assert scripts.textual_mask(truth, b"VO: Treats anxiety\n") == [True, False]


@pytest.mark.parametrize("broken", [False, True])
def test_offline_comparison_registers_only_completed_runs(tmp_path, monkeypatch, broken):
    from test_eval import screening, truth
    from test_script import NoMedia, NoPrecedents, ScriptSpark

    from preflight.models import Models

    item = "T1"
    baseline = Inputs({"run_id": "screen-synthetic"}, {item: [screening("s", ["Treats anxiety"], {0: ["15.6.2"]})]},
                      {}, {item: "positive"})
    prepared = (baseline, {item: b"VO: Treats anxiety\n"}, {},
                {item: truth(item, [("Treats anxiety", ["15.6.2"])])})
    recorded = []
    monkeypatch.setattr(scripts, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(scripts, "register", lambda row, metrics: recorded.append((row, metrics)))
    monkeypatch.setattr(scripts, "revision", lambda _: "synthetic")
    monkeypatch.setattr(scripts, "load_precedents", lambda *args: NoPrecedents())
    models = Models(ScriptSpark(broken=broken), NoMedia(), NoMedia(), NoMedia(), None)
    out = tmp_path / "comparison"
    if broken:
        with pytest.raises(ValueError, match="incomplete checks"):
            scripts.evaluate(prepared, models, out)
        assert not recorded and not (tmp_path / "results").exists()
    else:
        run_id = scripts.evaluate(prepared, models, out)
        assert recorded[0][0]["stage"] == "script" and recorded[0][0]["part"] == "dev"
        assert (tmp_path / "results" / "runs" / f"{run_id}.csv").exists()
        found = {m.name: m for m in recorded[0][1]}
        assert (found["claim_recall_carried"].hits, found["claim_recall_carried"].total) == (1, 1)
        assert found["paired_claims_gained"].hits == found["paired_claims_lost"].hits == 0
    assert (out / "items.csv").exists() and (out / "provenance.json").exists()
