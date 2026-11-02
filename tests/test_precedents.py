from datetime import date

import pytest

from preflight.check.precedents import PrecedentIndex, eligible
from preflight.eval.split import RULING_ID, Split, advertiser_key, load_split
from preflight.sources.rulings import Ruling, load_ruling_index

SPLIT = Split(version="v1", frozen=True, created="2026-10-31", dev=["A26-000001"], test=["G26-000002", "team-01"])
SPLIT_ADVERTISERS = {"A26-000001": "Acme Ltd", "G26-000002": "Borealis plc t/a Calm"}


def ruling(
    ruling_id: str, advertiser: str, ad: str = "An ad.", assessment: str = "Assessed.", on: date = date(2024, 1, 1)
) -> Ruling:
    return Ruling(
        ruling_id=ruling_id,
        url=f"https://example.invalid/{ruling_id}",
        date=on,
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


LOO_SPLIT = Split(
    version="v1", frozen=True, created="2026-10-31", dev=["A26-000001", "A26-000003", "team-01"], test=["G26-000002"]
)
LOO_RULINGS = [
    ruling("A26-000001", "Acme Ltd", on=date(2026, 3, 1)),
    ruling("A26-000003", "Delta Ltd", on=date(2025, 6, 1)),
    ruling("G26-000002", "Borealis plc"),
    ruling("A24-000009", "Acme Ltd"),
    ruling("A23-000008", "Borealis plc t/a Calm"),
    ruling("A22-000007", "Other Ltd"),
]


def test_leave_one_out_keeps_the_other_dev_rulings():
    assert [r.ruling_id for r in eligible(LOO_RULINGS, LOO_SPLIT, "A26-000001")] == ["A26-000003", "A22-000007"]
    assert [r.ruling_id for r in eligible(LOO_RULINGS, LOO_SPLIT, "team-01")] == [
        "A26-000001", "A26-000003", "A24-000009", "A22-000007",
    ]  # fmt: skip
    assert [r.ruling_id for r in eligible(LOO_RULINGS, LOO_SPLIT)] == ["A22-000007"]


def test_index_for_an_item_refuses_its_own_ruling_and_advertiser():
    by_id = {r.ruling_id: r for r in LOO_RULINGS}
    advertisers = {i: r.advertiser for i, r in by_id.items()}
    own = by_id["A26-000001"].date
    for refused in ("A26-000001", "A24-000009", "G26-000002", "A23-000008"):
        with pytest.raises(ValueError, match=refused):
            PrecedentIndex([by_id[refused]], LOO_SPLIT, "v", advertisers, item_id="A26-000001", before=own)
    kept = PrecedentIndex([by_id["A26-000003"]], LOO_SPLIT, "v", advertisers, item_id="A26-000001", before=own)
    assert [r.ruling_id for r in kept.rulings] == ["A26-000003"]
    with pytest.raises(ValueError, match="needs the date"):
        PrecedentIndex([by_id["A26-000003"]], LOO_SPLIT, "v", advertisers, item_id="A26-000001")
    assert PrecedentIndex([by_id["A26-000003"]], LOO_SPLIT, "v", advertisers, item_id="team-01").rulings


def test_an_item_sees_only_rulings_published_before_its_own():
    sweep = [*LOO_RULINGS, ruling("A26-000004", "Echo Ltd", on=date(2026, 3, 1))]
    # A26-000004 came out the same day as A26-000001, so it is a sibling, not a precedent
    assert [r.ruling_id for r in eligible(sweep, LOO_SPLIT, "A26-000001")] == ["A26-000003", "A22-000007"]
    assert "A26-000001" not in {r.ruling_id for r in eligible(sweep, LOO_SPLIT, "A26-000003")}
    advertisers = {r.ruling_id: r.advertiser for r in sweep}
    with pytest.raises(ValueError, match="A26-000004"):
        PrecedentIndex([sweep[-1]], LOO_SPLIT, "v", advertisers, item_id="A26-000001", before=date(2026, 3, 1))


# measured on rulings-2026-11-02: the strict index for the product, and the per-item range for evaluation runs
ELIGIBLE_ON_2026_11_02_V2 = 34
ELIGIBLE_PER_ITEM_ON_2026_11_02_V2 = (32, 57)


def test_rulings_2026_11_02_keep_split_v2_out():
    index = load_ruling_index("2026-11-02")
    split = load_split("v2")
    assert split.excluded_ruling_ids() <= {m.ruling_id for m in index}
    advertiser = {m.ruling_id: advertiser_key(m.advertiser) for m in index}
    test = {i for i in split.test if RULING_ID.match(i)}
    assert len(eligible(index, split)) == ELIGIBLE_ON_2026_11_02_V2
    sizes = []
    for item_id in split.items:
        barred = test | ({item_id} if RULING_ID.match(item_id) else set())
        kept = eligible(index, split, item_id)
        sizes.append(len(kept))
        assert not {m.ruling_id for m in kept} & barred
        assert not {advertiser[m.ruling_id] for m in kept} & {advertiser[i] for i in barred}
        own = next((m.date for m in index if m.ruling_id == item_id), None)
        assert own is None or all(m.date < own for m in kept)
    assert (min(sizes), max(sizes)) == ELIGIBLE_PER_ITEM_ON_2026_11_02_V2
