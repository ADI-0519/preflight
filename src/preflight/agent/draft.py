import hashlib
import json
import re
import tempfile
import wave
from pathlib import Path
from typing import Literal, NamedTuple

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from preflight.eval.reconstruct import Scene, card, concat, ensure_voice, frame, render_scene
from preflight.ingest import probe
from preflight.models.store import digest as bytes_digest

LABEL = "PreFlight draft"
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


class DraftScene(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    still: Path | None = None
    on_screen_text: tuple[str, ...] = ()
    voiceover: str = ""
    duration_seconds: float = 4.0


class Draft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    format: Literal["image", "video"]
    scenes: tuple[DraftScene, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _one_image_scene(self):
        if self.format == "image" and len(self.scenes) != 1:
            raise ValueError("an image draft has exactly one scene")
        return self


class Address(NamedTuple):
    scene: int
    kind: Literal["caption", "voiceover"]
    index: int

    def __str__(self) -> str:
        return f"{self.scene}/{self.kind}/{self.index}"

    @classmethod
    def parse(cls, text: str) -> "Address":
        scene, kind, index = text.split("/")
        return cls(int(scene), kind, int(index))


class Rendered(NamedTuple):
    media: Path
    scene_bounds: tuple[tuple[float, float], ...]


def load_draft(path: Path) -> Draft:
    fields = yaml.safe_load(path.read_text(encoding="utf-8"))
    for scene in fields["scenes"]:
        if scene.get("still"):
            scene["still"] = (path.parent / scene["still"]).resolve()
    return Draft.model_validate(fields)


def digest(draft: Draft) -> str:
    fields = draft.model_dump(mode="json")
    for scene in fields["scenes"]:
        scene["still"] = scene["still"] and bytes_digest(Path(scene["still"]))
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def sentences(voiceover: str) -> list[str]:
    return SENTENCE_BREAK.split(voiceover.strip()) if voiceover.strip() else []


def lines(draft: Draft) -> dict[Address, str]:
    found = {}
    for i, scene in enumerate(draft.scenes):
        found |= {Address(i, "caption", j): text for j, text in enumerate(scene.on_screen_text)}
        found |= {Address(i, "voiceover", j): text for j, text in enumerate(sentences(scene.voiceover))}
    return found


def with_line(draft: Draft, address: Address, text: str) -> Draft:
    scene = draft.scenes[address.scene]
    if address.kind == "caption":
        edited = scene.model_copy(update={"on_screen_text": tuple(
            text if j == address.index else t for j, t in enumerate(scene.on_screen_text)
        )})
    else:
        spoken = sentences(scene.voiceover)
        # the stop is punctuation, not wording; it keeps the sentence boundary for the next round
        spoken[address.index] = text if text.endswith((".", "!", "?")) else text + "."
        edited = scene.model_copy(update={"voiceover": " ".join(spoken)})
    return replace_scene(draft, address.scene, edited)


def with_still(draft: Draft, scene: int, still: Path) -> Draft:
    return replace_scene(draft, scene, draft.scenes[scene].model_copy(update={"still": still}))


def replace_scene(draft: Draft, index: int, scene: DraftScene) -> Draft:
    return draft.model_copy(update={"scenes": tuple(scene if i == index else s for i, s in enumerate(draft.scenes))})


def nominal_bounds(draft: Draft) -> tuple[tuple[float, float], ...]:
    bounds, start = [], 0.0
    for scene in draft.scenes:
        bounds.append((start, start + scene.duration_seconds))
        start += scene.duration_seconds
    return tuple(bounds)


def scene_at(draft: Draft, time: float, bounds: tuple[tuple[float, float], ...]) -> int:
    if draft.format == "image":
        return 0
    return next((i for i, (start, end) in enumerate(bounds) if start <= time < end), len(bounds) - 1)


def speak(line: str, voice: Path, path: Path) -> None:
    try:
        from piper import PiperVoice
    except ImportError as e:
        raise RuntimeError("piper is not installed; run `uv sync --extra render`") from e
    with wave.open(str(path), "wb") as f:
        PiperVoice.load(str(voice)).synthesize_wav(line, f)


def render_draft(draft: Draft, out_dir: Path) -> Rendered:
    out_dir.mkdir(parents=True, exist_ok=True)
    video = draft.format == "video"
    voice = ensure_voice() if video and any(s.voiceover.strip() for s in draft.scenes) else None
    clips, bounds, start = [], [], 0.0
    with tempfile.TemporaryDirectory(dir=out_dir) as tmp:
        work = Path(tmp)
        blank = None
        for i, scene in enumerate(draft.scenes):
            audio = None
            if voice and scene.voiceover.strip():
                audio = work / f"scene{i}.wav"
                speak(scene.voiceover, voice, audio)
            shot = Scene(
                duration_seconds=scene.duration_seconds, image_prompt="",
                on_screen_text=list(scene.on_screen_text), voiceover=scene.voiceover,
            )
            if scene.still is None and blank is None:
                blank = work / "card.png"
                card(blank)
            clips.append(render_scene(
                scene.still or blank, shot, audio, work / f"scene{i}.mp4", draft.format, label=LABEL
            ))
            length = probe(clips[-1])["duration"]
            bounds.append((start, start + length))
            start += length
        if video:
            media = out_dir / "draft.mp4"
            concat(clips, media, work)
        else:
            media = out_dir / "draft.png"
            frame(clips[0], media)
    return Rendered(media, tuple(bounds))
