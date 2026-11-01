import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from preflight.agent import Draft, DraftScene, approve, digest, fix, is_clean, load_draft
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


class Image:
    def __init__(self):
        self.calls = []

    def edit(self, image, prompt):
        self.calls.append((image, prompt))
        return b"edited-%d" % len(self.calls)


def run(draft, screen_draft, tmp_path, rounds=3, image=None):
    work = tmp_path / "work"
    result = fix(
        draft, screen_draft=screen_draft, image=image or Image(), rounds=rounds, log=work / "audit.jsonl", work_dir=work
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
    assert records[0]["for_person"] == [{"flag_id": "f0", "reason": "no authorised wording", "line": "0/voiceover/0"}]
    assert not records[0]["substitutions"]
    assert lines(result.draft) == lines(draft_of(tmp_path))


def test_nested_flags_are_handed_off_as_one_line(tmp_path):
    claims = [claim("c0", "Banish tiredness for good"), claim("c1", "Banish tiredness")]
    flags = [flag("f0", "c0"), flag("f1", "c1")]
    result, records = run(draft_of(tmp_path), Scripted(lambda i, p: screening(i, claims, flags)), tmp_path)
    (group,) = result.open
    assert group["line"] == "0/voiceover/0" and group["text"] == "Banish tiredness for good."
    assert [f["flag_id"] for f in group["flags"]] == ["f0", "f1"]
    assert records[-1]["open"] == result.open


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
        assert records[0]["for_person"] == [
            {"flag_id": "f0", "reason": "could not locate the claim in the draft", "line": None}
        ]
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


def test_round_limit(tmp_path):
    c = claim("c0", "Cures every illness", "on_screen")
    screener = Scripted(*[lambda i, p: screening(i, [c], [flag("f0", "c0")])] * 3)
    image = Image()
    result, records = run(draft_of(tmp_path), screener, tmp_path, rounds=2, image=image)
    assert result.state == "needs_person"
    assert len(image.calls) == 2
    assert [r["round"] for r in records if r["event"] == "round"] == [0, 1, 2]
    assert records[-2]["for_person"] == [{"flag_id": "f0", "reason": "round limit reached", "line": None}]
    assert [r["previous_id"] for r in map(lambda s: json.loads(s.read_text(encoding="utf-8")), sorted(
        (tmp_path / "work").glob("*-?.json")))] == [None, records[0]["screening_id"], records[1]["screening_id"]]


def test_still_edit_on_unmatched_on_screen_claim(tmp_path):
    c = claim("c0", "Cures every illness", "on_screen")
    screener = Scripted(lambda i, p: screening(i, [c], [flag("f0", "c0")]), lambda i, p: screening(i, previous_id=p))
    image = Image()
    start = draft_of(tmp_path)
    result, records = run(start, screener, tmp_path, image=image)
    assert result.state == "awaiting_approval"
    (edit,) = records[0]["still_edits"]
    assert edit["scene"] == 0 and "Cures every illness" in edit["prompt"]
    assert image.calls[0][0] == start.scenes[0].still.read_bytes()
    assert screener.drafts[1].scenes[0].still.read_bytes() == b"edited-1"
    assert lines(screener.drafts[1]) == lines(start)


def test_ambiguous_caption_claim_leaves_still_alone(tmp_path):
    draft = draft_of(tmp_path, voiceover="", captions=("Magnesium tablets", "Magnesium tablets today"))
    c = claim("c0", "Magnesium tablets", "on_screen")
    image = Image()
    result, records = run(draft, Scripted(lambda i, p: screening(i, [c], [flag("f0", "c0")])), tmp_path, image=image)
    assert result.state == "needs_person"
    assert not image.calls
    assert records[0]["for_person"] == [{"flag_id": "f0", "reason": "no authorised wording", "line": None}]


def test_fix_never_writes_approval(tmp_path):
    result, records = run(load_draft(FIXTURE / "draft.yaml"), recorded, tmp_path)
    assert result.state == "awaiting_approval"
    assert "approved" not in {r["event"] for r in records}
    assert not hasattr(result, "approved")


def test_approve_rules(tmp_path):
    _, _ = run(load_draft(FIXTURE / "draft.yaml"), recorded, tmp_path)
    log = tmp_path / "work" / "audit.jsonl"
    before = log.read_bytes()
    with pytest.raises(ValueError):
        approve(log, "  ")
    assert log.read_bytes() == before
    record = approve(log, "Ana", "checked the footnote")
    after = log.read_bytes()
    assert after.startswith(before)
    assert json.loads(after[len(before):]) == record
    assert record["by"] == "Ana" and record["screening_id"] == json.loads(before.splitlines()[-1])["screening_id"]
    with pytest.raises(ValueError):
        approve(log, "Ben")
    assert log.read_bytes() == after


def test_approve_refuses_needs_person(tmp_path):
    c = claim("c0", "Banish tiredness for good")
    run(draft_of(tmp_path), Scripted(lambda i, p: screening(i, [c], [flag("f0", "c0")])), tmp_path)
    with pytest.raises(ValueError):
        approve(tmp_path / "work" / "audit.jsonl", "Ana")


def test_no_ad_text_in_logging(tmp_path, caplog):
    def broken(i, p):
        raise RuntimeError(SECRET)

    with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError):
        run(draft_of(tmp_path, voiceover=SECRET), Scripted(broken), tmp_path)
    assert SECRET not in caplog.text
