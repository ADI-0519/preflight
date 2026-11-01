import json
from datetime import date
from functools import cache
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, computed_field, model_validator

from preflight.sources.cap import load_cap_rules
from preflight.sources.on_hold import load_on_hold
from preflight.sources.register import RegisterEntry, load_register
from preflight.sources.rulings import load_ruling_index

SCHEMA_VERSION = "1"

# rules 1 and 4: shown with every screening; no wording here may suggest the ad is cleared to run
NOTICE = (
    "PreFlight screens ads against the dated sources named in this report. It is not legal advice, "
    "and it does not decide whether an ad may run: a person makes that call."
)

WEB_SCHEMA = Path(__file__).resolve().parents[3] / "web" / "schema.json"

# kept to the millisecond so a piece of evidence and the frame it points at compare equal
Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False), AfterValidator(lambda t: round(t, 3))]
SnapshotVersion = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
Pixel = Annotated[int, Field(ge=0)]


def _ordered_box(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    if x0 >= x1 or y0 >= y1:
        raise ValueError(f"box {box} is not (x0, y0, x1, y1) with x0 < x1 and y0 < y1")
    return box


# pixels in the source frame
Box = Annotated[tuple[Pixel, Pixel, Pixel, Pixel], AfterValidator(_ordered_box)]


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", json_schema_serialization_defaults_required=True)

    # pydantic's model_copy skips validation; the fix loop edits screenings this way
    def model_copy(self, *, update=None, deep=False) -> Self:
        return self.model_validate(self.model_dump() | dict(update or {}))


class _Span(_Record):
    start: Seconds
    end: Seconds

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end < self.start:
            raise ValueError(f"span ends ({self.end}) before it starts ({self.start})")
        return self


class Ad(_Record):
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    media: Literal["video", "image", "page"]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    duration: Seconds | None = None
    fps: float | None = Field(default=None, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _timed_if_video(self) -> Self:
        if (self.media == "video") != (self.duration is not None and self.fps is not None):
            raise ValueError("duration and fps are set for video ads and only for them")
        return self


class Segment(_Span):
    segment_id: str
    # index of the transcription turn the segment came from
    turn: int = Field(ge=0)
    text: str
    # "turn" when word alignment failed and the transcription turn's start and end were kept
    timing: Literal["word", "turn"]


class OnScreenText(_Span):
    text_id: str
    text: str
    box: Box | None = None


class Region(_Record):
    frame_time: Seconds
    box: Box
    crop: str | None = None


class Track(_Record):
    track_id: str
    prompt: str
    regions: tuple[Region, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _one_region_per_frame(self) -> Self:
        if len({r.frame_time for r in self.regions}) != len(self.regions):
            raise ValueError(f"track {self.track_id} has two regions at the same frame time")
        return self


class TranscriptEvidence(_Record):
    kind: Literal["transcript"] = "transcript"
    segment_id: str


class OnScreenEvidence(_Record):
    kind: Literal["on_screen"] = "on_screen"
    text_id: str


class RegionEvidence(_Record):
    kind: Literal["region"] = "region"
    track_id: str
    frame_time: Seconds


Evidence = Annotated[TranscriptEvidence | OnScreenEvidence | RegionEvidence, Field(discriminator="kind")]


class RegisterRef(_Record):
    kind: Literal["register"] = "register"
    register_id: str


class OnHoldRef(_Record):
    kind: Literal["on_hold"] = "on_hold"
    on_hold_id: str


class CapRuleRef(_Record):
    kind: Literal["cap_rule"] = "cap_rule"
    rule: str = Field(pattern=r"^\d+(\.\d+)*$")


class RulingRef(_Record):
    kind: Literal["ruling"] = "ruling"
    ruling_id: str
    date: date


SourceRef = Annotated[RegisterRef | OnHoldRef | CapRuleRef | RulingRef, Field(discriminator="kind")]


class SuggestedWording(_Record):
    register_id: str
    wording: str

    # rule 2: built from a register entry; verify_sources checks any that arrive another way
    @classmethod
    def from_entry(cls, entry: RegisterEntry) -> Self:
        if entry.status != "authorised":
            raise ValueError(f"{entry.register_id} is not an authorised register entry")
        return cls(register_id=entry.register_id, wording=entry.wording)


class Claim(_Record):
    claim_id: str
    # as said or shown in the ad
    text: str
    kind: Literal["explicit", "implied"]
    substance: str | None = None
    evidence: tuple[Evidence, ...] = Field(min_length=1)


class Flag(_Record):
    flag_id: str
    # rule 3: the flag shows its claim's evidence, which the claim must have
    claim_id: str
    # on-hold claims may still be used in GB, so a match is reported as on hold (docs/notes/verified-facts.md)
    kind: Literal["possible_breach", "on_hold"]
    reason: str
    # rule 3: every flag cites a source
    sources: tuple[SourceRef, ...] = Field(min_length=1)
    suggested_wording: SuggestedWording | None = None

    @model_validator(mode="after")
    def _sources_fit_kind(self) -> Self:
        on_hold = [s.kind == "on_hold" for s in self.sources]
        if self.kind == "on_hold" and not any(on_hold):
            raise ValueError(f"on-hold flag {self.flag_id} cites no on-hold entry")
        if self.kind == "possible_breach" and all(on_hold):
            raise ValueError(f"flag {self.flag_id} cites only on-hold entries, which are not breach evidence")
        return self


class StageRun(_Record):
    stage: str
    status: Literal["done", "failed", "skipped"]
    model: str | None = None
    prompt: str | None = None
    effort: str | None = None

    @model_validator(mode="after")
    def _standard_mode(self) -> Self:
        # rule 10: never the training-enabled mode
        if self.model is not None and "contributor" in self.model.lower():
            raise ValueError(f"contributor-mode model in stage {self.stage}: {self.model}")
        return self


class Snapshots(_Record):
    gb_register: SnapshotVersion
    on_hold: SnapshotVersion
    cap_rules: SnapshotVersion
    rulings: SnapshotVersion


class Screening(_Record):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    screening_id: str
    # the screening this one re-checks after a fix round
    previous_id: str | None = None
    ad: Ad
    snapshots: Snapshots
    stages: tuple[StageRun, ...] = Field(min_length=1)
    screened_at: AwareDatetime
    segments: tuple[Segment, ...] = ()
    on_screen: tuple[OnScreenText, ...] = ()
    tracks: tuple[Track, ...] = ()
    claims: tuple[Claim, ...] = ()
    flags: tuple[Flag, ...] = ()
    notice: Literal[NOTICE] = NOTICE

    @computed_field
    @property
    def headline(self) -> str:
        s = self.snapshots
        sources = (
            f"the GB register ({s.gb_register}), the on-hold list ({s.on_hold}), "
            f"the CAP Code rule pack ({s.cap_rules}) and the ASA rulings index ({s.rulings})"
        )
        found = None
        if self.flags:
            claims = len({f.claim_id for f in self.flags})
            found = f"{_count(len(self.flags), 'flag')} on {_count(claims, 'claim')}"
        # a failed stage must never read as a clean result
        failed = [r.stage for r in self.stages if r.status == "failed"]
        if failed:
            so_far = f"{found} so far, against {sources}." if found else "No result is given."
            return f"Incomplete: {', '.join(failed)} failed. {so_far}"
        if found:
            return f"{found}, checked against {sources}."
        # rule 1: the clean result names every dated source it was checked against
        return f"No issues found against {sources}."

    # a saved screening carries its headline; it is recomputed on load
    @model_validator(mode="before")
    @classmethod
    def _drop_headline(cls, fields):
        if isinstance(fields, dict):
            fields = {k: v for k, v in fields.items() if k != "headline"}
        return fields

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        _unique("stage", [r.stage for r in self.stages])
        segments = _unique("segment", [s.segment_id for s in self.segments])
        texts = _unique("on-screen text", [t.text_id for t in self.on_screen])
        _unique("track", [t.track_id for t in self.tracks])
        tracks = {t.track_id: {r.frame_time for r in t.regions} for t in self.tracks}
        claims = _unique("claim", [c.claim_id for c in self.claims])
        _unique("flag", [f.flag_id for f in self.flags])
        if self.ad.duration is not None:
            ends = [s.end for s in self.segments + self.on_screen]
            ends += [r.frame_time for t in self.tracks for r in t.regions]
            if any(end > self.ad.duration for end in ends):
                raise ValueError(f"evidence runs past the end of the ad ({self.ad.duration} s)")
        for claim in self.claims:
            for e in claim.evidence:
                found = (
                    (e.kind == "transcript" and e.segment_id in segments)
                    or (e.kind == "on_screen" and e.text_id in texts)
                    or (e.kind == "region" and e.frame_time in tracks.get(e.track_id, ()))
                )
                if not found:
                    raise ValueError(f"claim {claim.claim_id} points at evidence missing from the screening: {e!r}")
        for f in self.flags:
            if f.claim_id not in claims:
                raise ValueError(f"flag {f.flag_id} is on unknown claim {f.claim_id}")
        return self


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _unique(name: str, ids: list[str]) -> set[str]:
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate {name} IDs")
    return set(ids)


@cache
def _register(version: str) -> dict[str, RegisterEntry]:
    return {e.register_id: e for e in load_register(version)}


@cache
def _on_hold_ids(version: str) -> frozenset[str]:
    return frozenset(c.on_hold_id for c in load_on_hold(version))


@cache
def _cap_rules(version: str) -> frozenset[str]:
    return frozenset(load_cap_rules(version).rules)


@cache
def _rulings(version: str) -> dict[str, date]:
    return {m.ruling_id: m.date for m in load_ruling_index(version)}


# rules 2 and 3: run on every screening the checker returns or the API accepts
def verify_sources(screening: Screening) -> None:
    s = screening.snapshots
    register, on_hold, cap_rules = _register(s.gb_register), _on_hold_ids(s.on_hold), _cap_rules(s.cap_rules)
    rulings = _rulings(s.rulings)
    for flag in screening.flags:
        for ref in flag.sources:
            missing = (
                (ref.kind == "register" and ref.register_id not in register)
                or (ref.kind == "on_hold" and ref.on_hold_id not in on_hold)
                or (ref.kind == "cap_rule" and ref.rule not in cap_rules)
                or (ref.kind == "ruling" and rulings.get(ref.ruling_id) != ref.date)
            )
            if missing:
                raise ValueError(f"flag {flag.flag_id} cites a source absent from its snapshot: {ref!r}")
        wording = flag.suggested_wording
        if wording is not None:
            entry = register.get(wording.register_id)
            if entry is None or entry.status != "authorised" or entry.wording != wording.wording:
                raise ValueError(f"flag {flag.flag_id}: suggested wording is not authorised register wording")


def json_schema() -> str:
    return json.dumps(Screening.model_json_schema(mode="serialization"), indent=2, ensure_ascii=False) + "\n"


def write_web_schema(path: Path = WEB_SCHEMA) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_schema(), encoding="utf-8", newline="\n")
