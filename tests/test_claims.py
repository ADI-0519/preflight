from pathlib import Path

import pytest

from preflight.claims import CLAIM_SCHEMA, extract_claims
from preflight.models import SparkResult
from preflight.schema import OnScreenText, Region, Segment, Track


class FakeSpark:
    def __init__(self, data):
        self.data = data

    def ask(self, *args, **kwargs):
        return SparkResult("muse-spark-1.3", "ignored", self.data, {})


def evidence():
    segments = [Segment(segment_id="segment-0", turn=0, start=0, end=2, text="Magnesium helps.", timing="word")]
    texts = [OnScreenText(text_id="text-0", start=1, end=3, text="Supports normal energy", box=None)]
    tracks = [Track(track_id="label-1", prompt="label", regions=[Region(frame_time=1.0, box=(0, 0, 10, 10))])]
    return segments, texts, tracks


def test_extract_claims_validates_references_and_assigns_stable_ids():
    segments, texts, tracks = evidence()
    claims, stage = extract_claims(
        segments,
        texts,
        tracks,
        FakeSpark(
            {
                "claims": [
                    {
                        "text": "Magnesium helps.",
                        "kind": "explicit",
                        "substance": "Magnesium",
                        "evidence": [{"kind": "transcript", "id": "segment-0"}],
                    },
                    {
                        "text": "Supports normal energy",
                        "kind": "explicit",
                        "substance": None,
                        "evidence": [{"kind": "on_screen", "id": "text-0"}],
                    },
                    {
                        "text": "The label implies a premium product.",
                        "kind": "implied",
                        "substance": None,
                        "evidence": [{"kind": "region", "id": "label-1", "frame_time": 1.0}],
                    },
                ]
            }
        ),
        video=Path("synthetic-video.mp4"),
    )
    assert [claim.claim_id for claim in claims] == ["claim-0", "claim-1", "claim-2"]
    assert claims[2].evidence[0].kind == "region"
    assert stage.prompt == "claims-2"


@pytest.mark.parametrize(
    "reference",
    [
        {"kind": "transcript", "id": "missing"},
        {"kind": "on_screen", "id": "missing"},
        {"kind": "region", "id": "label-1", "frame_time": 2.0},
    ],
)
def test_extract_claims_rejects_unknown_evidence(reference):
    segments, texts, tracks = evidence()
    with pytest.raises(ValueError, match="claim references"):
        extract_claims(
            segments,
            texts,
            tracks,
            FakeSpark(
                {
                    "claims": [
                        {
                            "text": "A claim",
                            "kind": "explicit",
                            "substance": None,
                            "evidence": [reference],
                        }
                    ]
                }
            ),
            video=Path("synthetic-video.mp4"),
        )


def test_extract_claims_deduplicates_identical_claim_evidence():
    segments, texts, tracks = evidence()
    claim = {
        "text": "Magnesium helps.",
        "kind": "explicit",
        "substance": "Magnesium",
        "evidence": [{"kind": "transcript", "id": "segment-0"}],
    }
    claims, _ = extract_claims(segments, texts, tracks, FakeSpark({"claims": [claim, claim]}))
    assert len(claims) == 1


def test_schema_requires_all_properties_for_strict_structured_output():
    def check(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert set(node["properties"]) == set(node["required"])
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(CLAIM_SCHEMA)


def test_visual_reference_requires_image():
    segments, texts, tracks = evidence()
    data = {
        "claims": [
            {
                "text": "Visual claim",
                "kind": "implied",
                "substance": None,
                "evidence": [{"kind": "region", "id": "label-1", "frame_time": 1.0}],
            }
        ]
    }
    with pytest.raises(ValueError, match="unknown visual track"):
        extract_claims(segments, texts, tracks, FakeSpark(data))


def test_still_image_cannot_cite_other_video_frames():
    segments, texts, tracks = evidence()
    data = {
        "claims": [
            {
                "text": "Visual claim",
                "kind": "implied",
                "substance": None,
                "evidence": [{"kind": "region", "id": "label-1", "frame_time": 1.0}],
            }
        ]
    }
    with pytest.raises(ValueError, match="unknown visual track"):
        extract_claims(segments, texts, tracks, FakeSpark(data), image=b"synthetic-image")


def test_image_and_video_are_mutually_exclusive():
    segments, texts, tracks = evidence()
    with pytest.raises(ValueError, match="image or a video"):
        extract_claims(segments, texts, tracks, FakeSpark({}), image=b"x", video=Path("ad.mp4"))
