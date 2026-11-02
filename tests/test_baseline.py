from preflight.eval.baseline import _register, judge, screen_item

REGISTER = "2026-05-19"


def test_authorised_wording_passes_and_other_wording_is_flagged():
    register = _register(REGISTER)
    assert judge("Vitamin C contributes to the normal function of the immune system", register) is None
    rules, why = judge("Vitamin C supercharges your immune system", register)
    assert rules == ["15.1", "15.1.1"] and "authorised" in why
    assert judge("Zesty orange flavour", register) is None


def test_disease_terms_are_flagged_as_whole_words():
    register = _register(REGISTER)
    assert judge("Relieves anxiety fast", register)[0] == ["15.6", "15.6.2"]
    # "pain" inside another word is not the term
    assert judge("Our Spain-grown oranges", register) is None


def test_a_team_ad_is_screened_line_by_line_with_no_model():
    s = screen_item("N01")
    flagged = {c.text for c in s.claims if any(f.claim_id == c.claim_id for f in s.flags)}
    assert "Vitamin C supercharges your immune system" in flagged
    assert "Vitamin C contributes to the normal function of the immune system" not in flagged
    assert all(r.model is None for r in s.stages)
