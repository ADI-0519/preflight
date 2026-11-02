import csv
import io
import wave
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from preflight.eval import check_recall, registry, run, score
from preflight.eval.reconstruct import LABEL, overlay_filter
from preflight.eval.registry import Metric, register, revision
from preflight.eval.run import MeteredSam, MeteredTranscribe, citation_spread
from preflight.eval.score import exact, interval, metrics, near_miss, score_item
from preflight.eval.split import BreachingClaim, GroundTruth, TeamAd
from preflight.eval.team_media import LABEL as TEAM_LABEL
from preflight.models.clients import SamResult
from preflight.schema import (
    Ad,
    CapRuleRef,
    Claim,
    Flag,
    OnScreenEvidence,
    OnScreenText,
    RulingRef,
    Screening,
    Snapshots,
    StageRun,
    SuggestedWording,
)

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


def test_extra_rules_dilute_the_weighted_catch():
    item = score_item(
        truth("A3", [("cures anxiety fast", ["15.6.2"]), ("sleep deeper", ["15.1"])]),
        [screening("s5", ["Cures anxiety fast", "Sleep deeper"], {0: ["15.6", "3.7", "15.7"], 1: ["15.1.1"]})],
    )
    # one right rule of three, then one of one
    assert item.weighted_carried == pytest.approx(1 / 3 + 1, abs=0.001)


def test_citing_every_rule_catches_by_chance():
    pack = score._screenable(SNAPSHOTS.cap_rules)
    one, every = (
        score_item(truth("A6", [("cures anxiety fast", ["15.6.2"])]), [screening("s", ["Cures anxiety fast"], {0: r})])
        for r in (["3.7"], list(pack))
    )
    fitting = sum(score.fits(r, ["15.6.2"]) for r in pack)
    assert one.chance_carried == pytest.approx(fitting / len(pack), abs=0.001)
    assert every.chance_carried == 1.0 and every.caught_carried == 1
    assert every.weighted_carried == pytest.approx(fitting / len(pack), abs=0.001)


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


def test_near_miss_scores_the_inserted_line_and_the_clean_ones():
    ad = TeamAd(
        item_id="N99", format="image", product="vitamin C tablets", register_ids=["gbhc-222b3bfc340d"],
        on_screen_text=["Vitamin C contributes to the normal function of the immune system", "Zesty orange flavour",
                        "Vitamin C supercharges your immune system"],
        voiceover="", base="T99", inserted="Vitamin C supercharges your immune system", substance="Vitamin C",
    )
    truth = GroundTruth(
        item_id="N99", kind="team", label="positive", outcome=None, written_by="w", checked_by="c",
        claims=[BreachingClaim(claim=ad.inserted, rules=["15.1", "15.1.1", "15.7"], points=[])],
    )
    s = screening("s10", ad.lines, {0: ["15.1.1"], 2: ["15.1", "15.1.1", "15.7"]})
    wording = SuggestedWording(register_id="gbhc-222b3bfc340d", wording=ad.on_screen_text[0])
    s = s.model_copy(update={"flags": (s.flags[0], s.flags[1].model_copy(update={"suggested_wording": wording}))})
    n = near_miss(ad, truth, [s])
    # the authorised line is flagged, a false alarm; the flavour line is not; register wording is offered
    assert (n.caught, n.clean_lines, n.clean_lines_flagged, n.eligible, n.wording) == (True, 2, 1, True, True)
    missed = near_miss(ad, truth, [s.model_copy(update={"flags": (s.flags[0],)})])
    assert (missed.caught, missed.wording) == (False, False)


@pytest.mark.parametrize(
    ("register_id", "fits"),
    [("gbhc-c41b26b64b9c", True), ("gbhc-99fee7203c79", True), ("gbhc-6e9ced5f8edb", True),
     ("gbhc-070dd4b125bd", False)],
)  # fmt: skip
def test_near_miss_takes_the_wording_of_any_substance_the_line_names(register_id, fits):
    # the joint calcium and vitamin D entry, vitamin D's and calcium's fit a line naming both; biotin's does not
    line = "Calcium and vitamin D prevent osteoporosis"
    ad = TeamAd(
        item_id="N99", format="image", product="calcium and vitamin D tablets", register_ids=[],
        on_screen_text=["Lemon flavour", line], voiceover="", base="T99", inserted=line, substance="Calcium",
    )
    truth = GroundTruth(
        item_id="N99", kind="team", label="positive", outcome=None, written_by="w", checked_by="c",
        claims=[BreachingClaim(claim=line, rules=["15.6", "15.6.2"], points=[])],
    )
    s = screening("s11", ad.lines, {1: ["15.6.2"]})
    wording = SuggestedWording(register_id=register_id, wording="w")
    s = s.model_copy(update={"flags": (s.flags[0].model_copy(update={"suggested_wording": wording}),)})
    assert near_miss(ad, truth, [s]).wording is fits


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


@pytest.mark.parametrize(
    ("line", "rules", "unmatched"),
    [
        ("Relieves stiffness", ["15.6.2"], 0),  # a piece of the claim
        ("Relieves soreness, stiffness, and discomfort in days, as thousands of customers say", ["15.6"], 0),
        ("Stiffness", ["15.6.2"], 1),  # one shared word is no quote
        ("Relieves stiffness", ["3.7"], 1),  # the right words under an unrelated rule
    ],
)
def test_a_line_carrying_part_or_all_of_a_claim_is_not_noise(line, rules, unmatched):
    item = score_item(
        truth("A8", [("Relieves soreness, stiffness, and discomfort", ["15.6", "15.6.2"])]),
        [screening("s", [line], {0: rules})],
    )
    assert item.unmatched_lines == unmatched
    # claim recall keeps the tight match: a piece or an over-long quote is not a catch
    assert item.caught == 0


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
    assert exact(0, 10) == (0.0, 0.309)
    assert exact(0, 15) == (0.0, 0.219)
    assert exact(5, 10) == (0.187, 0.813)
    assert exact(25, 25) == (0.862, 1.0)


def test_ad_counts_get_exact_intervals():
    m = by_name()
    assert (m["ad_recall"].low, m["ad_recall"].high) == exact(1, 2)
    assert (m["negative_ads_flagged"].low, m["negative_ads_flagged"].high) == exact(1, 2)


def test_rule_precision_and_recall_get_intervals():
    m = by_name()
    positives = [i for i in TOY if i.label == "positive"]
    rules = interval(positives, lambda i: i.rules_related, lambda i: i.rules_cited)
    assert (m["rule_precision"].low, m["rule_precision"].high) == rules
    assert (m["rule_recall"].low, m["rule_recall"].high) == interval(
        positives, lambda i: i.rules_found, lambda i: i.rules_wanted
    )
    assert rules != interval(positives, lambda i: i.rules_cited, lambda i: i.rules_related)


def test_no_denominator_gives_no_interval():
    unflagged = score_item(truth("A7", [("boosts immunity", ["15.1.1"])]), [screening("s", ["Boosts immunity"], {})])
    m = {x.name: x for x in metrics([unflagged])}
    assert (m["rule_precision"].hits, m["rule_precision"].total, m["rule_precision"].low) == (0, 0, None)


def test_chance_never_exceeds_the_rules_that_fit():
    pack = score._screenable(SNAPSHOTS.cap_rules)
    assert score._chance(len(pack) + 3, ["99.9"], pack) == 0.0
    assert score._chance(len(pack) + 3, ["15.6.2"], pack) == 1.0


def test_judge_only_false_alarms_get_an_exact_interval():
    negatives = {f"T{n}": [screening(f"s{n}", ["Iron contributes"], {})] for n in range(10)}
    _, found = check_recall.scored(negatives, {i: truth(i, []) for i in negatives})
    assert not any(m[0].startswith(("ad_recall", "claim_recall", "rule_")) for m in found)
    assert next(m for m in found if m[0] == "negative_ads_flagged_judge_only") == (
        "negative_ads_flagged_judge_only", 0, 10, 0.0, 0.309,
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


def saved_run(tmp_path, monkeypatch, part="dev"):
    runs, work = tmp_path / "runs.csv", tmp_path / "work"
    monkeypatch.setattr(registry, "RUNS", runs)
    monkeypatch.setattr(run, "RUNS", runs)
    monkeypatch.setattr(run, "RESULTS", tmp_path)
    monkeypatch.setattr(run, "WORK", work)
    monkeypatch.setattr(run, "revision", lambda part: "abc")
    monkeypatch.setattr(run, "kept", lambda t: None)
    truths = {"A24-1": truth("A24-1", [("cures anxiety fast", ["15.6.2"])]), "T16": truth("T16", [])}
    monkeypatch.setattr(run, "load_ground_truth", lambda split, i: truths[i])
    monkeypatch.setattr(run, "load_split", lambda split: SimpleNamespace(dev=["T16", "A24-1"]))
    register({"run_id": "screen-1", "split": "v2", "part": part, "prompt": "judge_v5"}, [("ad_recall", 0, 1)])
    registry.write_rows(tmp_path / "runs" / "screen-1.csv", [{"item_id": i, "media": 1} for i in ("T16", "A24-1")])
    (work / "screen-1").mkdir(parents=True)
    for name, s in [("screen-1-A24-1-reconstruction", screening("a", ["Cures anxiety fast"], {0: ["15.6"]})),
                    ("screen-1-T16-ad", screening("b", ["Tasty"], {}))]:  # fmt: skip
        (work / "screen-1" / f"{name}.json").write_text(s.model_dump_json(), encoding="utf-8")
    return runs, work


def test_rescore_registers_a_saved_run_again(tmp_path, monkeypatch):
    runs, _ = saved_run(tmp_path, monkeypatch)
    run.rescore("screen-1")
    with runs.open(newline="", encoding="utf-8") as f:
        rows = {r["metric"]: r for r in csv.DictReader(f) if r["run_id"].startswith("screen-1-rescored-")}
    ad = rows["ad_recall"]
    assert (ad["hits"], ad["high"], ad["prompt"]) == ("1", "1.0", "judge_v5")
    assert (rows["negative_ads_flagged"]["total"], rows["negative_ads_flagged"]["high"]) == ("1", "0.975")


def test_rescore_refuses_a_run_missing_a_saved_screening(tmp_path, monkeypatch):
    _, work = saved_run(tmp_path, monkeypatch)
    (work / "screen-1" / "screen-1-T16-ad.json").unlink()
    with pytest.raises(SystemExit, match="missing for T16"):
        run.rescore("screen-1")


def test_rescore_refuses_a_test_run(tmp_path, monkeypatch):
    saved_run(tmp_path, monkeypatch, part="test")
    with pytest.raises(SystemExit, match="test run"):
        run.rescore("screen-1")


def test_rescore_refuses_a_void_run(tmp_path, monkeypatch):
    saved_run(tmp_path, monkeypatch)
    (tmp_path / "void.csv").write_text("run_id,reason\nscreen-1,leak\n", encoding="utf-8")
    with pytest.raises(SystemExit, match=r"void \(leak\)"):
        run.rescore("screen-1")


def test_void_runs_are_registered_runs():
    with registry.RUNS.open(newline="", encoding="utf-8") as f:
        registered = {r["run_id"] for r in csv.DictReader(f)}
    assert run.void_runs() and run.void_runs().keys() <= registered


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


def test_citation_spread_counts_the_six_most_cited():
    cited = {f"A25-00000{n}": 8 - n for n in range(1, 8)}  # seven rulings cited 7, 6, ... 1 times
    flags = [
        Flag(flag_id=f"flag-{ruling_id}-{i}", claim_id="claim-0", kind="possible_breach", reason="r",
             sources=(CapRuleRef(rule="15.1"), RulingRef(ruling_id=ruling_id, date="2026-01-01")))
        for ruling_id, times in cited.items() for i in range(times)
    ]  # fmt: skip
    spread = {m.name: m for m in citation_spread([screening("s", ["a claim"], {}).model_copy(update={"flags": flags})])}
    assert spread["precedent_citations_top6"] == Metric("precedent_citations_top6", 27, 28)
    assert spread["precedent_rulings_cited"] == Metric("precedent_rulings_cited", 7, 28)


def test_a_candidate_judge_prompt_reaches_the_screen(tmp_path, monkeypatch):
    asked = {}

    def fake_screen(done, models, precedents, screening_id, **kwargs):
        asked.update(kwargs)
        return screening(screening_id, ["Tasty"], {})

    monkeypatch.setattr(run, "WORK", tmp_path)
    (tmp_path / "screen-1").mkdir()
    monkeypatch.setattr(run, "media", lambda item_id: [Path("ad.png")])
    monkeypatch.setattr(run, "ingest", lambda path: None)
    monkeypatch.setattr(run, "screen", fake_screen)
    monkeypatch.setattr(run, "metered", lambda models: (models, lambda: 0.0))
    run.screen_item(truth("T16", []), None, None, "screen-1", None, "judge_v7")
    assert asked["judge_prompt"] == "judge_v7"
