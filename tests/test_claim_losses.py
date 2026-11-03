import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from preflight.schema import (
    Ad,
    CapRuleRef,
    Claim,
    Flag,
    OnScreenEvidence,
    OnScreenText,
    Screening,
    Segment,
    Snapshots,
    StageRun,
    TranscriptEvidence,
)

spec = importlib.util.spec_from_file_location("claim_losses", Path(__file__).parents[1] / "scripts" / "claim_losses.py")
losses = importlib.util.module_from_spec(spec)
spec.loader.exec_module(losses)

CLAIM, RULES = "reduced stress and anxiety", ["15.6.2"]


def screening(screening_id: str, shown: list[str], claims: dict[str, list[str]], spoken: str = "") -> Screening:
    evidence = TranscriptEvidence(segment_id="seg-0") if spoken else OnScreenEvidence(text_id="text-0")
    # each claim's text maps to the rules its flag cites; an empty list leaves it unflagged
    return Screening(
        screening_id=screening_id, ad=Ad(content_hash="a" * 64, media="image", width=10, height=10),
        snapshots=Snapshots(gb_register="2026-05-19", on_hold="2021-01-12", cap_rules="2026-10-31",
                            rulings="2026-11-01"),
        stages=(StageRun(stage="check", status="done"),), screened_at=datetime(2026, 11, 3, tzinfo=UTC),
        segments=[Segment(segment_id="seg-0", turn=0, text=spoken, start=0, end=1, timing="turn")] if spoken else [],
        on_screen=[OnScreenText(text_id=f"text-{n}", text=t, start=0, end=1) for n, t in enumerate(shown)],
        claims=[Claim(claim_id=f"claim-{n}", text=t, kind="explicit", evidence=(evidence,))
                for n, t in enumerate(claims)],
        flags=[Flag(flag_id=f"flag-{n}", claim_id=f"claim-{n}", kind="possible_breach", reason="r",
                    sources=tuple(CapRuleRef(rule=r) for r in rules))
               for n, rules in enumerate(claims.values()) if rules],
    )  # fmt: skip


def test_a_claim_cut_across_two_cards_is_lost_before_extraction_and_its_flagged_pieces_cover_it():
    # saved cards sort reconstruction-1 before reconstruction, so the second card comes first
    cards = [screening("card-2", ["and anxiety", "Order today"], {"and anxiety": ["15.6.2"]}),
             screening("card-1", ["Reduced stress"], {"Reduced stress": ["15.6"]})]  # fmt: skip
    assert losses.lost_at(CLAIM, RULES, cards) == "shown in pieces across screenings"
    assert losses.pieces_caught(CLAIM, RULES, cards)


def test_pieces_on_one_screen_are_told_apart_from_pieces_across_cards():
    one = [screening("video", ["Reduced stress", "and anxiety"], {"Reduced stress": []})]
    assert losses.lost_at(CLAIM, RULES, one) == "shown in pieces on one ad's screens"
    # only one piece is flagged, so the pieces do not cover the claim
    assert not losses.pieces_caught(CLAIM, RULES, one)


def test_a_whole_claim_spoken_inside_a_long_flagged_quote_fails_only_on_length():
    sentence = "I have been sleeping so well this month and the best part is reduced stress and anxiety all day long"
    s = [screening("video", [], {sentence: ["15.6.2"]}, spoken=sentence)]
    assert losses.lost_at(CLAIM, RULES, s) == "flagged, quote too long to score"


def test_a_whole_claim_flagged_under_an_unrelated_rule_is_the_judge_missing_it():
    s = [screening("still", ["Reduced stress and anxiety"], {"Reduced stress and anxiety": ["3.7"]})]
    assert losses.lost_at(CLAIM, RULES, s) == "flagged with another rule"
    s = [screening("still", ["Reduced stress and anxiety"], {"Reduced stress and anxiety": []})]
    assert losses.lost_at(CLAIM, RULES, s) == "not flagged"


def test_a_second_card_is_filed_under_its_item(tmp_path, monkeypatch):
    monkeypatch.setattr(losses, "WORK", tmp_path)
    (tmp_path / "run").mkdir()
    for name in ("A24-1239908-reconstruction", "A24-1239908-reconstruction-1", "N01-ad"):
        s = screening(f"run-{name}", [], {})
        (tmp_path / "run" / f"{s.screening_id}.json").write_text(s.model_dump_json(), encoding="utf-8")
    # a team ad's media is ad.mp4 or ad.png, so its stem is ad
    assert {k: len(v) for k, v in losses.saved_screenings("run").items()} == {"A24-1239908": 2, "N01": 1}


def test_unmatched_lines_are_counted_by_tier_and_sampled_without_the_ruling(tmp_path, monkeypatch, capsys):
    scripts = Path(__file__).parents[1] / "scripts"
    spec = importlib.util.spec_from_file_location("unmatched", scripts / "unmatched_lines.py")
    unmatched = importlib.util.module_from_spec(spec)
    monkeypatch.syspath_prepend(str(scripts))
    spec.loader.exec_module(unmatched)
    ruled = screening("run-A1-ad", ["Reduced stress and anxiety", "Boosts energy"],
                      {"Reduced stress and anxiety": ["15.6.2"], "Boosts energy": ["15.1"]})
    clean = screening("run-N1-ad", ["Supports immunity"], {"Supports immunity": ["15.1"]})
    truths = {"A1": SimpleNamespace(label="positive", claims=[SimpleNamespace(claim=CLAIM, rules=RULES)]),
              "N1": SimpleNamespace(label="negative", claims=[])}  # fmt: skip
    monkeypatch.setattr(unmatched, "saved_screenings", lambda run: {"A1": [ruled], "N1": [clean]})
    monkeypatch.setattr(unmatched, "load_ground_truth", lambda split, item: truths[item])
    counts, lines = unmatched.tally("run")
    assert counts["positive", "high", "matched"] == 1 and counts["positive", "medium", "unmatched"] == 1
    assert counts["negative", "medium", "unmatched"] == 1
    assert sorted(x["text"] for x in lines) == ["Boosts energy", "Supports immunity"]
    # the grading sheet holds the flag, never the ASA's claim it failed to match
    assert all(CLAIM not in " ".join(x.values()) for x in lines)
