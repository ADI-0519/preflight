"""Conservative text triage experiment; deliberately not wired into screening."""

import json
import ssl
from dataclasses import dataclass
from pathlib import Path

import httpx
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, StrictBool, ValidationError

from preflight.models import Glimmer
from preflight.models.clients import GLIMMER_BASE_URL
from preflight.schema import Screening

PROMPT_VERSION = "triage_v1"
PROMPTS = Path(__file__).resolve().parents[2] / "prompts"
MODELS = ("meta-models/muse-spark-open-1026", "meta-models/muse-spark-open")


def baseten_client(key: str) -> OpenAI:
    # Use OS trust roots on Windows while retaining certificate/hostname checks.
    return OpenAI(
        base_url=GLIMMER_BASE_URL, api_key=key, max_retries=0,
        http_client=httpx.Client(verify=ssl.create_default_context(), timeout=90),
    )


@dataclass(frozen=True)
class Unit:
    id: str
    screening_id: str
    kind: str
    source_id: str
    text: str
    start: float = 0
    end: float = 0


@dataclass(frozen=True)
class Decision:
    id: str
    needs_review: bool


@dataclass(frozen=True)
class Result:
    decisions: tuple[Decision, ...]
    model: str
    usage: dict
    fallback: bool = False


class _Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    needs_review: StrictBool


class _Response(BaseModel):
    model_config = ConfigDict(extra="forbid")
    units: list[_Decision]


def units(screenings: list[Screening]) -> list[Unit]:
    """Namespace evidence IDs across media and modalities without losing provenance."""
    found = [
        Unit(f"{s.screening_id}/text:{t.text_id}", s.screening_id, "text", t.text_id, t.text, t.start, t.end)
        for s in screenings
        for t in s.on_screen
    ] + [
        Unit(f"{screening.screening_id}/segment:{s.segment_id}",
             screening.screening_id, "segment", s.segment_id, s.text, s.start, s.end)
        for screening in screenings for s in screening.segments
    ]
    if len({u.id for u in found}) != len(found):
        raise ValueError("triage needs unique evidence IDs")
    return found


def request(ad_units: list[Unit]) -> str:
    return (PROMPTS / f"{PROMPT_VERSION}.txt").read_text(encoding="utf-8") + "\n\nAd units:\n" + json.dumps(
        [{"id": u.id, "screening_id": u.screening_id, "kind": u.kind,
          "start": u.start, "end": u.end, "text": u.text} for u in ad_units], ensure_ascii=False,
    )


def classify(client: Glimmer, ad_units: list[Unit]) -> Result:
    """One batch per ad. Invalid output retains every unit, never silently skips it."""
    if client.model not in MODELS:
        raise ValueError("P43 requires a supported Meta open-weights model")
    if len({u.id for u in ad_units}) != len(ad_units):
        raise ValueError("triage needs unique evidence IDs")
    if not ad_units:
        return Result((), client.model, {})
    response = client.ask(request(ad_units), prompt_version=PROMPT_VERSION)
    try:
        parsed = _Response.model_validate_json(response.text)
        by_id = {d.id: d.needs_review for d in parsed.units}
        if len(by_id) != len(parsed.units) or set(by_id) != {u.id for u in ad_units}:
            raise ValueError("triage response must identify every unit exactly once")
    except (ValidationError, ValueError):
        return Result(tuple(Decision(u.id, True) for u in ad_units), response.model, response.usage, True)
    return Result(tuple(Decision(u.id, by_id[u.id]) for u in ad_units), response.model, response.usage)
