"""Extract ad claims from already-collected evidence.

The model identifies claims and evidence references; it does not create evidence.
All references are checked against the evidence supplied by the caller before a
claim is returned.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from preflight.models import Spark
from preflight.schema import Claim, OnScreenText, RegionEvidence, Segment, StageRun, Track, TranscriptEvidence

PROMPT_VERSION = "claims-2"
EFFORT = "medium"

CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "kind": {"type": "string", "enum": ["explicit", "implied"]},
                    "substance": {"type": ["string", "null"]},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "kind": {"type": "string", "enum": ["transcript", "on_screen", "region"]},
                                "id": {"type": "string"},
                                "frame_time": {"type": ["number", "null"]},
                            },
                            "required": ["kind", "id", "frame_time"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["text", "kind", "substance", "evidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}


class _Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["transcript", "on_screen", "region"]
    id: str
    frame_time: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class _DraftClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    kind: Literal["explicit", "implied"]
    substance: str | None = None
    evidence: list[_Evidence] = Field(min_length=1)


class _Response(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[_DraftClaim]


def _context(segments: list[Segment], on_screen: list[OnScreenText], tracks: list[Track]) -> str:
    prompt = Path(__file__).resolve().parents[3] / "prompts" / "claim_extraction_v2.txt"
    lines = [prompt.read_text(encoding="utf-8"), "\nTRANSCRIPT EVIDENCE:"]
    lines.extend(f"- {s.segment_id} [{s.start:.3f}-{s.end:.3f}s]: {s.text}" for s in segments)
    lines.append("\nON-SCREEN TEXT EVIDENCE:")
    lines.extend(f"- {t.text_id} [{t.start:.3f}-{t.end:.3f}s]: {t.text}" for t in on_screen)
    lines.append("\nVISUAL REGION EVIDENCE:")
    for track in tracks:
        regions = ", ".join(f"{r.frame_time!r}s: {r.box}" for r in track.regions)
        lines.append(f"- {track.track_id} (detection prompt: {track.prompt}); frame times and pixel boxes: {regions}")
    return "\n".join(lines)


def _evidence(
    draft: _DraftClaim,
    segments: dict[str, Segment],
    texts: dict[str, OnScreenText],
    tracks: dict[str, Track],
):
    out = []
    seen = set()
    for ref in draft.evidence:
        if ref.kind == "transcript":
            if ref.id not in segments:
                raise ValueError(f"claim references unknown transcript segment {ref.id!r}")
            if ref.frame_time is not None:
                raise ValueError("transcript evidence cannot contain frame_time")
            value = TranscriptEvidence(segment_id=ref.id)
        elif ref.kind == "on_screen":
            if ref.id not in texts:
                raise ValueError(f"claim references unknown on-screen text {ref.id!r}")
            if ref.frame_time is not None:
                raise ValueError("on-screen evidence cannot contain frame_time")
            from preflight.schema import OnScreenEvidence

            value = OnScreenEvidence(text_id=ref.id)
        else:
            if ref.id not in tracks:
                raise ValueError(f"claim references unknown visual track {ref.id!r}")
            if ref.frame_time is None:
                raise ValueError(f"region evidence {ref.id!r} needs frame_time")
            times = {region.frame_time for region in tracks[ref.id].regions}
            if ref.frame_time not in times:
                raise ValueError(f"claim references frame {ref.frame_time} not present in track {ref.id}")
            value = RegionEvidence(track_id=ref.id, frame_time=ref.frame_time)
        key = value.model_dump_json()
        if key not in seen:
            out.append(value)
            seen.add(key)
    return tuple(out)


def extract_claims(
    segments: list[Segment],
    on_screen: list[OnScreenText],
    tracks: list[Track],
    spark: Spark,
    *,
    image: bytes | None = None,
    image_mime: str = "image/png",
    video: Path | None = None,
) -> tuple[list[Claim], StageRun]:
    """Extract claims from evidence and an optional full-frame image or video.

    Visual references are accepted only for media actually supplied to Spark.
    For a still image only frame-zero regions are available.
    """

    if image is not None and video is not None:
        raise ValueError("provide an image or a video, not both")
    if video is not None:
        visible_tracks = tracks
    elif image is not None:
        visible_tracks = [
            track.model_copy(update={"regions": tuple(r for r in track.regions if r.frame_time == 0)})
            for track in tracks
            if any(r.frame_time == 0 for r in track.regions)
        ]
    else:
        visible_tracks = []
    result = spark.ask(
        _context(segments, on_screen, visible_tracks),
        prompt_version=PROMPT_VERSION,
        effort=EFFORT,
        schema=CLAIM_SCHEMA,
        image=image,
        image_mime=image_mime,
        video=video,
    )
    try:
        response = _Response.model_validate(result.data)
    except ValidationError as error:
        raise ValueError(f"claim extractor returned an invalid response: {error}") from error

    segment_map = {item.segment_id: item for item in segments}
    text_map = {item.text_id: item for item in on_screen}
    track_map = {item.track_id: item for item in visible_tracks}
    claims = []
    seen_claims: set[tuple[str, str, tuple[str, ...]]] = set()
    for index, draft in enumerate(response.claims):
        evidence = _evidence(draft, segment_map, text_map, track_map)
        if not evidence:
            raise ValueError(f"claim {index} has no valid evidence")
        key = (draft.text.strip(), draft.kind, tuple(item.model_dump_json() for item in evidence))
        if key in seen_claims:
            continue
        seen_claims.add(key)
        claims.append(
            Claim(
                claim_id=f"claim-{len(claims)}",
                text=draft.text.strip(),
                kind=draft.kind,
                substance=draft.substance.strip() if draft.substance else None,
                evidence=evidence,
            )
        )
    return claims, StageRun(stage="claims", status="done", model=result.model, prompt=PROMPT_VERSION, effort=EFFORT)
