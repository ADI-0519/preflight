import csv
import importlib.util
import json
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_eval import saved_run

from preflight.eval import registry, run
from preflight.eval.score import line_counts
from preflight.eval.split import BreachingClaim, GroundTruth
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


def test_a_second_card_is_filed_under_its_registered_item(tmp_path, monkeypatch):
    _, work = saved_run(tmp_path, monkeypatch)
    registry.write_rows(tmp_path / "runs" / "screen-1.csv", [{"item_id": "A24-1", "media": 2}])
    for path in (work / "screen-1").glob("*.json"):
        path.unlink()
    for stem in ("reconstruction", "reconstruction-1"):
        s = screening(f"screen-1-A24-1-{stem}", [], {})
        (work / "screen-1" / f"{s.screening_id}.json").write_text(s.model_dump_json(), encoding="utf-8")
    assert {k: len(v) for k, v in run.saved("screen-1")[1].items()} == {"A24-1": 2}


def test_single_run_cli_reports_all_misses_without_network_or_registry_writes(tmp_path, monkeypatch, capsys):
    runs, work = saved_run(tmp_path, monkeypatch)
    # Replace the positive ad with an extracted, unflagged claim and an unrelated flagged line.
    s = screening("screen-1-A24-1-reconstruction", ["Cures anxiety fast", "Orange flavour"],
                  {"Cures anxiety fast": [], "Orange flavour": ["15.1"]})
    (work / "screen-1" / f"{s.screening_id}.json").write_text(s.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(losses, "kept", lambda _: None)
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("diagnostics used the network"))
    before = runs.read_bytes()
    monkeypatch.setattr(sys, "argv", ["claim_losses.py", "screen-1", "--json"])
    losses.main()
    report = json.loads(capsys.readouterr().out)
    assert (report["caught"], report["carried"], len(report["misses"])) == (0, 1, 1)
    assert report["misses_by_step"]["not flagged"] == 1
    assert report["unmatched_by_tier"] == {"high": 0, "medium": 1, "low": 0, "unchecked": 0}
    assert report["unmatched_lines"][0]["text"] == "Orange flavour"
    assert runs.read_bytes() == before


@pytest.mark.parametrize("case", ["missing", "test", "foreign"])
def test_diagnostic_guards_run_before_labels(tmp_path, monkeypatch, case):
    _, work = saved_run(tmp_path, monkeypatch, part="test" if case == "test" else "dev")
    if case == "missing":
        (work / "screen-1" / "screen-1-T16-ad.json").unlink()
    elif case == "foreign":
        (work / "screen-1" / "screen-1-held-out-ad.json").write_text("must not open")
    monkeypatch.setattr(run, "load_ground_truth", lambda *args: pytest.fail("guard opened labels"))
    with pytest.raises(SystemExit):
        losses.diagnose("screen-1")


def test_grading_sheet_samples_unmatched_lines_without_the_ruling(tmp_path, monkeypatch):
    s = screening("s", ["Reduced stress and anxiety", "Boosts energy", "Supports immunity"],
                  {"Reduced stress and anxiety": ["15.6.2"], "Boosts energy": ["15.1"], "Supports immunity": ["15.1"]})
    truth = GroundTruth(item_id="T1", kind="team", label="positive", outcome=None, written_by="synthetic",
                        checked_by=None, claims=[BreachingClaim(claim=CLAIM, rules=RULES, points=[1])])
    monkeypatch.setattr(losses, "saved", lambda *args: (
        {"run_id": "screen-1", "split": "v2", "part": "dev", "stage": "screen"}, {"T1": [s]}, [truth],
    ))
    report = losses.diagnose("screen-1")
    out = tmp_path / "sheet.csv"
    assert losses.grading_sheet(report, 1, out) == 1
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert rows[0]["text"] in {"Boosts energy", "Supports immunity"} and rows[0]["grade"] == ""
    # the same run always draws the same lines, and the ASA's claim never reaches the grader
    again = tmp_path / "again.csv"
    losses.grading_sheet(report, 1, again)
    assert again.read_text(encoding="utf-8") == out.read_text(encoding="utf-8")
    assert CLAIM not in out.read_text(encoding="utf-8").lower()


def test_empty_target_is_not_covered_by_empty_pieces():
    assert not losses.covered("", [])


def test_folded_child_with_matching_rule_keeps_whole_line_out_of_unmatched_report(monkeypatch):
    text = "Reduced stress and anxiety"
    s = screening("s", [text], {text + " through a calmer daily routine": ["3.7"], text: ["15.6.2"]})
    truth = GroundTruth(item_id="T1", kind="team", label="positive", outcome=None, written_by="synthetic",
                        checked_by=None, claims=[BreachingClaim(claim=text, rules=RULES, points=[1])])
    monkeypatch.setattr(losses, "saved", lambda *args: (
        {"run_id": "screen-1", "split": "v2", "part": "dev", "stage": "screen"}, {"T1": [s]}, [truth],
    ))
    report = losses.diagnose("screen-1")
    assert line_counts(truth.claims, [s]) == (1, 0)
    assert report["unmatched_lines"] == []


def test_baseline_comparison_counts_only_claims_previously_caught(monkeypatch):
    text = "Reduced stress and anxiety"
    truth = GroundTruth(item_id="T1", kind="team", label="positive", outcome=None, written_by="synthetic",
                        checked_by=None, claims=[BreachingClaim(claim=text, rules=RULES, points=[1])])
    plain = screening("plain", [text], {text: ["15.6.2"]})
    after = screening("after", [text], {text: []})
    def saved(run_id, directory=None):
        return ({"run_id": run_id, "split": "v2", "part": "dev",
                 "stage": "screen" if run_id == "plain" else "stress"},
                {"T1": [plain if run_id == "plain" else after]}, [truth])
    monkeypatch.setattr(losses, "saved", saved)
    report = losses.diagnose("stress", baseline="plain")
    assert report["miss_scope"] == "lost against baseline"
    assert report["misses_by_step"]["not flagged"] == 1
    assert report["misses"][0]["format"] == "stills"
    plain = plain.model_copy(update={"flags": ()})
    assert losses.diagnose("stress", baseline="plain")["misses"] == []
