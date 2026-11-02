import csv
import io
import wave
from datetime import UTC, datetime

import pytest

from preflight.eval import check_recall, registry
from preflight.eval.reconstruct import LABEL, overlay_filter
from preflight.eval.registry import Metric, register, revision
from preflight.eval.run import MeteredSam, MeteredTranscribe
from preflight.eval.score import exact, interval, metrics, score_item
from preflight.eval.split import BreachingClaim, GroundTruth
from preflight.eval.team_media import LABEL as TEAM_LABEL
from preflight.models.clients import SamResult
from preflight.schema import Ad, CapRuleRef, Claim, Flag, OnScreenEvidence, OnScreenText, Screening, Snapshots, StageRun

SNAPSHOTS = Snapshots(gb_register="2026-05-19", on_hold="2021-01-12", cap_rules="2026-10-31", rulings="2026-11-01")


def screening(screening_id: str, claims: list[str], flags: dict[int, list[str]]) -> Screening:
    texts = [OnScreenText(text_id=f"text-{n}", text=t, start=0, end=1) for n, t in enumerate(claims)]
    return Screening(
        screening_id=screening_id, ad=Ad(content_hash="a" * 64, media="image", width=10, height=10),
        snapshots=SNAPSHOTS, stages=(StageRun(stage="check", status="done"),),
        screened_at=datetime(2026, 11, 1, tzinfo=UTC), on_screen=texts,
        claims=[
            Claim(claim_id=f"claim-{n}", text=t, kind="explicit", evidence=(OnScreenEvidence(text_id=f"text-{n}"),))
            for n, t in enumerate(claims)
        ],
        flags=[
            Flag(flag_id=f"flag-{n}", claim_id=f"claim-{n}", kind="possible_breach", reason="r",
                 sources=tuple(CapRuleRef(rule=r) for r in rules))
            for n, rules in flags.items()
        ],  # fmt: skip
    )


def truth(item_id: str, claims: list[tuple[str, list[str]]]) -> GroundTruth:
    return GroundTruth(
        item_id=item_id, kind="team" if item_id.startswith("T") else "ruling",
        label="positive" if claims else "negative", outcome=None, written_by="w", checked_by="c",
        claims=[BreachingClaim(claim=c, rules=r, points=[1]) for c, r in claims],
    )


# two positives and two negatives with known answers
TOY = [
    score_item(
        truth("A1", [("cures anxiety fast", ["15.6.2"]), ("doctor recommended", ["12.1"]), ("sleep deeper", ["15.1"])]),
        [screening("s1", ["Cures anxiety fast!", "Doctor recommended formula", "Sleep deeper every night with our "
                          "unique blend of calming herbs, picked by hand and dried slowly"],
                   {0: ["15.6"], 1: ["3.7"], 2: ["15.1"]})],  # fmt: skip
        kept=[True, True, False],
    ),
    score_item(truth("A2", [("boosts immunity", ["15.1.1"])]), [screening("s2", ["Boosts immunity"], {})]),
    score_item(truth("T1", []), [screening("s3", ["Vitamin C contributes", "Tasty"], {0: ["15.1"]})]),
    score_item(truth("T2", []), [screening("s4", ["Iron contributes"], {})]),
]


def by_name() -> dict[str, Metric]:
    return {m.name: m for m in metrics(TOY)}


def test_a_flag_counts_only_with_a_related_rule_on_a_matching_claim():
    a1 = TOY[0]
    # 15.6 is the parent of 15.6.2; 3.7 is unrelated to 12.1; the sleep quote is too long to match
    assert (a1.caught, a1.caught_any_rule, a1.caught_carried, a1.carried, a1.flags) == (1, 2, 1, 2, 3)
    assert TOY[1].caught == 0


def test_extra_rules_count_for_with_rule_but_not_exact_rules():
    item = score_item(
        truth("A3", [("cures anxiety fast", ["15.6.2"]), ("sleep deeper", ["15.1"])]),
        [screening("s5", ["Cures anxiety fast", "Sleep deeper"], {0: ["15.6", "3.7", "15.7"], 1: ["15.1.1"]})],
    )
    assert (item.caught, item.caught_exact_rules) == (2, 1)
    # 15.6 and 15.1.1 relate to their claims' rules; 3.7 and 15.7 do not
    assert (item.rules_related, item.rules_cited) == (2, 4)


def test_former_rule_numbers_are_read_in_current_numbering():
    flags = [screening("s6", ["Half the price of the leading brand"], {0: ["3.39"]})]
    before = truth("A23-1216841", [("Half the price of the leading brand", ["3.40"])])
    after = truth("A99-0000001", [("Half the price of the leading brand", ["3.40"])])
    assert score_item(before, flags).caught == 1  # this ruling cites the earlier 3.40, now 3.39
    assert score_item(after, flags).caught == 0  # elsewhere 3.40 is the current rule on who made the product
    approved = [screening("s7", ["FSA approved"], {0: ["3.52"]})]
    assert score_item(truth("A24-1241017", [("FSA approved", ["3.50"])]), approved).caught == 1  # 3.50 is now 3.52
    assert score_item(truth("A23-1216841", [("FSA approved", ["3.50"])]), approved).caught == 0  # renumbered per ruling


def test_a_flag_carrying_two_claims_is_judged_against_both_claims_rules():
    item = score_item(
        truth("A4", [("strengthen muscles", ["15.1", "15.1.1"]), ("combat stress", ["15.6", "15.6.2"])]),
        [screening("s8", ["Strengthen muscles and combat stress"], {0: ["15.1.1", "15.6.2"]})],
    )
    assert (item.caught, item.caught_exact_rules, item.caught_all_rules) == (2, 2, 2)
    # the flag's two rules are counted once, each related to one of the claims it carries
    assert (item.rules_related, item.rules_cited) == (2, 2)
    assert (item.rules_found, item.rules_wanted) == (4, 4)


def test_leaving_rules_out_costs_rule_recall_but_not_exact_rules():
    item = score_item(
        truth("A5", [("supports vitality", ["15.2", "15.7"])]),
        [screening("s9", ["Supports vitality"], {0: ["15.2"]})],
    )
    assert (item.caught_exact_rules, item.caught_all_rules) == (1, 0)
    assert (item.rules_related, item.rules_cited, item.rules_found, item.rules_wanted) == (1, 1, 1, 2)


def test_toy_split_scores():
    m = by_name()
    assert (m["ad_recall"].hits, m["ad_recall"].total) == (1, 2)
    assert (m["claim_recall"].hits, m["claim_recall"].total) == (1, 4)
    assert (m["claim_recall_carried"].hits, m["claim_recall_carried"].total) == (1, 3)
    assert (m["claim_recall_any_rule"].hits, m["claim_recall_any_rule"].total) == (2, 4)
    assert (m["claim_recall_exact_rules"].hits, m["claim_recall_exact_rules"].total) == (1, 4)
    assert (m["rule_precision"].hits, m["rule_precision"].total) == (1, 2)
    assert (m["flags_per_positive_ad"].hits, m["flags_per_positive_ad"].total) == (3, 2)
    assert (m["negative_ads_flagged"].hits, m["negative_ads_flagged"].total) == (1, 2)
    assert (m["flags_per_negative_ad"].hits, m["flags_per_negative_ad"].total) == (1, 2)


def test_line_metrics_count_top_level_claims():
    nested = screening(
        "s5", ["sleep deeper tonight", "sleep deeper", "other words"], {0: ["15.1"], 1: ["15.1"], 2: ["3.7"]}
    )
    shared = (OnScreenEvidence(text_id="text-0"),)
    nested = nested.model_copy(update={"claims": [
        c.model_copy(update={"evidence": shared}) if c.claim_id != "claim-2" else c for c in nested.claims
    ]})  # fmt: skip
    item = score_item(truth("A3", [("sleep deeper", ["15.1"])]), [nested])
    # the second claim folds under the first, so three flags make two lines and only "other words" matches nothing
    assert (item.flags, item.lines, item.unmatched_lines) == (3, 2, 1)
    m = {x.name: x for x in metrics([item])}
    assert (m["flagged_lines_per_positive_ad"].hits, m["flagged_lines_per_positive_ad"].total) == (2, 1)
    assert m["unmatched_lines_per_positive_ad"].hits == 1


def test_existing_metrics_keep_their_values():
    found = {x.name: (x.hits, x.total) for x in metrics(TOY)}
    assert {n: found[n] for n in ("ad_recall", "claim_recall", "claim_recall_carried", "claim_recall_any_rule",
                                  "flags_per_positive_ad")} == {
        "ad_recall": (1, 2), "claim_recall": (1, 4), "claim_recall_carried": (1, 3),
        "claim_recall_any_rule": (2, 4), "flags_per_positive_ad": (3, 2),
    }  # fmt: skip


def test_intervals_hold_the_point_estimate_and_repeat():
    for m in metrics(TOY):
        if m.low is not None:
            assert m.low <= m.hits / m.total <= m.high
    assert metrics(TOY) == metrics(TOY)
    assert interval(TOY[:1], lambda i: 1, lambda i: 1) == (1.0, 1.0)


def test_exact_upper_bounds_for_no_false_alarms():
    assert exact(0, 10) == (0.0, 0.308)
    assert exact(0, 15) == (0.0, 0.218)
    assert exact(5, 10) == (0.187, 0.813)
    assert exact(25, 25) == (0.863, 1.0)


def test_ad_counts_get_exact_intervals():
    m = by_name()
    assert (m["ad_recall"].low, m["ad_recall"].high) == exact(1, 2)
    assert (m["negative_ads_flagged"].low, m["negative_ads_flagged"].high) == exact(1, 2)


def test_rule_precision_and_recall_get_intervals():
    m = by_name()
    assert m["rule_precision"].low is not None and m["rule_recall"].low is not None


def test_judge_only_false_alarms_get_an_exact_interval():
    negatives = {f"T{n}": [screening(f"s{n}", ["Iron contributes"], {})] for n in range(10)}
    _, found = check_recall.scored(negatives, {i: truth(i, []) for i in negatives})
    assert next(m for m in found if m[0] == "negative_ads_flagged_judge_only") == (
        "negative_ads_flagged_judge_only", 0, 10, 0.0, 0.308,
    )


def test_only_negatives_give_no_recall():
    assert {m.name for m in metrics(TOY[2:])} == {"negative_ads_flagged", "flags_per_negative_ad"}


def test_register_adds_new_columns_to_old_rows(tmp_path, monkeypatch):
    runs = tmp_path / "runs.csv"
    runs.write_text("run_id,metric,hits,total\nold,claim_recall,1,2\n", encoding="utf-8")
    monkeypatch.setattr(registry, "RUNS", runs)
    register({"run_id": "new", "snapshots": "cap_rules=2026-10-31"}, [("ad_recall", 1, 2), Metric("x", 3, 4, 0.5, 0.9)])
    with runs.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == registry.FIELDS
    assert [(r["run_id"], r["metric"], r["low"]) for r in rows] == [
        ("old", "claim_recall", ""), ("new", "ad_recall", ""), ("new", "x", "0.5"),
    ]


@pytest.mark.parametrize(("status", "part", "expected"), [("", "test", "abc"), (" M x.py", "dev", "abc-dirty")])
def test_revision(monkeypatch, status, part, expected):
    monkeypatch.setattr(registry, "git", lambda *a: "abc\n" if a[0] == "rev-parse" else status)
    assert revision(part) == expected


def test_test_part_refuses_a_dirty_or_untracked_tree(monkeypatch):
    monkeypatch.setattr(registry, "git", lambda *a: "abc\n" if a[0] == "rev-parse" else "?? prompts/judge_v4.txt")
    with pytest.raises(SystemExit, match="dirty"):
        revision("test")


def test_team_ads_are_not_labelled_as_reconstructions():
    assert TEAM_LABEL in overlay_filter(["Iron contributes"], TEAM_LABEL)
    assert LABEL not in overlay_filter(["Iron contributes"], TEAM_LABEL)



class FakeSam:
    def segment(self, prompt, **media):
        return SamResult([], {"video_frames_processed": 20} if "video" in media else {})


class FakeTranscribe:
    def transcribe(self, wav):
        return []


def test_meters_price_sam_frames_and_transcribed_audio():
    sam = MeteredSam(FakeSam())
    sam.segment("label", video="clip.mp4")
    sam.segment("label", image=b"png")
    # SAM bills at least 50 frames per video
    assert sam.usd == pytest.approx([50 * 0.0002, 0.0025])
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(bytes(2 * 16000 * 36))
    heard = MeteredTranscribe(FakeTranscribe())
    heard.transcribe(buffer.getvalue())
    assert heard.usd == pytest.approx([36 / 3600 * 0.18])
