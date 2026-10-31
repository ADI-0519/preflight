import pytest

from preflight.sources.on_hold import load_on_hold, read_rows

SNAPSHOT = "2021-01-12"


@pytest.fixture(scope="module")
def on_hold():
    return {c.on_hold_id: c for c in load_on_hold(SNAPSHOT)}


# checked by hand against article-13.1-on-hold-health-claims.ods (DHSC, 12 Jan 2021)
def test_reishi_immune(on_hold):
    c = on_hold["3764"]
    assert c.kind == "botanical"
    assert c.substance == "Ganoderma Lucidum (Rheishi)"
    assert c.health_relationship == "Contributes to natural immunological defences"


def test_multiline_wording_kept(on_hold):
    c = on_hold["4112"]
    assert c.proposed_wording == "Reishi mushrooms [Reishi mushroom extracts] \n- may help to support the immune system"


def test_snapshot_counts(on_hold):
    claims = list(on_hold.values())
    assert len(claims) == 2095
    assert sum(c.kind == "botanical" for c in claims) == 2078
    assert on_hold["1488"].kind == "other" and on_hold["1488"].substance == "Caffeine"


def test_rows_before_header_and_blank_rows_skipped():
    rows = [
        ["Notes about the list", None],
        ["Botanical substance", "Health relationship", "Claim wording", "Claim ID"],
        ["Abies pectinata", "lungs", "clearer voice", "3195"],
        [None, None, None, None],
    ]
    (claim,) = read_rows(rows, "botanical")
    assert claim.on_hold_id == "3195" and claim.proposed_wording == "clearer voice"


def test_row_without_claim_id_is_rejected():
    rows = [["Substance", "Relationship", "Wording", "Claim ID"], ["Abies pectinata", "lungs", None, None]]
    with pytest.raises(ValueError, match="without a Claim ID"):
        list(read_rows(rows, "botanical"))


def test_missing_header_is_rejected():
    with pytest.raises(ValueError, match="header row"):
        list(read_rows([["Abies pectinata", "lungs", "x", "3195"]], "botanical"))
