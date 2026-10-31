from preflight.eval.check_reconstructions import carried, check_item, words
from preflight.eval.reconstruct import Scene, ShotList


def shots(*lines: str, voiceover: str = "") -> ShotList:
    return ShotList(
        format="image",
        scenes=[Scene(duration_seconds=4, image_prompt="a jar", on_screen_text=list(lines), voiceover=voiceover)],
    )


def test_words_drop_brand_and_sic_markers():
    assert words("Calms [brand] kids [sic]’s") == ["calms", "kids", "'s"]


def test_claim_carried_exactly_near_or_missing():
    text = words("Calms ADHD in kids. Try [brand] gummies with your breakfast today")
    assert carried("Calms ADHD in kids", text) == "exact"
    assert carried("Try Brightleaf gummies with your breakfast today", text) == "near"
    assert carried("Clinically proven", text) == "missing"


def test_check_item_reports_missing_claims_and_added_lines():
    description = "Text stated, “Calms ADHD in kids” and “Clinically proven”."
    result = check_item(
        "A26-1000001",
        description,
        ["Calms ADHD in kids", "Clinically proven"],
        shots("Calms ADHD in kids", "Doctors love it"),
    )
    assert result["exact"] == 1 and result["missing"] == ["Clinically proven"]
    assert result["added"] == ["Doctors love it"]
    assert result["lines"] == 2
