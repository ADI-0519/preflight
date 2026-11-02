"""Benchmark reconstructions: a ruling's ad description -> shot list -> stills, voiceover -> labelled video.

The builder takes an AdDescription and nothing else (docs/plan.md, evaluation protocol item 3; rule 8).
Outputs go to data/raw/reconstructions/<ruling-id>/ and are never committed.

    uv run --extra render python -m preflight.eval.reconstruct eval/splits/v1.yaml
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "data" / "raw" / "reconstructions"
VOICE_DIR = ROOT / "data" / "raw" / "voices"
PROMPT_VERSION = "reconstruct_shotlist_v1"
PROMPT_PATH = ROOT / "prompts" / f"{PROMPT_VERSION}.txt"

BASE_URL = "https://api.meta.ai/v1"
SHOTLIST_MODEL = "muse-spark-1.3"  # Standard mode (rule 10)
IMAGE_MODEL = "muse-image-1.0"
VOICE = "en_GB-alan-medium"
VOICE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/medium/"

LABEL = "AI reconstruction from ASA ruling text"
# Used when Muse Image refuses a scene's picture. Only the picture changes: the ad's wording is drawn on afterwards.
FALLBACK_STILL = "A plain unbranded supplement pack on a simple tabletop, soft daylight, studio product shot"
WIDTH, HEIGHT = 1280, 720
FONTS = [
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
]

# Published prices (docs/plan.md): Spark per million tokens in and out, Muse Image per image.
SPARK_IN, SPARK_OUT, IMAGE_EACH = 1.25, 4.25, 0.01


class AdDescription(BaseModel):
    """The only input a reconstruction may see: the ruling ID and its "Ad description" section."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ruling_id: str
    text: str = Field(min_length=1)

    @classmethod
    def from_ruling(cls, ruling) -> "AdDescription":
        return cls(ruling_id=ruling.ruling_id, text=ruling.ad_description)


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_seconds: float
    image_prompt: str
    on_screen_text: list[str]
    voiceover: str


class ShotList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["video", "image"]
    scenes: list[Scene]


def shotlist_schema() -> dict:
    scene = {
        "type": "object",
        "properties": {
            "duration_seconds": {"type": "number"},
            "image_prompt": {"type": "string"},
            "on_screen_text": {"type": "array", "items": {"type": "string"}},
            "voiceover": {"type": "string"},
        },
        "required": ["duration_seconds", "image_prompt", "on_screen_text", "voiceover"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "format": {"type": "string", "enum": ["video", "image"]},
            "scenes": {"type": "array", "items": scene},
        },
        "required": ["format", "scenes"],
        "additionalProperties": False,
    }


class Builder:
    def __init__(self, client=None, voice: Path | None = None):
        if client is None:
            from dotenv import load_dotenv
            from openai import OpenAI

            load_dotenv(ROOT / ".env")
            client = OpenAI(base_url=BASE_URL, api_key=os.environ["META_API_KEY"])
        self.client = client
        self.voice = voice
        self.prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def shotlist(self, desc: AdDescription) -> tuple[ShotList, dict]:
        response = self.client.responses.create(
            model=SHOTLIST_MODEL,
            input=self.prompt + desc.text,
            reasoning={"effort": "low"},
            text={"format": {"type": "json_schema", "name": "shotlist", "schema": shotlist_schema(), "strict": True}},
        )
        usage = response.usage.model_dump() if response.usage else {}
        return ShotList.model_validate_json(response.output_text), usage

    def still(self, prompt: str, path: Path) -> bool:
        """Generate one still; returns True if Muse Image refused the prompt and the neutral fallback was used."""
        try:
            self._image(prompt, path)
            return False
        except Exception as e:  # the API answers a refused prompt with a 400 naming its content policy
            if "content management policy" not in str(e):
                raise
            self._image(FALLBACK_STILL, path)
            return True

    def _image(self, prompt: str, path: Path) -> None:
        response = self.client.images.generate(
            model=IMAGE_MODEL,
            prompt=f"{prompt}. Photographic advertising style. No text, letters, labels or logos anywhere.",
            n=1,
            output_format="png",
        )
        path.write_bytes(base64.b64decode(response.data[0].b64_json))

    def speak(self, line: str, path: Path) -> None:
        from piper import PiperVoice

        voice = PiperVoice.load(str(self.voice))
        with wave.open(str(path), "wb") as f:
            voice.synthesize_wav(line, f)

    def build(self, desc: AdDescription, out_dir: Path = OUT_DIR) -> dict:
        if type(desc) is not AdDescription:
            raise TypeError("the builder accepts an AdDescription only")
        target = out_dir / desc.ruling_id
        target.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        shots, usage = self.shotlist(desc)
        (target / "shotlist.json").write_text(shots.model_dump_json(indent=2), encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            clips, fallbacks = [], []
            for i, scene in enumerate(shots.scenes):
                still = target / f"scene{i}.png"
                if self.still(scene.image_prompt, still):
                    fallbacks.append(i)
                audio = None
                if shots.format == "video" and scene.voiceover.strip():
                    audio = work / f"scene{i}.wav"
                    self.speak(scene.voiceover, audio)
                clips.append(render_scene(still, scene, audio, work / f"scene{i}.mp4", shots.format))
            if shots.format == "video":
                concat(clips, target / "reconstruction.mp4", work)
            else:
                frame(clips[0], target / "reconstruction.png")
                for i, clip in enumerate(clips[1:], 1):
                    frame(clip, target / f"reconstruction-{i}.png")
        cost = (usage.get("input_tokens", 0) * SPARK_IN + usage.get("output_tokens", 0) * SPARK_OUT) / 1e6
        cost += IMAGE_EACH * (len(shots.scenes) + len(fallbacks))
        meta = {
            "reconstruction": True,
            "ruling_id": desc.ruling_id,
            "label": LABEL,
            "prompt_version": PROMPT_VERSION,
            "models": {"shotlist": SHOTLIST_MODEL, "image": IMAGE_MODEL, "voice": f"piper:{VOICE}"},
            "format": shots.format,
            "scenes": len(shots.scenes),
            "fallback_stills": fallbacks,  # scenes whose picture is the neutral fallback; their wording is unchanged
            "usage": usage,
            "cost_usd": round(cost, 4),
            "seconds": round(time.monotonic() - started, 1),
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        (target / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return meta


# ffmpeg assembly


def _escape(line: str) -> str:
    return line.replace("\\", "\\\\").replace("'", "\u2019").replace(":", "\\:").replace("%", "\\%")


def _wrap(line: str, width: int = 48) -> list[str]:
    words, rows, row = line.split(), [], ""
    for word in words:
        if row and len(row) + 1 + len(word) > width:
            rows.append(row)
            row = word
        else:
            row = f"{row} {word}".strip()
    return [*rows, row] if row else rows


def _font() -> str:
    """drawtext's fontfile option for the first font found, or nothing to let fontconfig choose."""
    for path in FONTS:
        if path.exists():
            return "fontfile='" + path.as_posix().replace(":", "\\:") + "':"
    return ""


def overlay_filter(on_screen_text: list[str], label: str = LABEL) -> str:
    font = _font()
    # every quoted line must reach the screen, so long text gets a smaller font rather than being cut
    for size in (34, 28, 24, 20, 17, 14):
        rows = [r for line in on_screen_text for r in _wrap(line, width=48 * 34 // size)]
        step = int(size * 1.3)
        if step * len(rows) <= HEIGHT - 120:
            break
    filters = [
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease",
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black",
    ]
    top = max(HEIGHT - 50 - step * len(rows), 60)
    for i, row in enumerate(rows):
        filters.append(
            f"drawtext={font}text='{_escape(row)}':fontsize={size}:fontcolor=white:"
            f"box=1:boxcolor=black@0.6:boxborderw={size // 4}:x=(w-text_w)/2:y={top + step * i}"
        )
    filters.append(
        f"drawtext={font}text='{_escape(label)}':fontsize=22:fontcolor=yellow:"
        "box=1:boxcolor=black@0.7:boxborderw=6:x=20:y=20"
    )
    return ",".join(filters)


def _run(*cmd: str) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def _duration(path: Path) -> float:
    with wave.open(str(path)) as f:
        return f.getnframes() / f.getframerate()


def render_scene(still: Path, scene: Scene, audio: Path | None, out: Path, fmt: str, label: str = LABEL) -> Path:
    seconds = max(scene.duration_seconds, _duration(audio) + 0.5 if audio else 0, 2.0)
    cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{seconds:.2f}", "-i", str(still)]
    cmd += ["-i", str(audio)] if audio else ["-f", "lavfi", "-t", f"{seconds:.2f}", "-i", "anullsrc=r=24000:cl=mono"]
    cmd += ["-vf", overlay_filter(scene.on_screen_text, label), "-r", "25", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-ar", "24000", "-ac", "1", "-af", "apad", "-t", f"{seconds:.2f}", str(out)]
    _run(*cmd)
    return out


def concat(clips: list[Path], out: Path, work: Path) -> None:
    listing = work / "clips.txt"
    listing.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    _run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out))


def card(out: Path) -> None:
    _run("ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x303030:s={WIDTH}x{HEIGHT}", "-frames:v", "1", str(out))


def frame(clip: Path, out: Path) -> None:
    _run("ffmpeg", "-y", "-i", str(clip), "-frames:v", "1", str(out))


# CLI


def ensure_voice() -> Path:
    model = VOICE_DIR / f"{VOICE}.onnx"
    if not model.exists():
        import httpx

        VOICE_DIR.mkdir(parents=True, exist_ok=True)
        for name in (f"{VOICE}.onnx", f"{VOICE}.onnx.json"):
            response = httpx.get(VOICE_URL + name, follow_redirects=True, timeout=300)
            response.raise_for_status()
            (VOICE_DIR / name).write_bytes(response.content)
    return model


def descriptions_for(manifest: Path) -> list[AdDescription]:
    import yaml

    from preflight.sources.rulings import load_rulings

    split = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    wanted = {i for part in ("dev", "test") for i in split[part] if i.startswith(("A", "G"))}
    rulings = {r.ruling_id: r for r in load_rulings(scope_only=False)}
    missing = sorted(wanted - rulings.keys())
    if missing:
        raise SystemExit(f"rulings not in data/raw/rulings: {', '.join(missing)}")
    return [AdDescription.from_ruling(rulings[i]) for i in sorted(wanted)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reconstructions for every ruling item in a split.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--only", nargs="*", help="ruling IDs to build (default: all ruling items)")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is not on PATH")
    builder = Builder(voice=ensure_voice())
    results = []
    for desc in descriptions_for(args.manifest):
        skip = args.only and desc.ruling_id not in args.only
        if (OUT_DIR / desc.ruling_id / "meta.json").exists() and (skip or not args.rebuild):
            results.append(json.loads((OUT_DIR / desc.ruling_id / "meta.json").read_text(encoding="utf-8")))
            continue
        if skip:
            continue
        try:
            meta = builder.build(desc)
            print(f"{desc.ruling_id}: {meta['format']}, {meta['scenes']} scenes, ${meta['cost_usd']}", flush=True)
            results.append(meta)
        except Exception as e:
            print(f"{desc.ruling_id}: FAILED {e!r}", flush=True)
            results.append({"ruling_id": desc.ruling_id, "failed": repr(e)})
    (OUT_DIR / "_build.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    built = [r for r in results if "failed" not in r]
    print(f"{len(built)} built, {len(results) - len(built)} failed, ${sum(r['cost_usd'] for r in built):.2f}")


if __name__ == "__main__":
    main()
