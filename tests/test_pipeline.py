import logging
from dataclasses import replace
from datetime import UTC, datetime
from html import escape

import pytest
from test_evidence import CLIP, ffmpeg, hand_built, models  # noqa: F401

from preflight import cli
from preflight.eval import claim_recall
from preflight.models import SparkResult
from preflight.pipeline import SNAPSHOTS, screen
from preflight.schema import NOTICE, Screening, StageRun, verify_sources

SECRET = "secret ad text"


class NoPrecedents:
    version = SNAPSHOTS.rulings

    def top(self, query, k=3):
        return []


class BrokenSam:
    def segment(self, *args, **kwargs):
        raise RuntimeError(SECRET)


class Router:
    # answers the calls whose schema holds the given property from `fake`, the rest from the recorded responses
    def __init__(self, real, fake, prop):
        self.real, self.fake, self.prop = real, fake, prop

    def ask(self, text, **kwargs):
        chosen = self.fake if self.prop in kwargs["schema"]["properties"] else self.real
        return chosen.ask(text, **kwargs)


class Judge:
    def __init__(self, skip):
        self.skip = skip

    def ask(self, text, **kwargs):
        ids = kwargs["schema"]["properties"]["verdicts"]["items"]["properties"]["claim_id"]["enum"]
        verdicts = [
            {"claim_id": i, "verdict": "no_issue", "cap_rules": [], "reason": "ok", "register_ids": [],
             "suggested_register_id": None}
            for i in (ids[:-1] if self.skip else ids)
        ]
        return SparkResult("muse-spark-1.3", "", {"verdicts": verdicts}, {})


class CitingFirst:
    def ask(self, text, **kwargs):
        ids = kwargs["schema"]["properties"]["claims"]["items"]["properties"]["evidence"]["items"]["enum"]
        claim = {"text": "Clinically proven formula", "kind": "explicit", "substance": None, "evidence": ids[:1]}
        return SparkResult("muse-spark-1.3", "", {"claims": [claim]}, {})


@pytest.fixture
def clip(tmp_path):
    done = hand_built(tmp_path, "video", 16)
    ffmpeg("-i", str(CLIP), "-fps_mode", "passthrough", str(tmp_path / "frames" / "%06d.png"))
    return done.model_copy(update={"audio": CLIP.parent / "speech.wav"})


def test_cli_screens_the_fixture_clip_end_to_end(tmp_path, monkeypatch, models, clip):  # noqa: F811
    monkeypatch.setattr(cli, "ingest", lambda path: clip)
    monkeypatch.setattr(cli, "from_env", lambda: models)
    monkeypatch.setattr(cli, "load_precedents", lambda version: NoPrecedents())
    assert cli.main(["screen", str(CLIP), "--out", str(tmp_path / "out"), "--no-align"]) == 0
    (saved,) = (tmp_path / "out").glob("*.json")
    screening = Screening.model_validate_json(saved.read_text(encoding="utf-8"))
    verify_sources(screening)
    assert [(r.stage, r.status) for r in screening.stages] == [
        (s, "done") for s in ("transcribe", "on_screen", "regions", "claims", "check")
    ]
    assert screening.claims
    assert f'"notice": "{NOTICE}"' in saved.read_text(encoding="utf-8")
    page = saved.with_suffix(".html").read_text(encoding="utf-8")
    assert screening.headline in page and NOTICE in page
    claims = {c.claim_id: c for c in screening.claims}
    for flag in screening.flags:
        assert escape(claims[flag.claim_id].text) in page and escape(flag.reason) in page


def test_a_failed_stage_is_recorded_and_the_rest_runs(models, clip):  # noqa: F811
    spark = Router(Router(models.spark, Judge(skip=False), "verdicts"), CitingFirst(), "claims")
    broken = replace(models, sam=BrokenSam(), spark=spark)
    out = screen(clip, broken, NoPrecedents(), "t", align=None)
    status = {r.stage: r.status for r in out.stages}
    assert status["regions"] == "failed" and status["transcribe"] == status["on_screen"] == "done"
    assert out.tracks == () and out.claims
    assert out.headline.startswith("Incomplete: regions")


def test_a_failed_check_keeps_the_claims_and_reads_incomplete(models, clip):  # noqa: F811
    spark = Router(models.spark, Judge(skip=True), "verdicts")
    out = screen(clip, replace(models, spark=spark), NoPrecedents(), "t", align=None)
    assert out.claims and out.flags == ()
    assert [r.stage for r in out.stages][-1] == "check" and out.stages[-1].status == "failed"
    assert out.headline == "Incomplete: check failed. No result is given."


def test_failed_stage_log_holds_no_ad_text(models, clip, caplog):  # noqa: F811
    with caplog.at_level(logging.WARNING):
        screen(clip, replace(models, sam=BrokenSam()), NoPrecedents(), "t", align=None)
    assert "stage regions failed: RuntimeError" in caplog.text
    assert SECRET not in caplog.text


def test_claim_recall_raises_on_a_failed_stage(monkeypatch, models, clip):  # noqa: F811
    monkeypatch.setattr(claim_recall, "ingest", lambda path: clip)
    broken = replace(models, sam=BrokenSam())
    with pytest.raises(RuntimeError, match="regions failed"):
        claim_recall.screen(CLIP, broken, "run", Router(models.spark, CitingFirst(), "claims"))


def test_cli_returns_incomplete_when_no_evidence_can_be_checked(tmp_path, monkeypatch, models, clip):  # noqa: F811
    # A valid still may have no detected text or regions; that is not a completed check.
    skipped = Screening(
        screening_id="no-evidence", ad=clip.ad, snapshots=SNAPSHOTS,
        screened_at=datetime.now(UTC),
        stages=(StageRun(stage="claims", status="skipped"), StageRun(stage="check", status="skipped")),
    )
    monkeypatch.setattr(cli, "ingest", lambda path: clip)
    monkeypatch.setattr(cli, "from_env", lambda: models)
    monkeypatch.setattr(cli, "load_precedents", lambda version: NoPrecedents())
    monkeypatch.setattr(cli, "screen", lambda *args, **kwargs: skipped)
    assert cli.main(["screen", str(CLIP), "--out", str(tmp_path / "out"), "--no-align"]) == 1
    saved = Screening.model_validate_json((tmp_path / "out" / "no-evidence.json").read_text(encoding="utf-8"))
    assert saved.headline.startswith("Incomplete")
