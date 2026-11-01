from preflight.check.shortlist import shortlist
from preflight.schema import Claim
from preflight.sources.on_hold import OnHoldClaim, load_on_hold
from preflight.sources.register import RegisterEntry, load_register


def entry(n: int, substance: str, status: str = "authorised") -> RegisterEntry:
    return RegisterEntry(
        register_id=f"gbhc-{n:012d}",
        claim_type="health",
        substance=substance,
        wording=f"{substance} contributes to something.",
        wording_source="invented",
        conditions=None,
        health_relationship=None,
        status=status,
        proprietary=False,
        efsa_ids=[],
        references=[],
        regulation=None,
    )


def claim(text: str = "A claim.", substance: str | None = None) -> Claim:
    return Claim(
        claim_id="c1",
        text=text,
        kind="explicit",
        substance=substance,
        evidence=[{"kind": "transcript", "segment_id": "s1"}],
    )


def held(n: int, substance: str) -> OnHoldClaim:
    return OnHoldClaim(
        on_hold_id=str(n), kind="botanical", substance=substance, health_relationship=None, proposed_wording=None
    )


def substances(entries) -> list[str]:
    return [e.substance for e in entries]


def test_substance_matches_entry_and_compounds():
    register = [entry(1, "Magnesium"), entry(2, "Magnesium hydroxide"), entry(3, "Zinc")]
    got = shortlist([claim(substance="magnesium")], register, [])
    assert substances(got.register) == ["Magnesium", "Magnesium hydroxide"]


def test_entry_name_inside_longer_term():
    register = [entry(1, "Magnesium"), entry(2, "Zinc")]
    got = shortlist([claim(substance="Magnesium citrate")], register, [])
    assert substances(got.register) == ["Magnesium"]


def test_parenthetical_and_alias_match():
    register = [entry(1, "Alpha-linolenic acid (ALA)"), entry(2, "Cobalamin"), entry(3, "Zinc")]
    assert substances(shortlist([claim(substance="ALA")], register, []).register) == ["Alpha-linolenic acid (ALA)"]
    assert substances(shortlist([claim(substance="Vitamin B12")], register, []).register) == ["Cobalamin"]
    register = [entry(1, "Vitamin B12")]
    assert substances(shortlist([claim(substance="cobalamin")], register, []).register) == ["Vitamin B12"]


def test_claim_text_names_a_substance():
    register = [entry(1, "Zinc"), entry(2, "Zinc oxide", "non_authorised"), entry(3, "Iron")]
    got = shortlist([claim(text="Now with zinc for immunity")], register, [])
    assert substances(got.register) == ["Zinc", "Zinc oxide"]


def test_whole_words_only():
    register = [entry(1, "Iron"), entry(2, "Ironwort", "non_authorised")]
    got = shortlist([claim(substance="iron")], register, [])
    assert substances(got.register) == ["Iron"]


def test_caps_keep_every_authorised_entry():
    authorised = [entry(i, f"Zinc form {i}") for i in range(40)]
    others = [entry(100 + i, "Zinc " + "x" * i, "non_authorised") for i in range(45)]
    got = shortlist([claim(substance="zinc")], authorised + others, [])
    assert sum(e.status == "authorised" for e in got.register) == 40
    shortest = {e.register_id for e in sorted(others, key=lambda e: len(e.substance))[:30]}
    assert {e.register_id for e in got.register if e.status == "non_authorised"} == shortest


def test_on_hold_is_capped_per_term():
    got = shortlist([claim(substance="aloe")], [], [held(i, "Aloe " + "x" * i) for i in range(40)])
    assert len(got.on_hold) == 30


def test_on_hold_botanical_found():
    got = shortlist([claim(substance="ashwagandha")], [], load_on_hold("2021-01-12"))
    assert got.on_hold


def test_real_register_keeps_authorised_magnesium():
    register = load_register("2026-05-19")
    got = shortlist([claim(substance="magnesium")], register, [])
    authorised = {e.register_id for e in register if e.status == "authorised" and e.substance == "Magnesium"}
    assert authorised
    assert authorised <= {e.register_id for e in got.register}
