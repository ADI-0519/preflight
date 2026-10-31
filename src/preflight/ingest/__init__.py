import json
import shutil
import struct
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

from preflight.models.store import digest
from preflight.schema import Ad

# the transcription limit is 10 minutes
MAX_SECONDS = 600
STILL_FORMATS = {"image2", "png_pipe", "jpeg_pipe", "webp_pipe", "gif", "bmp_pipe", "tiff_pipe"}
MANIFEST = "ingest.json"


class Frame(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    time: float
    path: Path


class Ingested(BaseModel):
    model_config = ConfigDict(frozen=True)

    ad: Ad
    source: Path
    audio: Path | None
    video: Path | None
    rate: float | None
    threshold: float
    frames: tuple[Frame, ...]
    keyframes: tuple[int, ...]
    url: str | None = None
    text: Path | None = None


def run(*cmd: str, cwd: Path | None = None) -> str:
    done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(f"{cmd[0]} failed: {done.stderr[-2000:]}")
    return done.stdout


def probe(path: Path) -> dict:
    try:
        info = json.loads(
            run("ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path))
        )
    except RuntimeError as err:
        raise ValueError(f"{path.name} is not a readable media file") from err
    streams = info.get("streams", [])
    # cover art in an audio file is a video stream flagged attached_pic
    pictures = [s for s in streams if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")]
    if not pictures:
        raise ValueError(f"{path.name} has no video stream")
    video = pictures[0]
    duration = float(info["format"].get("duration") or video.get("duration") or 0)
    container = info["format"]["format_name"].split(",")[0]
    still = container in STILL_FORMATS or video.get("nb_frames") == "1" or not duration
    # r_frame_rate overstates variable-rate phone video; ffprobe writes 0/0 when it can't tell
    rate = next((r for r in (video.get("avg_frame_rate"), video.get("r_frame_rate")) if r and r != "0/0"), None)
    if not still and rate is None:
        raise ValueError(f"{path.name} has no frame rate")
    return {
        "still": still,
        "duration": duration,
        "fps": float(Fraction(rate)) if not still else None,
        "audio": any(s["codec_type"] == "audio" for s in streams),
    }


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def scene_scores(path: Path) -> list[float]:
    lines = path.read_text().splitlines()
    return [float(line.split("=")[1]) for line in lines if line.startswith("lavfi.scene_score=")]


def build_video(src: Path, work: Path, info: dict, rate: float, threshold: float) -> tuple[Path | None, list[int]]:
    graph = (
        f"[0:v:0]fps={rate},split=3[png][mp4][scene];"
        "[scene]select='gte(scene,0)',metadata=print:key=lavfi.scene_score:file=scenes.txt[scored]"
    )
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-filter_complex", graph]
    cmd += ["-map", "[png]", "-fps_mode", "passthrough", "frames/%06d.png"]
    cmd += ["-map", "[mp4]", "-fps_mode", "passthrough", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", "frames.mp4"]
    cmd += ["-map", "[scored]", "-f", "null", "-"]
    if info["audio"]:
        cmd += ["-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "audio.wav"]
    run(*cmd, cwd=work)
    scores = scene_scores(work / "scenes.txt")
    (work / "scenes.txt").unlink()
    # keyframes mark shot cuts: a caption change on a still shot scores about 0.03, so on-screen text timing is Spark's
    keyframes = [i for i, score in enumerate(scores) if i == 0 or score >= threshold]
    return (work / "audio.wav" if info["audio"] else None), keyframes


def build(
    src: Path, work: Path, content_hash: str, media: str, info: dict, rate: float, threshold: float
) -> Ingested:
    (work / "frames").mkdir(parents=True)
    if media == "video":
        audio, keyframes = build_video(src, work, info, rate, threshold)
    else:
        run("ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
            "-frames:v", "1", "frames/000000.png", cwd=work)
        audio, keyframes = None, [0]
    paths = sorted((work / "frames").glob("*.png"))
    width, height = png_size(paths[0])
    video = media == "video"
    ad = Ad(
        content_hash=content_hash,
        media=media,
        width=width,
        height=height,
        duration=info["duration"] if video else None,
        fps=info["fps"] if video else None,
    )
    return Ingested(
        ad=ad,
        source=src,
        audio=audio and Path(audio.name),
        video=Path("frames.mp4") if video else None,
        rate=rate if video else None,
        threshold=threshold,
        frames=tuple(
            Frame(index=i, time=i / rate if video else 0.0, path=p.relative_to(work)) for i, p in enumerate(paths)
        ),
        keyframes=tuple(keyframes),
    )


def absolute(done: Ingested, root: Path) -> Ingested:
    return done.model_copy(update={
        "audio": done.audio and root / done.audio,
        "video": done.video and root / done.video,
        "text": done.text and root / done.text,
        "frames": tuple(f.model_copy(update={"path": root / f.path}) for f in done.frames),
    })


def load(directory: Path) -> Ingested:
    done = Ingested.model_validate_json((directory / MANIFEST).read_text())
    return absolute(done, directory)


def ingest(
    path: Path,
    out_root: Path = Path("data/work"),
    *,
    media: Literal["page"] | None = None,
    rate: float = 2.0,
    threshold: float = 0.3,
) -> Ingested:
    return ingest_file(path, out_root, media, rate, threshold)


def ingest_file(
    path: Path, out_root: Path, media: str | None, rate: float, threshold: float, url: str | None = None, text: str = ""
) -> Ingested:
    src = path.resolve()
    content_hash = digest(src)
    out = out_root.resolve() / content_hash
    info = probe(src)
    if info["still"]:
        kind = media or "image"
    elif media:
        raise ValueError("a page screenshot must be a still image")
    elif info["duration"] > MAX_SECONDS:
        raise ValueError(f"{src.name} is {info['duration']:.0f} s long; the limit is {MAX_SECONDS} s")
    else:
        kind = "video"
    if (out / MANIFEST).exists():
        cached = load(out)
        same_video = kind != "video" or (cached.rate, cached.threshold) == (rate, threshold)
        if cached.ad.media == kind and cached.url == url and same_video:
            # the first upload of these bytes may since have been deleted
            return cached if url else cached.model_copy(update={"source": src})
    work = out.with_name(f".tmp-{content_hash}")
    shutil.rmtree(work, ignore_errors=True)
    try:
        done = build(src, work, content_hash, kind, info, rate, threshold)
        if url:
            shutil.copy(src, work / "page.png")
            (work / "page.txt").write_text(text, encoding="utf-8")
            done = done.model_copy(update={"source": out / "page.png", "url": url, "text": Path("page.txt")})
        (work / MANIFEST).write_text(done.model_dump_json(indent=1))
        shutil.rmtree(out, ignore_errors=True)
        work.rename(out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return absolute(done, out)


def capture(url: str, out_root: Path = Path("data/work"), *, width: int = 1280, timeout: float = 30.0) -> Ingested:
    if urlsplit(url).scheme not in ("http", "https"):
        raise ValueError("only http and https URLs can be captured")
    try:
        from playwright.sync_api import TimeoutError as PageTimeout
        from playwright.sync_api import sync_playwright
    except ImportError as err:
        raise RuntimeError(
            "page capture needs the page extra: run `uv sync --extra page` and `uv run playwright install chromium`"
        ) from err
    out_root = out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out_root, prefix=".shot-") as tmp:
        shot = Path(tmp) / "page.png"
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": width, "height": 800})
                response = page.goto(url, wait_until="load", timeout=timeout * 1000)
                # an error page would otherwise be screened as the ad
                if response is None or not response.ok:
                    raise ValueError(f"page returned HTTP {response and response.status}")
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except PageTimeout:
                    pass  # pages that keep polling never go idle; the load event is enough
                shot.write_bytes(page.screenshot(full_page=True))
                text = page.inner_text("body")
            finally:
                browser.close()
        return ingest_file(shot, out_root, "page", 2.0, 0.3, url, text)
