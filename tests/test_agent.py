import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from preflight.agent import Draft, DraftScene, digest, fix, is_clean, load_draft
from preflight.agent.draft import Address, lines
from preflight.pipeline import SNAPSHOTS
from preflight.schema import (
    Ad,
    Claim,
    Flag,
    OnScreenEvidence,
    OnScreenText,
    RegisterRef,
    Screening,
    Segment,
    StageRun,
    SuggestedWording,
    TranscriptEvidence,
)
from preflight.sources.register import load_register

FIXTURE = Path(__file__).parent / "fixtures" / "agent" / "magnesium"
REGISTER = {e.register_id: e for e in load_register(SNAPSHOTS.gb_register)}
FATIGUE, NERVES = "gbhc-e1f78000ec6b", "gbhc-63277e369bb5"
SECRET = "secret ad text"


def wording(register_id: str) -> SuggestedWording:
    return SuggestedWording.from_entry(REGISTER[register_id])


def screening(screening_id, claims=(), flags=(), failed=False, previous_id=None) -> Screening:
    return Screening(
        screening_id=screening_id, previous_id=previous_id,
        ad=Ad(content_hash="0" * 64, media="video", width=1280, height=720, duration=8.0, fps=25.0),
        snapshots=SNAPSHOTS, stages=(StageRun(stage="check", status="failed" if failed else "done"),),
        screened_at=datetime.now(UTC),
        segments=(Segment(segment_id="s0", start=0, end=2, turn=0, text="x", timing="word"),),
        on_screen=(OnScreenText(text_id="t0", start=5, end=7, text="x"),),
        claims=tuple(claims), flags=tuple(flags),
    )


def claim(claim_id, text, kind="transcript") -> Claim:
    evidence = TranscriptEvidence(segment_id="s0") if kind == "transcript" else OnScreenEvidence(text_id="t0")
    return Claim(claim_id=claim_id, text=text, kind="explicit", evidence=(evidence,))


def flag(flag_id, claim_id, register_id=None) -> Flag:
    return Flag(
        flag_id=flag_id, claim_id=claim_id, kind="possible_breach", reason="r",
        sources=(RegisterRef(register_id=FATIGUE),),
        suggested_wording=wording(register_id) if register_id else None,
    )


def draft_of(tmp_path, voiceover="Banish tiredness for good. Calm nerves always.", captions=("Magnesium tablets",)):
    still = tmp_path / "still.png"
    still.write_bytes((FIXTURE / "still.png").read_bytes())
    return Draft(
        format="video",
        scenes=(DraftScene(still=still, on_screen_text=captions, voiceover=voiceover),),
    )


class Scripted:
    # answers each screening from the next builder, which gets the screening id and its predecessor
    def __init__(self, *builders):
        self.builders, self.drafts = list(builders), []

    def __call__(self, draft, screening_id, previous_id):
        self.drafts.append(draft)
        return self.builders.pop(0)(screening_id, previous_id)


def run(draft, screen_draft, tmp_path, rounds=3):
    work = tmp_path / "work"
    result = fix(
        draft, screen_draft=screen_draft, rounds=rounds, log=work / "audit.jsonl", work_dir=work
    )
    return result, [json.loads(line) for line in (work / "audit.jsonl").read_text(encoding="utf-8").splitlines()]


def replay(draft):
    manifest = json.loads((FIXTURE / "replay.json").read_text(encoding="utf-8"))
    return FIXTURE / manifest[digest(draft)]


def recorded(draft, screening_id, previous_id):
    found = Screening.model_validate_json(replay(draft).read_text(encoding="utf-8"))
    return found.model_copy(update={"screening_id": screening_id, "previous_id": previous_id})


def test_replay_reaches_awaiting_approval(tmp_path):
    result, records = run(load_draft(FIXTURE / "draft.yaml"), recorded, tmp_path)
    assert result.state == "awaiting_approval"
    assert not result.screening.flags
    assert all(r.status != "failed" for r in result.screening.stages)
    assert records[-1]["state"] == "awaiting_approval"
    assert result.screening.previous_id == records[0]["screening_id"]


def test_every_substitution_is_register_wording(tmp_path):
    result, records = run(load_draft(FIXTURE / "draft.yaml"), recorded, tmp_path)
    register = {e.register_id: e for e in load_register("2026-05-19") if e.status == "authorised"}
    substitutions = [s for r in records if r["event"] == "round" for s in r["substitutions"]]
    assert substitutions
    final = lines(result.draft)
    for s in substitutions:
        assert s["after"] == register[s["register_id"]].wording
        assert final[Address.parse(s["line"])].removesuffix(".") == s["after"]


def test_flag_without_wording_goes_to_person(tmp_path):
    c = claim("c0", "Banish tiredness for good")
    result, records = run(
        draft_of(tmp_path), Scripted(lambda i, p: screening(i, [c], [flag("f0", "c0")])), tmp_path
    )
    assert result.state == "needs_person"
    assert records[0]["for_person"] == [{"flag_id": "f0", "reason": "no authorised wording"}]
    assert not records[0]["substitutions"]
    assert lines(result.draft) == lines(draft_of(tmp_path))


def test_unmatched_or_ambiguous_flag_goes_to_person(tmp_path):
    ambiguous = draft_of(tmp_path, voiceover="", captions=("Magnesium tablets", "Magnesium tablets today"))
    cases = [
        (draft_of(tmp_path), claim("c0", "Cures every illness", "on_screen")),
        (ambiguous, claim("c0", "Magnesium tablets", "on_screen")),
    ]
    for draft, c in cases:
        result, records = run(
            draft, Scripted(lambda i, p, c=c: screening(i, [c], [flag("f0", "c0", FATIGUE)])), tmp_path / "x"
        )
        assert result.state == "needs_person"
        assert records[0]["for_person"] == [{"flag_id": "f0", "reason": "could not locate the claim in the draft"}]
        assert lines(result.draft) == lines(draft)


def test_failed_stage_is_never_clean(tmp_path):
    result, records = run(draft_of(tmp_path), Scripted(lambda i, p: screening(i, failed=True)), tmp_path)
    assert not is_clean(result.screening)
    assert result.state == "needs_person"
    assert records[-1]["state"] == "needs_person"


def test_no_change_stops_with_needs_person(tmp_path):
    c = claim("c0", "Banish tiredness for good")
    screener = Scripted(lambda i, p: screening(i, [c], [flag("f0", "c0")]), lambda i, p: pytest.fail("second round"))
    result, records = run(draft_of(tmp_path), screener, tmp_path)
    assert result.state == "needs_person"
    assert [r["event"] for r in records] == ["round", "state"]


def test_fix_never_writes_approval(tmp_path):
    result, records = run(load_draft(FIXTURE / "draft.yaml"), recorded, tmp_path)
    assert result.state == "awaiting_approval"
    assert "approved" not in {r["event"] for r in records}
    assert not hasattr(result, "approved")


def test_no_ad_text_in_logging(tmp_path, caplog):
    def broken(i, p):
        raise RuntimeError(SECRET)

    with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError):
        run(draft_of(tmp_path, voiceover=SECRET), Scripted(broken), tmp_path)
    assert SECRET not in caplog.text
