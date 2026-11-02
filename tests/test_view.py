import json
from datetime import UTC, date, datetime

from preflight.schema import (
    Ad,
    CapRuleRef,
    Claim,
    Flag,
    OnHoldRef,
    OnScreenEvidence,
    OnScreenText,
    RulingRef,
    Screening,
    Segment,
    Snapshots,
    StageRun,
    TranscriptEvidence,
)
from preflight.sources.register import load_register
from preflight.view import build_view, fold

REGISTER = {e.register_id: e for e in load_register("2026-05-19")}
TIREDNESS = "gbhc-e1f78000ec6b"
SNAPSHOTS = Snapshots(gb_register="2026-05-19", on_hold="2021-01-12", cap_rules="2026-10-31", rulings="2026-11-01")
LINE = "our magnesium tablets banish tiredness for good"
SEG0 = TranscriptEvidence(segment_id="seg-0")
SEG1 = TranscriptEvidence(segment_id="seg-1")
TEXT0 = OnScreenEvidence(text_id="text-0")


def claim(n: int, text: str, *evidence, substance=None) -> Claim:
    return Claim(claim_id=f"claim-{n}", text=text, kind="explicit", substance=substance, evidence=evidence)


def flag(n: int, rules=("15.1",), extra=()) -> Flag:
    sources = (*(CapRuleRef(rule=r) for r in rules), *extra)
    return Flag(
        flag_id=f"flag-{n}", claim_id=f"claim-{n}", kind="possible_breach", reason=f"reason {n}", sources=sources
    )


def build(claims, flags, media="video") -> Screening:
    video = media == "video"
    return Screening(
        screening_id="scr-1",
        ad=Ad(content_hash="a" * 64, media=media, width=320, height=180, duration=10.0 if video else None,
              fps=2.0 if video else None),
        snapshots=SNAPSHOTS, stages=(StageRun(stage="check", status="done"),),
        screened_at=datetime(2026, 11, 1, tzinfo=UTC),
        segments=(Segment(segment_id="seg-0", turn=0, text=LINE, start=1.2, end=3.0, timing="word"),
                  Segment(segment_id="seg-1", turn=1, text="banish tiredness", start=5.0, end=6.0, timing="word")),
        on_screen=(OnScreenText(text_id="text-0", text="Banish tiredness", start=0, end=0),),
        claims=claims, flags=flags,
    )  # fmt: skip


def nested() -> Screening:
    claims = (
        claim(0, LINE, SEG0, substance="magnesium"),
        claim(1, "banish tiredness", SEG0),
        claim(2, "for good", SEG0),
    )
    return build(claims, (flag(0, ("15.6", "15.6.2", "3.7")), flag(1), flag(2)))


def test_nested_claims_on_one_line_fold_into_one_line():
    view = build_view(nested())
    assert len(view["lines"]) == 1
    line = view["lines"][0]
    assert line["claim_id"] == "claim-0"
    assert [f["claim_id"] for f in line["folded"]] == ["claim-1", "claim-2"]
    assert line["evidence"][0]["label"] == "Heard 0:01.2–0:03.0"


def test_contained_claim_with_other_evidence_stays_a_line():
    s = build((claim(0, LINE, SEG0), claim(1, "banish tiredness", SEG1)), (flag(0), flag(1)))
    assert [(top.claim_id, len(rest)) for top, rest in fold(s)] == [("claim-0", 0), ("claim-1", 0)]


def test_ancestor_rules_move_to_other_rules():
    line = build_view(nested())["lines"][0]
    assert line["primary_rules"] == ["15.6.2", "3.7"]
    assert line["other_rules"] == ["15.6"]


def test_ruling_relevance():
    cited = RulingRef(ruling_id="A26-1341476", date=date(2026, 10, 14))
    unknown = RulingRef(ruling_id="X00-0", date=date(2026, 1, 1))
    s = build((claim(0, LINE, SEG0),), (flag(0, ("15.1.1",), (cited, unknown)),))
    rulings = {r["ruling_id"]: r for r in build_view(s)["lines"][0]["rulings"]}
    assert rulings["A26-1341476"]["relevant"] and rulings["A26-1341476"]["date"] == "2026-10-14"
    assert not rulings["X00-0"]["relevant"] and rulings["X00-0"]["url"] is None
    s = build((claim(0, LINE, SEG0),), (flag(0, ("3.7",), (cited,)),))
    assert not build_view(s)["lines"][0]["rulings"][0]["relevant"]


def test_may_say_wording_is_the_snapshot_text():
    entries = [e for m in build_view(nested())["may_say"] for e in m["entries"]]
    by_id = {e["register_id"]: e for e in entries}
    assert by_id[TIREDNESS]["wording"] == REGISTER[TIREDNESS].wording
    assert by_id[TIREDNESS]["conditions"] == REGISTER[TIREDNESS].conditions
    assert len(by_id) == len(entries)


def test_still_image_and_untimed_labels():
    one = (claim(0, "Banish tiredness", TEXT0),)
    assert build_view(build(one, (flag(0),), media="image"))["lines"][0]["evidence"][0]["label"] == "On screen (still)"
    assert build_view(build(one, (flag(0),)))["lines"][0]["evidence"][0]["label"] == "On screen, time not read"


def test_lines_follow_evidence_time_and_view_is_json():
    claims = (claim(0, "banish tiredness", SEG1), claim(1, LINE, SEG0), claim(2, "unflagged", SEG0))
    view = build_view(build(claims, (flag(0), flag(1))))
    assert [x["claim_id"] for x in view["lines"]] == ["claim-1", "claim-0"]
    assert [q["claim_id"] for q in view["quiet_claims"]] == ["claim-2"]
    assert view["checked"] and view["incomplete_stages"] == []
    json.dumps(view)


def test_a_word_inside_another_word_does_not_fold():
    s = build((claim(0, "secure your energy", SEG0), claim(1, "cure", SEG0)), (flag(0), flag(1)))
    assert len(fold(s)) == 2


def test_may_say_groups_a_substance_whatever_its_case():
    s = build((claim(0, LINE, SEG0, substance="Magnesium"), claim(1, "magnesium boost", SEG1, substance="magnesium")),
              (flag(0), flag(1)))  # fmt: skip
    assert [g["substance"] for g in build_view(s)["may_say"]] == ["Magnesium"]


def test_an_unfinished_check_is_incomplete():
    s = nested().model_copy(update={"stages": (StageRun(stage="claims", status="done"),)})
    assert build_view(s)["incomplete_stages"] == ["check"]


def test_a_folded_phrase_keeps_every_source_its_flag_cites():
    held = Flag(
        flag_id="flag-1", claim_id="claim-1", kind="on_hold", reason="on hold",
        sources=(OnHoldRef(on_hold_id="4710"),),
    )  # fmt: skip
    s = build((claim(0, LINE, SEG0), claim(1, "banish tiredness", SEG0)), (flag(0), held))
    (folded,) = build_view(s)["lines"][0]["folded"]
    assert folded["flag_ids"] == ["flag-1"] and folded["on_hold_refs"] == ["4710"]
    assert folded["primary_rules"] == []


def test_untimed_evidence_is_marked_and_quiet_claims_carry_evidence():
    s = build((claim(0, LINE, SEG0), claim(1, "Banish tiredness", TEXT0)), (flag(0),))
    view = build_view(s)
    assert view["lines"][0]["evidence"][0]["timed"]
    (quiet,) = view["quiet_claims"]
    assert quiet["evidence"][0]["timed"] is False


def tier_of(rules, extra=()) -> str:
    return build_view(build((claim(0, LINE, SEG0),), (flag(0, rules, extra),)))["lines"][0]["tier"]


def test_tier_high_for_section_12():
    assert tier_of(("12.1",)) == "high"
    assert tier_of(("3.7", "12.1.2")) == "high"


def test_tier_high_for_15_6():
    assert tier_of(("15.1.1", "15.6.2")) == "high"
    assert tier_of(("15.6",)) == "high"
    assert tier_of(("15.60",)) == "medium"


def test_tier_medium_for_section_15_and_3():
    assert tier_of(("15.1",)) == "medium"
    assert tier_of(("15.1.1",)) == "medium"
    assert tier_of(("3.7",)) == "medium"
    # a section that only starts with the same digits is another section
    assert tier_of(("1.3",)) == "low" and tier_of(("13.1",)) == "low"


def test_tier_low_otherwise():
    assert tier_of(("4.1",)) == "low"
    held = Flag(
        flag_id="flag-0", claim_id="claim-0", kind="on_hold", reason="on hold",
        sources=(OnHoldRef(on_hold_id="4710"),),
    )  # fmt: skip
    assert build_view(build((claim(0, LINE, SEG0),), (held,)))["lines"][0]["tier"] == "low"


def test_tier_rises_with_folded_phrase():
    s = build((claim(0, LINE, SEG0), claim(1, "banish tiredness", SEG0)), (flag(0, ("15.1",)), flag(1, ("12.2",))))
    (line,) = build_view(s)["lines"]
    assert line["primary_rules"] == ["15.1"] and line["tier"] == "high"


def test_lines_sorted_by_tier_then_time():
    claims = (
        claim(0, LINE, SEG0), claim(1, "banish tiredness", SEG1), claim(2, "cures colds", TEXT0),
        claim(3, "other words", SEG1),
    )  # fmt: skip
    flags = (flag(0, ("15.1",)), flag(1, ("12.1",)), flag(2, ("12.1",)), flag(3, ("4.1",)))
    view = build_view(build(claims, flags))
    assert [(x["claim_id"], x["tier"]) for x in view["lines"]] == [
        ("claim-1", "high"), ("claim-2", "high"), ("claim-0", "medium"), ("claim-3", "low"),
    ]  # fmt: skip


def test_unchecked_claims_when_check_did_not_finish():
    s = build((claim(0, LINE, SEG0), claim(1, "unflagged", SEG1)), (flag(0),))
    assert [q["tier"] for q in build_view(s)["quiet_claims"]] == [None]
    unfinished = build((claim(0, LINE, SEG0), claim(1, "unflagged", SEG1)), ())
    unfinished = unfinished.model_copy(update={"stages": (StageRun(stage="check", status="failed"),)})
    view = build_view(unfinished)
    assert [q["tier"] for q in view["quiet_claims"]] == ["unchecked", "unchecked"]
    assert view["tiers"]["unchecked"] == 2 and view["lines"] == []


def test_tier_counts():
    claims = (claim(0, LINE, SEG0), claim(1, "banish tiredness", SEG1), claim(2, "cures colds", TEXT0),
              claim(3, "quiet", SEG1))  # fmt: skip
    view = build_view(build(claims, (flag(0, ("15.1",)), flag(1, ("12.1",)), flag(2, ("4.1",)))))
    assert view["tiers"] == {"high": 1, "medium": 1, "low": 1, "unchecked": 0}
