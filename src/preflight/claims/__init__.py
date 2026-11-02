import json
import re
from pathlib import Path

from preflight.ingest import Ingested
from preflight.models import Spark
from preflight.schema import (
    Claim,
    Evidence,
    OnScreenEvidence,
    OnScreenText,
    RegionEvidence,
    Segment,
    StageRun,
    Track,
    TranscriptEvidence,
)

PROMPTS = Path(__file__).resolve().parents[3] / "prompts"
PROMPT_VERSION = "claims_v3"
# the second pass is shown the first pass's claims and asked for what they missed
MISSED_VERSION = "claims_missed_v1"
EFFORT = "high"


def output_schema(ids: list[str]) -> dict:
    claim = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "kind": {"type": "string", "enum": ["explicit", "implied"]},
            "substance": {"type": ["string", "null"]},
            # an enum keeps the model to evidence the screening holds
            "evidence": {"type": "array", "items": {"type": "string", "enum": ids}},
        },
        "required": ["text", "kind", "substance", "evidence"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"claims": {"type": "array", "items": claim}},
        "required": ["claims"],
        "additionalProperties": False,
    }


def span(start: float, end: float) -> str:
    return f"{start:g}-{end:g} s"


def listing(segments: list[Segment], texts: list[OnScreenText], tracks: list[Track]) -> str:
    out = ["Transcript segments:"]
    out += [f'{s.segment_id} [{span(s.start, s.end)}]: "{s.text}"' for s in segments] or ["none"]
    out += ["", "On-screen text:"]
    out += [f'{t.text_id} [{span(t.start, t.end)}]: "{t.text}"' for t in texts] or ["none"]
    out += ["", "Visual tracks:"]
    out += [
        f"{t.track_id} [{t.prompt}, {span(t.regions[0].frame_time, t.regions[-1].frame_time)}]" for t in tracks
    ] or ["none"]
    return "\n".join(out)


def evidence_by_id(segments: list[Segment], texts: list[OnScreenText], tracks: list[Track]) -> dict[str, Evidence]:
    found: dict[str, Evidence] = {s.segment_id: TranscriptEvidence(segment_id=s.segment_id) for s in segments}
    found |= {t.text_id: OnScreenEvidence(text_id=t.text_id) for t in texts}
    for t in tracks:
        # a track is shown at its cropped frame, the one where it is largest
        shown = next((r for r in t.regions if r.crop), t.regions[0])
        found[t.track_id] = RegionEvidence(track_id=t.track_id, frame_time=shown.frame_time)
    if len(found) != len(segments) + len(texts) + len(tracks):
        raise ValueError("segment, on-screen text and track IDs overlap")
    return found


def parse(answer: dict, evidence: dict[str, Evidence]) -> list[Claim]:
    prepared = []
    substances: dict[tuple, dict[str, str]] = {}
    for item in answer["claims"]:
        text = item["text"].strip()
        if not text:
            raise ValueError("claim extraction returned a claim with no text")
        substance = (item["substance"] or "").strip() or None
        key = (" ".join(re.findall(r"\w+", text.casefold())), item["kind"])
        named = substances.setdefault(key, {})
        if substance:
            named.setdefault(" ".join(substance.casefold().split()), substance)
        prepared.append((key, text, substance, item["evidence"]))

    merged: dict[tuple, dict] = {}
    for key, text, substance, ids in prepared:
        named = substances[key]
        name = " ".join(substance.casefold().split()) if substance else None
        # Enrich a missing substance only when all repeats agree. Different
        # substances, and an ambiguous unnamed claim, retain their own evidence.
        if name is None and len(named) == 1:
            name = next(iter(named))
        entry = merged.setdefault(
            (*key, name), {"text": text, "substance": named[name] if name is not None else None, "ids": []},
        )
        entry["ids"] += [i for i in ids if i not in entry["ids"]]
    return [
        Claim(
            claim_id=f"claim-{n}",
            text=entry["text"],
            kind=kind,
            substance=entry["substance"],
            # a claim citing no evidence fails validation here
            evidence=tuple(evidence[i] for i in entry["ids"]),
        )
        for n, ((_, kind, _substance), entry) in enumerate(merged.items())
    ]


def extract_claims(
    done: Ingested,
    spark: Spark,
    segments: list[Segment],
    texts: list[OnScreenText],
    tracks: list[Track],
    *,
    prompt: str = PROMPT_VERSION,
    effort: str = EFFORT,
    second_pass: bool = False,
) -> tuple[list[Claim], StageRun]:
    evidence = evidence_by_id(segments, texts, tracks)
    if not evidence:
        return [], StageRun(stage="claims", status="skipped")
    text = (PROMPTS / f"{prompt}.txt").read_text(encoding="utf-8") + "\n" + listing(segments, texts, tracks)
    schema = output_schema(list(evidence))
    media = {"video": done.source} if done.ad.media == "video" else {"image": done.frames[0].path.read_bytes()}
    version = f"{prompt}+{MISSED_VERSION}" if second_pass else prompt

    def ask(question: str, prompt_version: str):
        return spark.ask(question, prompt_version=prompt_version, effort=effort, schema=schema, **media)

    # the first call is the single-pass call, so a second-pass run reuses its cached answer
    r = ask(text, prompt)
    found = r.data["claims"]
    if second_pass:
        missed = (PROMPTS / f"{MISSED_VERSION}.txt").read_text(encoding="utf-8")
        shown = "\n".join(json.dumps(c, ensure_ascii=False) for c in found)
        found = found + ask(f"{text}\n\n{missed}\n{shown}", version).data["claims"]
    run = StageRun(stage="claims", status="done", model=r.model, prompt=version, effort=effort)
    return parse({"claims": found}, evidence), run
