from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from preflight.check import PROMPT_VERSION, check
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
    return check(screening(texts), spark, FakeIndex()), spark.calls


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
        run({"claim-0": bad, "claim-1": verdict(), "claim-2": verdict()})


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
    check(screening(), spark, FakeIndex(), prompt="judge_v3", per_claim=False)
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
        check(screening(), Uneven({}), FakeIndex())


def test_no_claims_skips_the_model():
    out, calls = run({}, texts=[])
    assert (out.flags, out.stages[-1].status, calls) == ((), "skipped", [])


def test_precedents_must_come_from_the_screenings_snapshot():
    class Other(FakeIndex):
        version = "2026-11-01"

    with pytest.raises(ValueError, match="not the screening's rulings snapshot"):
        check(screening(), FakeSpark({}), Other())
