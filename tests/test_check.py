from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from preflight.check import PROMPT_VERSION, asks_quote, check, output_schema
from preflight.models import SparkResult
from preflight.schema import Ad, Claim, Screening, Segment, Snapshots, StageRun, TranscriptEvidence
from preflight.sources.register import load_register
from preflight.sources.rulings import Ruling

REGISTER = {e.register_id: e for e in load_register("2026-05-19")}
TIREDNESS = "gbhc-e1f78000ec6b"
NON_AUTHORISED = "gbhc-7085a3950f8d"
ASHWAGANDHA = "3251"
# outside split v1, in the 2026-10-31 rulings snapshot
RULING = Ruling(
    ruling_id="A25-1317840", url="https://example.org", date=date(2026, 3, 25), advertiser="Example Drinks Ltd",
    media=["Website (own site)"], outcome="upheld", background=None, ad_description="A drink said it calmed nerves.",
    issue="Whether the claims were authorised.", response=None, assessment="Upheld. The claim was not authorised.",
    action=None, cap_rules=["15.1.1"], bcap_rules=[],
)
TEXTS = ["Magnesium for calm and focus", "Ashwagandha for a balanced mind", "Clinically proven"]


class FakeIndex:
    version = "2026-10-31"

    def top(self, query, k=3):
        return [RULING]


class FakeSpark:
    def __init__(self, verdicts):
        self.verdicts, self.calls = verdicts, []

    def ask(self, text, **kwargs):
        self.calls.append((text, kwargs))
        verdicts = [{"claim_id": i, **v} for i, v in self.verdicts.items()]
        return SparkResult("muse-spark-1.3", "", {"verdicts": verdicts}, {})


def verdict(kind="no_issue", rules=(), register=(), on_hold=(), rulings=(), suggested=None, reason="ok"):
    return {
        "verdict": kind, "cap_rules": list(rules), "register_ids": list(register), "on_hold_ids": list(on_hold),
        "ruling_ids": list(rulings), "reason": reason, "suggested_register_id": suggested,
    }


def screening(texts=TEXTS) -> Screening:
    segments = [
        Segment(segment_id=f"segment-{n}", turn=0, text=t, start=n, end=n + 1, timing="word")
        for n, t in enumerate(texts)
    ]
    claims = [
        Claim(
            claim_id=f"claim-{n}", text=t, kind="explicit", substance=t.split()[0].lower() if n < 2 else None,
            evidence=(TranscriptEvidence(segment_id=f"segment-{n}"),),
        )
        for n, t in enumerate(texts)
    ]
    return Screening(
        screening_id="scr-1",
        ad=Ad(content_hash="a" * 64, media="video", width=320, height=180, duration=10.0, fps=25.0),
        snapshots=Snapshots(
            gb_register="2026-05-19", on_hold="2021-01-12", cap_rules="2026-10-31", rulings="2026-10-31"
        ),
        stages=(StageRun(stage="claims", status="done", model="muse-spark-1.3", prompt="claims_v3", effort="high"),),
        screened_at=datetime(2026, 11, 1, tzinfo=UTC),
        segments=segments,
        claims=claims,
    )


def run(verdicts, texts=TEXTS):
    spark = FakeSpark(verdicts)
    # one call, so a broken answer fails the check; a vote is tested below
    return check(screening(texts), spark, FakeIndex(), samples=1), spark.calls


def test_breach_cites_rule_register_and_ruling_with_its_date():
    out, _ = run({
        "claim-0": verdict(
            "possible_breach", ["15.1.1", "15.7"], [NON_AUTHORISED], rulings=["A25-1317840"], reason=" No entry. "
        ),
        "claim-1": verdict(),
        "claim-2": verdict(),
    })
    (flag,) = out.flags
    assert (flag.claim_id, flag.kind, flag.reason) == ("claim-0", "possible_breach", "No entry.")
    assert [s.kind for s in flag.sources] == ["cap_rule", "cap_rule", "register", "ruling"]
    assert flag.sources[-1].date == date(2026, 3, 25)
    assert out.stages[-1] == StageRun(
        stage="check", status="done", model="muse-spark-1.3", prompt=PROMPT_VERSION, effort="high"
    )


# rule 2: the model names an entry; the wording is the register's, copied exactly
def test_suggested_wording_is_the_register_entry_verbatim():
    out, _ = run({
        "claim-0": verdict("possible_breach", ["15.1.1"], [TIREDNESS], suggested=TIREDNESS),
        "claim-1": verdict(),
        "claim-2": verdict(),
    })
    wording = out.flags[0].suggested_wording
    assert (wording.register_id, wording.wording) == (TIREDNESS, REGISTER[TIREDNESS].wording)


def test_section_3_breach_gets_no_wording():
    out, _ = run({
        "claim-0": verdict(),
        "claim-1": verdict(),
        "claim-2": verdict("possible_breach", ["3.7"], suggested=TIREDNESS),
    })
    assert out.flags[0].suggested_wording is None


def test_on_hold_match_is_reported_as_on_hold():
    out, _ = run({"claim-0": verdict(), "claim-1": verdict("on_hold", on_hold=[ASHWAGANDHA]), "claim-2": verdict()})
    (flag,) = out.flags
    assert flag.kind == "on_hold" and flag.sources[0].on_hold_id == ASHWAGANDHA


@pytest.mark.parametrize("bad", [verdict("possible_breach"), verdict("possible_breach", on_hold=[ASHWAGANDHA])])
def test_a_breach_citing_no_breach_source_raises(bad):
    with pytest.raises(ValidationError):
        run({"claim-0": verdict(), "claim-1": bad, "claim-2": verdict()})


def test_schema_asks_for_every_claim_and_only_listed_ids():
    _, ((prompt, kwargs),) = run({f"claim-{n}": verdict() for n in range(3)})
    item = kwargs["schema"]["properties"]["verdicts"]["items"]["properties"]
    assert item["claim_id"]["enum"] == ["claim-0", "claim-1", "claim-2"]
    assert TIREDNESS in item["register_ids"]["items"]["enum"]
    assert ASHWAGANDHA in item["on_hold_ids"]["items"]["enum"]
    assert item["ruling_ids"]["items"]["enum"] == ["A25-1317840"]
    assert None in item["suggested_register_id"]["enum"]
    assert NON_AUTHORISED not in item["suggested_register_id"]["enum"]
    assert '"15.6.2"' not in prompt and "15.6.2:" in prompt
    assert 'claim-2 (explicit, substance: none named; closest past rulings: A25-1317840): "Clinically proven"' in prompt
    assert "A25-1317840 (25 March 2026; CAP rules 15.1.1)" in prompt


def test_claims_follow_the_reference_material_and_precede_the_instructions():
    _, ((prompt, _),) = run({f"claim-{n}": verdict() for n in range(3)})
    order = [prompt.index(s) for s in ("CAP Code rules:", "Register entries:", "Past rulings:", "Transcript segments:",
                                       "Claims:", "Instructions")]
    assert order == sorted(order)


def test_v3_layout_keeps_the_claims_first():
    spark = FakeSpark({f"claim-{n}": verdict() for n in range(3)})
    check(screening(), spark, FakeIndex(), prompt="judge_v3", per_claim=False, samples=1)
    ((prompt, _),) = spark.calls
    assert prompt.index("Claims:") < prompt.index("CAP Code rules:")
    assert 'claim-2 (explicit, substance: none named): "Clinically proven"' in prompt


def test_on_hold_entries_include_their_proposed_wording():
    _, ((prompt, _),) = run({f"claim-{n}": verdict() for n in range(3)})
    assert '3251 [on hold; Ashwagandha root (Withania somnifera); Adaptogenic properties]: "' in prompt


def test_reason_comes_before_the_verdict():
    _, ((_, kwargs),) = run({f"claim-{n}": verdict() for n in range(3)})
    keys = list(kwargs["schema"]["properties"]["verdicts"]["items"]["properties"])
    assert keys.index("reason") < keys.index("verdict")


def test_nothing_to_cite_is_left_out_of_the_schema():
    _, ((prompt, kwargs),) = run({"claim-0": verdict()}, texts=["Clinically proven"])
    item = kwargs["schema"]["properties"]["verdicts"]["items"]["properties"]
    assert "on_hold_ids" not in item and "suggested_register_id" not in item
    assert "On-hold entries:\nnone" in prompt


@pytest.mark.parametrize("given", [["claim-0", "claim-1"], ["claim-0", "claim-1", "claim-1", "claim-2"]])
def test_every_claim_needs_exactly_one_verdict(given):
    class Uneven(FakeSpark):
        def ask(self, text, **kwargs):
            return SparkResult("muse-spark-1.3", "", {"verdicts": [{"claim_id": i, **verdict()} for i in given]}, {})

    with pytest.raises(ValueError, match="not one for each"):
        check(screening(), Uneven({}), FakeIndex(), samples=1)


def test_no_claims_skips_the_model():
    out, calls = run({}, texts=[])
    assert (out.flags, out.stages[-1].status, calls) == ((), "done", [])


def test_precedents_must_come_from_the_screenings_snapshot():
    class Other(FakeIndex):
        version = "2026-11-01"

    with pytest.raises(ValueError, match="not the screening's rulings snapshot"):
        check(screening(), FakeSpark({}), Other())


def test_suggestion_for_another_claims_substance_is_dropped_and_the_flag_kept():
    out, _ = run({
        "claim-0": verdict(),
        "claim-1": verdict("possible_breach", ["15.1.1"], [TIREDNESS], suggested=TIREDNESS),
        "claim-2": verdict(),
    })
    (flag,) = out.flags
    assert flag.suggested_wording is None and [s.kind for s in flag.sources] == ["cap_rule"]


def test_on_hold_citation_for_another_claims_substance_is_dropped():
    out, _ = run({
        "claim-0": verdict("possible_breach", ["15.1.1"], on_hold=[ASHWAGANDHA]),
        "claim-1": verdict(),
        "claim-2": verdict(),
    })
    assert [s.kind for s in out.flags[0].sources] == ["cap_rule"]


def test_flag_left_without_the_source_its_kind_needs_keeps_another_substances_entries():
    out, _ = run({
        "claim-0": verdict("on_hold", ["15.1"], on_hold=[ASHWAGANDHA]),
        "claim-1": verdict("possible_breach", register=[TIREDNESS]),
        "claim-2": verdict(),
    })
    assert [s.model_dump() for f in out.flags for s in f.sources] == [
        {"kind": "cap_rule", "rule": "15.1"}, {"kind": "on_hold", "on_hold_id": ASHWAGANDHA},
        {"kind": "register", "register_id": TIREDNESS},
    ]


def test_claim_naming_no_substance_may_cite_the_ads_entries():
    out, _ = run({
        "claim-0": verdict(),
        "claim-1": verdict(),
        "claim-2": verdict("possible_breach", ["15.1.1"], [TIREDNESS], suggested=TIREDNESS),
    })
    (flag,) = out.flags
    assert flag.suggested_wording.register_id == TIREDNESS
    assert any(getattr(s, "register_id", None) == TIREDNESS for s in flag.sources)


def test_replayed_suggestion_outside_the_authorised_shortlist_is_rejected():
    with pytest.raises(ValueError, match="authorised shortlist"):
        run({
            "claim-0": verdict("possible_breach", ["15.1.1"], suggested=NON_AUTHORISED),
            "claim-1": verdict(),
            "claim-2": verdict(),
        })


def test_no_issue_cannot_silently_discard_sources():
    with pytest.raises(ValueError, match="no_issue"):
        run({"claim-0": verdict(rules=["15.1.1"]), "claim-1": verdict(), "claim-2": verdict()})


@pytest.mark.parametrize("bad", [verdict("unknown"), verdict("possible_breach", ["15.1.1"], reason=" ")])
def test_malformed_verdict_is_rejected(bad):
    with pytest.raises(ValueError):
        run({"claim-0": bad, "claim-1": verdict(), "claim-2": verdict()})


def test_snapshot_rule_outside_the_screenable_candidates_is_rejected():
    with pytest.raises(ValueError, match="CAP"):
        run({"claim-0": verdict("possible_breach", ["1.7"]), "claim-1": verdict(), "claim-2": verdict()})


def test_successful_empty_extraction_finishes_check_without_model_call():
    s = screening([])
    spark = FakeSpark({})
    out = check(s, spark, FakeIndex())
    assert out.stages[-1].status == "done" and spark.calls == []
    assert out.headline.startswith("No issues found")


def test_skipped_extraction_with_no_claims_does_not_read_clean():
    s = screening([]).model_copy(update={"stages": (StageRun(stage="claims", status="skipped"),)})
    out = check(s, FakeSpark({}), FakeIndex())
    assert out.stages[-1].status == "skipped"
    assert out.headline.startswith("Incomplete")


def test_existing_check_is_not_overwritten():
    s, _ = run({f"claim-{n}": verdict() for n in range(3)})
    spark = FakeSpark({})
    with pytest.raises(ValueError, match="already"):
        check(s, spark, FakeIndex())
    assert spark.calls == []


class SampledSpark:
    def __init__(self, samples):
        self.samples, self.calls = samples, []

    def ask(self, text, **kwargs):
        self.calls.append((text, kwargs))
        verdicts = [{"claim_id": i, **v} for i, v in self.samples[kwargs["sample"]].items()]
        return SparkResult("muse-spark-1.3", "", {"verdicts": verdicts}, {})


def vote_on(samples, first_sample=0):
    spark = SampledSpark(samples)
    out = check(screening(), spark, FakeIndex(), samples=3, first_sample=first_sample)
    return out, spark.calls


def breach(*rules, **kw):
    return verdict("possible_breach", rules, **kw)


def test_two_of_three_samples_flag_a_claim_and_one_does_not():
    out, _ = vote_on([
        {"claim-0": breach("15.1.1"), "claim-1": breach("15.7"), "claim-2": verdict()},
        {"claim-0": breach("15.1.1"), "claim-1": verdict(), "claim-2": verdict()},
        {"claim-0": breach("15.1.1"), "claim-1": verdict(), "claim-2": verdict()},
    ])
    (flag,) = out.flags
    assert (flag.claim_id, flag.votes) == ("claim-0", 3)
    assert out.schema_version == "3"


def test_rules_cited_by_two_samples_are_kept():
    out, _ = vote_on([
        {"claim-0": breach("15.1.1", "15.7"), "claim-1": verdict(), "claim-2": verdict()},
        {"claim-0": verdict(), "claim-1": verdict(), "claim-2": verdict()},
        {"claim-0": breach("15.1.1", "3.7"), "claim-1": verdict(), "claim-2": verdict()},
    ])
    (flag,) = out.flags
    assert [s.rule for s in flag.sources if s.kind == "cap_rule"] == ["15.1.1"] and flag.votes == 2


def test_with_no_rule_cited_twice_the_most_cited_is_kept_from_the_reasons_sample():
    out, _ = vote_on([
        {"claim-0": verdict(), "claim-1": verdict(), "claim-2": verdict()},
        {"claim-0": breach("15.7", reason="second"), "claim-1": verdict(), "claim-2": verdict()},
        {"claim-0": breach("3.7", reason="third"), "claim-1": verdict(), "claim-2": verdict()},
    ])
    (flag,) = out.flags
    assert flag.reason == "second" and [s.rule for s in flag.sources if s.kind == "cap_rule"] == ["15.7"]


# rule 2: a vote that leaves only a section 3 rule leaves no wording
def test_wording_goes_when_the_vote_leaves_no_health_rule():
    out, _ = vote_on([
        {"claim-0": breach("15.1.1", "3.7", register=[TIREDNESS], suggested=TIREDNESS), "claim-1": verdict(),
         "claim-2": verdict()},
        {"claim-0": breach("3.7"), "claim-1": verdict(), "claim-2": verdict()},
        {"claim-0": verdict(), "claim-1": verdict(), "claim-2": verdict()},
    ])  # fmt: skip
    assert out.flags[0].suggested_wording is None


def test_a_split_between_on_hold_and_breach_reads_as_a_breach():
    out, _ = vote_on([
        {"claim-0": verdict(), "claim-1": verdict("on_hold", on_hold=[ASHWAGANDHA]), "claim-2": verdict()},
        {"claim-0": verdict(), "claim-1": breach("15.1.1"), "claim-2": verdict()},
        {"claim-0": verdict(), "claim-1": verdict(), "claim-2": verdict()},
    ])
    assert [(f.kind, f.votes) for f in out.flags] == [("possible_breach", 2)]


def test_each_sample_asks_the_same_question_with_its_own_rule_order():
    clean = {"claim-0": verdict(), "claim-1": verdict(), "claim-2": verdict()}
    _, calls = vote_on([clean] * 6, first_sample=3)
    (single_text, single), *_ = run(clean)[1]
    assert sorted(kw["sample"] for _, kw in calls) == [3, 4, 5]
    texts = [text for text, _ in calls]
    assert len(set(texts)) == 3 and single_text not in texts
    assert all(sorted(t.splitlines()) == sorted(single_text.splitlines()) for t in texts)
    assert all(kw["schema"] == single["schema"] for _, kw in calls)


def test_a_single_sample_keeps_the_original_call():
    out, calls = run({"claim-0": breach("15.1.1"), "claim-1": verdict(), "claim-2": verdict()})
    assert [kw["sample"] for _, kw in calls] == [0] and out.flags[0].votes is None


def test_a_sample_that_breaks_the_contract_abstains():
    out, _ = vote_on([
        {"claim-0": breach("15.1.1"), "claim-1": verdict(), "claim-2": verdict()},
        {"claim-0": verdict(rules=["15.1.1"]), "claim-1": verdict(), "claim-2": verdict()},
        {"claim-0": breach("15.1.1"), "claim-1": verdict(), "claim-2": verdict()},
    ])
    assert [(f.claim_id, f.votes) for f in out.flags] == [("claim-0", 2)] and out.stages[-1].samples == 2


def test_two_broken_samples_fail_the_check_rather_than_read_clean():
    broken = {"claim-0": verdict(rules=["15.1.1"]), "claim-1": verdict(), "claim-2": verdict()}
    with pytest.raises(ValueError, match="only 1 of 3"):
        vote_on([broken, {"claim-0": verdict(), "claim-1": verdict(), "claim-2": verdict()}, broken])


def test_the_check_votes_by_default():
    spark = FakeSpark({"claim-0": breach("15.1.1"), "claim-1": verdict(), "claim-2": verdict()})
    out = check(screening(), spark, FakeIndex())
    assert len(spark.calls) == 3 and out.flags[0].votes == 3


def quoted(*quotes, rules=("15.1.1",)):
    return {**breach(*rules), "quotes": list(quotes)}


@pytest.mark.parametrize("quotes, kept", [
    (["calm", "focus"], ("calm", "focus")),
    # the claim's own words are kept when the model changes only case or spacing
    (["Calm  AND focus"], ("calm and focus",)),
    (["calm and sleep", "focus", "focus"], ("focus",)),
    (["Magnesium for calm and focus"], ()),
    ([], ()),
])
def test_a_flag_marks_only_phrases_its_claim_holds(quotes, kept):
    out, _ = run({"claim-0": quoted(*quotes), "claim-1": verdict(), "claim-2": verdict()})
    assert out.flags[0].quotes == kept


def test_only_prompts_that_ask_for_quotes_get_the_field():
    _, ((_, kwargs),) = run({f"claim-{n}": verdict() for n in range(3)})
    assert "quotes" not in kwargs["schema"]["properties"]["verdicts"]["items"]["properties"]
    assert [asks_quote(p) for p in ("judge_v8", "judge_v9", "judge_v10", "judge_v11")] == [False, False, True, False]
    claims, found = list(screening().claims), SimpleNamespace(register=[], on_hold=[])
    item = output_schema(claims, found, [], [], quote=True)["properties"]["verdicts"]["items"]
    assert "quotes" in item["properties"] and "quotes" in item["required"]


def test_the_vote_keeps_the_quotes_of_the_reasons_sample():
    out, _ = vote_on([
        {"claim-0": quoted("calm and focus"), "claim-1": verdict(), "claim-2": verdict()},
        {"claim-0": quoted("focus"), "claim-1": verdict(), "claim-2": verdict()},
        {"claim-0": verdict(), "claim-1": verdict(), "claim-2": verdict()},
    ])
    assert out.flags[0].quotes == ("calm and focus",)


def test_a_saved_quote_missing_from_its_claim_is_rejected():
    out, _ = run({"claim-0": quoted("calm and focus"), "claim-1": verdict(), "claim-2": verdict()})
    saved = out.model_dump(mode="json")
    saved["flags"][0]["quotes"] = ["calm", "calm and sleep"]
    with pytest.raises(ValidationError, match="quotes words missing"):
        Screening.model_validate(saved)
