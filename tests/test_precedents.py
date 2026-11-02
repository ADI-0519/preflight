from datetime import date

import pytest

from preflight.check.precedents import PrecedentIndex, eligible
from preflight.eval.split import Split, advertiser_key, load_split
from preflight.sources.rulings import Ruling, load_ruling_index

SPLIT = Split(version="v1", frozen=True, created="2026-10-31", dev=["A26-000001"], test=["G26-000002", "team-01"])
SPLIT_ADVERTISERS = {"A26-000001": "Acme Ltd", "G26-000002": "Borealis plc t/a Calm"}


def ruling(ruling_id: str, advertiser: str, ad: str = "An ad.", assessment: str = "Assessed.") -> Ruling:
    return Ruling(
        ruling_id=ruling_id,
        url=f"https://example.invalid/{ruling_id}",
        date=date(2024, 1, 1),
        advertiser=advertiser,
        media=[],
        outcome="upheld",
        background=None,
        ad_description=ad,
        issue="Issue.",
        response=None,
        assessment=assessment,
        action=None,
        cap_rules=[],
        bcap_rules=[],
    )


def test_index_refuses_a_split_ruling():
    with pytest.raises(ValueError, match="A26-000001"):
        PrecedentIndex([ruling("A26-000001", "Other Ltd")], SPLIT, "2026-11-01", SPLIT_ADVERTISERS)


def test_index_refuses_a_split_advertiser():
    with pytest.raises(ValueError, match="A24-000009"):
        PrecedentIndex([ruling("A24-000009", "Acme Ltd t/a Calm")], SPLIT, "2026-11-01", SPLIT_ADVERTISERS)


def test_index_refuses_when_a_split_ruling_has_no_advertiser():
    with pytest.raises(ValueError, match="G26-000002"):
        PrecedentIndex([ruling("A24-000009", "Other Ltd")], SPLIT, "2026-11-01", {"A26-000001": "Acme Ltd"})


def test_eligible_drops_split_rulings_and_advertisers():
    rulings = [
        ruling("A26-000001", "Acme Ltd"),
        ruling("G26-000002", "Borealis plc t/a Calm"),
        ruling("A24-000009", "ACME Ltd t/a Calm"),
        ruling("A23-000008", "Borealis plc"),
        ruling("A22-000007", "Other Ltd"),
    ]
    assert [r.ruling_id for r in eligible(rulings, SPLIT)] == ["A22-000007"]


def test_eligible_raises_when_a_split_ruling_is_missing():
    with pytest.raises(ValueError, match="G26-000002"):
        eligible([ruling("A26-000001", "Acme Ltd"), ruling("A22-000007", "Other Ltd")], SPLIT)


def test_top_ranks_the_matching_ruling_first_and_drops_zero_scores():
    rulings = [
        ruling("A22-000001", "One Ltd", ad="A gummy for sleep with melatonin", assessment="Sleep claims need wording."),
        ruling("A22-000002", "Two Ltd", ad="A protein bar", assessment="Muscle growth claim."),
        ruling("A22-000003", "Three Ltd", ad="A tea", assessment="Detox claim."),
        ruling("A22-000004", "Four Ltd", ad="A powder", assessment="Energy claim."),
    ]
    index = PrecedentIndex(rulings, SPLIT, "2026-11-01", SPLIT_ADVERTISERS)
    assert [r.ruling_id for r in index.top("melatonin sleep gummy", k=3)] == ["A22-000001"]
    assert index.top("zzzz") == []


# measured on rulings-2026-11-02
ELIGIBLE_ON_2026_11_02_V2 = 34


def test_rulings_2026_11_02_keep_split_v2_out():
    index = load_ruling_index("2026-11-02")
    split = load_split("v2")
    held_back = split.excluded_ruling_ids()
    assert held_back <= {m.ruling_id for m in index}
    kept = eligible(index, split)
    assert len(kept) == ELIGIBLE_ON_2026_11_02_V2
    advertisers = {advertiser_key(m.advertiser) for m in index if m.ruling_id in held_back}
    assert not {m.ruling_id for m in kept} & held_back
    assert not {advertiser_key(m.advertiser) for m in kept} & advertisers
