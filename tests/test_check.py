from datetime import date

import pytest

from preflight.check import Precedent, PrecedentIndex, check_claims
from preflight.eval.split import load_split
from preflight.models import SparkResult
from preflight.schema import Claim, TranscriptEvidence
from preflight.sources.cap import load_cap_rules
from preflight.sources.on_hold import load_on_hold
from preflight.sources.register import load_register


class FakeSpark:
    def __init__(self, data):
        self.data = data

    def ask(self, *args, **kwargs):
        return SparkResult("muse-spark-1.3", "ignored", self.data, {})


def claim(text="Magnesium contributes to a reduction of tiredness and fatigue"):
    return Claim(
        claim_id="claim-0",
        text=text,
        kind="explicit",
        substance="Magnesium",
        evidence=(TranscriptEvidence(segment_id="segment-0"),),
    )


def source(**overrides):
    return {
        "kind": "cap_rule",
        "register_id": None,
        "on_hold_id": None,
        "rule": "15.1.1",
        "ruling_id": None,
        "date": None,
        **overrides,
    }


def test_checker_copies_authorised_wording_and_never_model_wording():
    register = load_register("2026-05-19")
    cap = load_cap_rules("2026-10-31")
    result = check_claims(
        [claim("Magnesium supports tiredness")],
        register,
        load_on_hold("2021-01-12"),
        cap,
        FakeSpark(
            {
                "decisions": [
                    {
                        "claim_id": "claim-0",
                        "decision": "possible_breach",
                        "reason": "The wording is not the authorised register wording.",
                        "sources": [source()],
                        "register_id": "gbhc-e1f78000ec6b",
                    }
                ]
            }
        ),
    )
    assert len(result.flags) == 1
    flag = result.flags[0]
    assert flag.suggested_wording.wording == "Magnesium contributes to a reduction of tiredness and fatigue"
    assert flag.suggested_wording.register_id == "gbhc-e1f78000ec6b"
    assert result.stage.prompt == "judge-1"


def test_checker_accepts_clean_claim_without_creating_a_flag():
    result = check_claims(
        [claim()],
        load_register("2026-05-19"),
        load_on_hold("2021-01-12"),
        load_cap_rules("2026-10-31"),
        FakeSpark(
            {
                "decisions": [
                    {
                        "claim_id": "claim-0",
                        "decision": "no_flag",
                        "reason": "The evidence is supported by the supplied candidate.",
                        "sources": [],
                        "register_id": None,
                    }
                ]
            }
        ),
    )
    assert result.flags == ()


def test_checker_rejects_register_wording_outside_shortlist():
    with pytest.raises(ValueError, match="not an authorised candidate"):
        check_claims(
            [claim("Magnesium supports tiredness")],
            load_register("2026-05-19"),
            load_on_hold("2021-01-12"),
            load_cap_rules("2026-10-31"),
            FakeSpark(
                {
                    "decisions": [
                        {
                            "claim_id": "claim-0",
                            "decision": "possible_breach",
                            "reason": "Needs a source-backed review.",
                            "sources": [source()],
                            "register_id": "gbhc-8ed4428d48ae",
                        }
                    ]
                }
            ),
        )


def test_precedent_index_refuses_held_back_rulings_and_searches_allowed_ones():
    allowed = Precedent("A26-1000001", date(2026, 10, 14), "Brightleaf", ("15.1.1",), "calms ADHD in kids")
    held_back = Precedent("A26-1000002", date(2026, 10, 15), "Other", ("15.1.1",), "calms ADHD")
    index = PrecedentIndex((allowed,))
    assert index.search("ADHD") == [allowed]
    with pytest.raises(ValueError, match="held-back"):
        PrecedentIndex((allowed, held_back), excluded_ids=frozenset({held_back.ruling_id}))


def test_precedent_index_loads_frozen_split_without_caller_exclusions():
    held_back = next(iter(load_split("v1").excluded_ruling_ids()))
    with pytest.raises(ValueError, match="held-back"):
        PrecedentIndex((Precedent(held_back, date(2026, 1, 1), "Example", (), "example"),))


def test_precedent_bm25_saturates_frequency_and_rewards_rare_terms():
    repeated = Precedent("repeat", date(2026, 1, 1), "Example", (), "common " * 20)
    specific = Precedent("specific", date(2026, 1, 1), "Example", (), "common rare")
    other = Precedent("other", date(2026, 1, 1), "Example", (), "common filler")
    index = PrecedentIndex((repeated, specific, other))

    assert index.search("common rare") == [specific, repeated, other]
    assert index.search("rare rare") == [specific]


def test_precedent_bm25_normalizes_length_and_preserves_ties_and_limits():
    short = Precedent("short", date(2026, 1, 1), "Example", (), "target")
    long = Precedent("long", date(2026, 2, 1), "Example", (), "target " + "filler " * 30)
    newer = Precedent("newer", date(2026, 3, 1), "Example", (), "target")
    index = PrecedentIndex((short, long, newer))

    assert index.search("TARGET", limit=2) == [newer, short]
    assert index.search("missing") == []
    assert index.search("!!!") == []
    assert index.search("target", limit=0) == []
    assert PrecedentIndex(()).search("target") == []
    assert PrecedentIndex((Precedent("empty", date(2026, 1, 1), "Example", (), ""),)).search("target") == []


def test_needs_review_does_not_become_possible_breach():
    response = {
        "decisions": [
            {
                "claim_id": "claim-0",
                "decision": "needs_review",
                "reason": "Uncertain",
                "sources": [source()],
                "register_id": None,
            }
        ]
    }
    with pytest.raises(ValueError, match="requires human review"):
        check_claims(
            [claim()],
            load_register("2026-05-19"),
            load_on_hold("2021-01-12"),
            load_cap_rules("2026-10-31"),
            FakeSpark(response),
        )
