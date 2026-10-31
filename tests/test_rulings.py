from datetime import date
from pathlib import Path

import pytest

from preflight.sources.rulings import RAW_DIR, in_scope, load_rulings, meta, parse_ruling, topics

# Synthetic pages in the asa.org.uk layout, one per outcome; names and text are invented.
# Real pages stay out of the repo (docs/source-terms.md).
FIXTURES = Path(__file__).parent / "fixtures" / "rulings"


def parse(name: str):
    path = FIXTURES / name
    return parse_ruling(path.read_text(encoding="utf-8"), f"https://www.asa.org.uk/rulings/{name}")


def test_upheld():
    r = parse("fixture-brightleaf-ltd-a26-1000001-fixture-brightleaf-ltd.html")
    assert r.ruling_id == "A26-1000001"
    assert r.advertiser == "Brightleaf Ltd t/a Brightleaf"
    assert r.outcome == "upheld"
    assert r.date == date(2026, 10, 14)
    assert r.media == ["Social media (paid ad)"]
    assert r.cap_rules == ["15.1", "15.1.1", "15.6", "15.6.2"]
    assert r.ad_description == (
        "A paid-for Facebook ad for Brightleaf, a food supplement, seen in May 2026.\n\n"
        "Text stated, “Calms ADHD in kids” and “Clinically proven”."
    )
    assert r.assessment.startswith("1. Upheld")
    assert r.action == "The ad must not appear again in the form investigated."
    assert topics(r) == ["adhd-autism", "children"]
    assert in_scope(r)


def test_not_upheld_without_background():
    r = parse("fixture-oakfield-foods-a25-1000002-fixture-oakfield-foods.html")
    assert r.outcome == "not upheld"
    assert r.background is None
    assert r.cap_rules == ["15.1", "15.1.1", "15.7"]
    assert "Magnesium contributes" in r.ad_description


def test_upheld_in_part_with_bcap_and_two_media():
    r = parse("fixture-fernway-g24-1000003-fixture-fernway.html")
    assert r.ruling_id == "G24-1000003"
    assert r.outcome == "upheld in part"
    assert r.media == ["Television", "Video on demand"]
    assert r.cap_rules == ["15.2"]
    assert r.bcap_rules == ["13.4", "13.4.1"]
    assert r.response is None


def test_ad_description_is_separate_from_assessment():
    for path in FIXTURES.glob("*.html"):
        r = parse(path.name)
        assert r.assessment not in r.ad_description
        assert "Upheld" not in r.ad_description and "upheld" not in r.ad_description


def test_meta_holds_no_ruling_text():
    m = meta(parse("fixture-brightleaf-ltd-a26-1000001-fixture-brightleaf-ltd.html"))
    dumped = m.model_dump_json()
    assert "Calms ADHD" not in dumped and "Clinically proven" not in dumped
    assert m.topics == ["adhd-autism", "children"]


def test_out_of_scope_without_claim_rules_or_supplement():
    page = (FIXTURES / "fixture-fernway-g24-1000003-fixture-fernway.html").read_text(encoding="utf-8")
    page = page.replace("> 15.2</a>", "> 3.1</a>")
    r = parse_ruling(page, "https://www.asa.org.uk/rulings/fixture-fernway-g24-1000003-fixture-fernway.html")
    assert not in_scope(r)


@pytest.mark.skipif(not any(RAW_DIR.glob("*.html")), reason="no cached rulings in data/raw/rulings")
def test_every_cached_page_parses():
    rulings = load_rulings(scope_only=False)
    assert rulings
    assert all(r.ad_description and r.assessment for r in rulings)
