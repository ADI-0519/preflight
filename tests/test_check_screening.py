from datetime import UTC, datetime

import pytest

from preflight.check.checker import Precedent, PrecedentIndex
from preflight.check.screening import check_screening
from preflight.eval.split import load_split
from preflight.models import SparkResult
from preflight.schema import Ad, Claim, Screening, Segment, Snapshots, StageRun, TranscriptEvidence
from preflight.sources.rulings import load_ruling_index


class NoFlagSpark:
    def ask(self, *args, **kwargs):
        return SparkResult("muse-spark-1.3", "", {"decisions": []}, {})


def draft():
    return Screening(
        screening_id="synthetic",
        ad=Ad(content_hash="a" * 64, media="image", width=100, height=100),
        snapshots=Snapshots(
            gb_register="2026-05-19", on_hold="2021-01-12", cap_rules="2026-10-31", rulings="2026-10-31"
        ),
        stages=(StageRun(stage="claims", status="done"),),
        screened_at=datetime.now(UTC),
    )


def index():
    excluded = load_split("v1").excluded_ruling_ids()
    ruling = next(r for r in load_ruling_index("2026-10-31") if r.ruling_id not in excluded)
    return PrecedentIndex((Precedent(ruling.ruling_id, ruling.date, ruling.advertiser, (), "example"),))


def test_screening_attaches_check_and_verifies_sources():
    result = check_screening(draft(), NoFlagSpark(), precedents=index())
    assert result.stages[-1].stage == "check"
    assert result.flags == ()


def test_screening_rejects_failed_upstream_stage():
    screening = draft().model_copy(update={"stages": (StageRun(stage="claims", status="failed"),)})
    with pytest.raises(ValueError, match="failed upstream"):
        check_screening(screening, NoFlagSpark(), precedents=index())


def test_screening_flags_claim_with_snapshot_source_and_evidence():
    class BreachSpark:
        def ask(self, *args, **kwargs):
            return SparkResult(
                "muse-spark-1.3",
                "",
                {
                    "decisions": [
                        {
                            "claim_id": "c1",
                            "decision": "possible_breach",
                            "reason": "Needs review against the rule.",
                            "sources": [
                                {
                                    "kind": "cap_rule",
                                    "rule": "15.1.1",
                                    "register_id": None,
                                    "on_hold_id": None,
                                    "ruling_id": None,
                                    "date": None,
                                }
                            ],
                            "register_id": None,
                        }
                    ]
                },
                {},
            )

    screening = draft().model_copy(
        update={
            "segments": (Segment(segment_id="s1", turn=0, start=0, end=0, text="A claim", timing="turn"),),
            "claims": (
                Claim(claim_id="c1", text="A claim", kind="explicit", evidence=(TranscriptEvidence(segment_id="s1"),)),
            ),
        }
    )
    result = check_screening(screening, BreachSpark(), precedents=index())
    assert result.flags[0].sources[0].rule == "15.1.1"
    assert result.claims[0].evidence[0].segment_id == "s1"
