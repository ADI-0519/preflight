"""Attach checker results to a screening and verify their declared provenance."""

from preflight.check.checker import PrecedentIndex, check_claims
from preflight.models import Spark
from preflight.schema import Screening, verify_sources
from preflight.sources.cap import load_cap_rules
from preflight.sources.on_hold import load_on_hold
from preflight.sources.register import load_register
from preflight.sources.rulings import load_ruling_index


def check_screening(screening: Screening, spark: Spark, *, precedents: PrecedentIndex) -> Screening:
    """Check a prepared screening using exactly the source snapshots it names.

    This does not run ingestion or claim extraction. Callers must provide the
    completed upstream stages and handle failures as incomplete screenings.
    """
    if any(stage.stage == "check" for stage in screening.stages):
        raise ValueError("screening already contains a check stage")
    if screening.flags:
        raise ValueError("screening already contains flags")
    if any(stage.status == "failed" for stage in screening.stages):
        raise ValueError("cannot check a screening with failed upstream stages")
    if not any(stage.stage == "claims" and stage.status == "done" for stage in screening.stages):
        raise ValueError("claim extraction must complete before checking")
    snapshots = screening.snapshots
    if not precedents.records:
        raise ValueError("a nonempty precedent index is required to check against rulings")
    ruling_dates = {r.ruling_id: r.date for r in load_ruling_index(snapshots.rulings)}
    for record in precedents.records:
        if ruling_dates.get(record.ruling_id) != record.date:
            raise ValueError(f"precedent {record.ruling_id} is absent from the declared rulings snapshot")
    result = check_claims(
        list(screening.claims),
        load_register(snapshots.gb_register),
        load_on_hold(snapshots.on_hold),
        load_cap_rules(snapshots.cap_rules),
        spark,
        precedents=precedents,
    )
    checked = screening.model_copy(update={"flags": result.flags, "stages": (*screening.stages, result.stage)})
    verify_sources(checked)
    return checked
