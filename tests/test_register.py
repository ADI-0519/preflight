import pytest

from preflight.sources.register import load_register, read_health_claims, read_nutrition_claims

SNAPSHOT = "2026-05-19"


@pytest.fixture(scope="module")
def register():
    return {e.register_id: e for e in load_register(SNAPSHOT)}


# The three entries below were checked by hand against rows 122, 271 and 302 of the
# Health_claims sheet in great-britain-nutrition-and-health-claims-spreadsheet-19-may-2026.xlsx.


def test_magnesium_tiredness(register):
    e = register["gbhc-e1f78000ec6b"]
    assert e.substance == "Magnesium"
    assert e.wording == "Magnesium contributes to a reduction of tiredness and fatigue"
    assert e.wording == e.wording_source
    assert e.status == "authorised"
    assert e.claim_type == "Art.13(1)"
    assert e.efsa_ids == ["244"]


def test_vitamin_d_immune_with_conditions(register):
    e = register["gbhc-8ed4428d48ae"]
    assert e.wording == "Vitamin D contributes to the normal function of the immune system"
    assert e.conditions == (
        "The claim may be used only for food which is at least a source of vitamin D as referred to in the claim "
        "SOURCE OF [NAME OF VITAMIN/S] AND/OR [NAME OF MINERAL/S] as listed in the Annex to Regulation (EC) "
        "No 1924/2006."
    )
    assert e.efsa_ids == ["154", "159"]
    assert e.regulation == "http://eur-lex.europa.eu/LexUriServ/LexUriServ.do?uri=CELEX:32012R0432:EN:NOT"


def test_markup_removed_but_source_kept(register):
    e = register["gbhc-095e95b87c2e"]
    assert e.substance == "Non-digestible carbohydrates"
    assert e.wording == (
        "Consumption of foods/drinks containing <name of all used non-digestible carbohydrates> instead of sugars "
        "induces a lower blood glucose rise after their consumption compared to sugar-containing foods/drinks."
    )
    assert e.wording_source.startswith("<p>Consumption of foods/drinks containing &lt;name of all used")
    assert e.efsa_ids == []
    assert len(e.references) == 3


def test_snapshot_counts(register):
    entries = list(register.values())
    assert len(entries) == 2379
    assert sum(e.status == "authorised" for e in entries) == 297
    assert sum(e.claim_type == "Nutrition claim" for e in entries) == 30
    assert sum(e.proprietary for e in entries) == 6


def test_continuation_rows_and_statuses():
    link = '=HYPERLINK("http://example.org/a.pdf?x=1&amp;y=2","2009;7(9):1")'
    rows = [
        ("Art.13(1)", "Zinc", "Zinc does X", "C", "r", link, "Reg text", "Authorised for use in Great Britain*", 1),
        (None, None, None, None, None, '=HYPERLINK("http://example.org/b.pdf","b")', None, None, None),
        ("Art.13(1)", "Zinc", "Zinc does Y", None, None, None, None, "Non-authorised", "2, 3"),
    ]
    first, second = read_health_claims(rows)
    assert first.references == ["http://example.org/a.pdf?x=1&y=2", "http://example.org/b.pdf"]
    assert first.status == "authorised" and first.proprietary
    assert first.regulation == "Reg text"
    assert second.status == "non_authorised" and second.efsa_ids == ["2", "3"]
    assert first.register_id != second.register_id


def test_unknown_status_is_rejected():
    with pytest.raises(ValueError, match="unknown register status"):
        list(read_health_claims([("Art.13(1)", "Zinc", "Zinc does X", None, None, None, None, "On hold", 1)]))


def test_nutrition_claims_skip_blank_rows():
    entries = list(read_nutrition_claims([("Low fat", "A claim that..."), (None, None)]))
    assert [e.wording for e in entries] == ["Low fat"]
    assert entries[0].register_id.startswith("gbnc-")
