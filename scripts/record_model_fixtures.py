import base64
import json
import subprocess
import sys
from pathlib import Path

from preflight.evidence.on_screen import read_on_screen
from preflight.evidence.regions import find_regions
from preflight.ingest import Frame, Ingested
from preflight.models import Store, from_env
from preflight.models.store import digest
from preflight.pipeline import SNAPSHOTS, screen
from preflight.schema import Ad

FIXTURES = Path("tests/fixtures/models")
MEDIA = FIXTURES / "media"
FONT = "C\\:/Windows/Fonts/arial.ttf"
SPEECH = "Brightleaf Daily D. Vitamin D contributes to the normal function of the immune system."
SCHEMA = {
    "type": "object",
    "properties": {"claims": {"type": "array", "items": {"type": "string"}}},
    "required": ["claims"],
    "additionalProperties": False,
}
PROMPT_VERSION = "fixture-1"


def run(*cmd: str) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def make_media() -> None:
    MEDIA.mkdir(parents=True, exist_ok=True)
    speech = MEDIA / "speech_raw.wav"
    run(
        "powershell", "-NoProfile", "-Command",
        "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{speech.resolve()}'); $s.Speak(\"{SPEECH}\"); $s.Dispose()",
    )
    run("ffmpeg", "-y", "-i", str(speech), "-t", "3", "-ac", "1", "-ar", "16000", "-sample_fmt", "s16",
        str(MEDIA / "speech.wav"))
    speech.unlink()
    overlay = (
        "drawbox=x=40:y=60:w=240:h=60:color=black:t=fill,"
        f"drawtext=fontfile='{FONT}':text='Brightleaf Daily D':fontsize=26:fontcolor=white:x=52:y=78"
    )
    run("ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x2e7d32:s=320x180:r=5:d=3", "-vf", overlay,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(MEDIA / "ad.mp4"))
    run("ffmpeg", "-y", "-i", str(MEDIA / "ad.mp4"), "-frames:v", "1", str(MEDIA / "frame.png"))
    make_boxes()


def make_boxes() -> None:
    # two objects in one frame, to pin how SAM joins them on a line
    boxes = "drawbox=x=20:y=40:w=100:h=60:color=black:t=fill,drawbox=x=180:y=80:w=110:h=70:color=black:t=fill"
    run("ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x2e7d32:s=320x180", "-vf", boxes, "-frames:v", "1",
        str(MEDIA / "boxes.png"))


def caption(text: str, start: float, end: float) -> str:
    return (
        f"drawtext=fontfile='{FONT}':text='{text}':fontsize=18:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=8"
        f":x=(w-text_w)/2:y=60:enable='gte(t,{start})*lt(t,{end})'"
    )


def make_captions() -> None:
    footnote = (
        f"drawtext=fontfile='{FONT}':text='*Vitamin D contributes to the normal function of the immune system'"
        ":fontsize=8:fontcolor=white:x=6:y=165"
    )
    graph = ",".join(
        [caption("Supports your immune system", 1.0, 4.0), caption("Clinically proven formula", 4.0, 7.0), footnote]
    )
    run("ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x2e7d32:s=320x180:r=2:d=8", "-vf", graph,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(MEDIA / "captions.mp4"))


def record_evidence(m) -> None:
    clip = MEDIA / "captions.mp4"
    work = Path("data/work/_captions")
    (work / "frames").mkdir(parents=True, exist_ok=True)
    run("ffmpeg", "-y", "-i", str(clip), "-fps_mode", "passthrough", str(work / "frames" / "%06d.png"))
    frames = tuple(Frame(index=i, time=i / 2, path=p) for i, p in enumerate(sorted((work / "frames").glob("*.png"))))
    ad = Ad(content_hash=digest(clip), media="video", width=320, height=180, duration=8.0, fps=2.0)
    done = Ingested(ad=ad, source=clip, audio=None, video=clip, rate=2.0, threshold=0.3, frames=frames, keyframes=(0,))
    texts, run_spark = read_on_screen(done, m.spark)
    for line in (run_spark, *texts):
        print(line)
    tracks, run_sam = find_regions(done, m.sam)
    print(run_sam)
    for t in tracks:
        print(t.track_id, [(r.frame_time, r.box) for r in t.regions])


class NoPrecedents:
    version = SNAPSHOTS.rulings

    def top(self, query, k=3):
        return []


def record_screen(m) -> None:
    clip = MEDIA / "captions.mp4"
    work = Path("data/work/_screen")
    (work / "frames").mkdir(parents=True, exist_ok=True)
    run("ffmpeg", "-y", "-i", str(clip), "-fps_mode", "passthrough", str(work / "frames" / "%06d.png"))
    frames = tuple(Frame(index=i, time=i / 2, path=p) for i, p in enumerate(sorted((work / "frames").glob("*.png"))))
    ad = Ad(content_hash=digest(clip), media="video", width=320, height=180, duration=8.0, fps=2.0)
    done = Ingested(
        ad=ad, source=clip, audio=MEDIA / "speech.wav", video=clip, rate=2.0, threshold=0.3, frames=frames,
        keyframes=(0,),
    )
    screening = screen(done, m, NoPrecedents(), "fixture", align=None)
    print(screening.headline)
    for c in screening.claims:
        print(c.claim_id, c.kind, c.text)
    for f in screening.flags:
        print(f.flag_id, f.claim_id, f.kind, [r for r in f.sources])


def shrink_image_fixture() -> None:
    # the model returns 1600x1600; the recorded copy is scaled down to keep the repo small
    for path in (FIXTURES / "muse-image-1.0").glob("*.json"):
        entry = json.loads(path.read_text(encoding="utf-8"))
        full, small = MEDIA / "_full.png", MEDIA / "_small.png"
        full.write_bytes(base64.b64decode(entry["response"]["png"]))
        run("ffmpeg", "-y", "-i", str(full), "-vf", "scale=128:128", str(small))
        entry["response"]["png"] = base64.b64encode(small.read_bytes()).decode()
        entry["note"] = "recorded response, with the png scaled down to 128x128"
        path.write_text(json.dumps(entry), encoding="utf-8")
        full.unlink()
        small.unlink()


def main() -> None:
    steps = sys.argv[1:]
    if "media" in steps:
        make_media()
    if "captions" in steps:
        make_captions()
    m = from_env(Store(FIXTURES, "cache"))
    frame, wav, video = (MEDIA / "frame.png").read_bytes(), (MEDIA / "speech.wav").read_bytes(), MEDIA / "ad.mp4"
    if "spark" in steps:
        for r in (
            m.spark.ask(f"List every claim in this script.\n\n{SPEECH}", prompt_version=PROMPT_VERSION, effort="low",
                        schema=SCHEMA),
            m.spark.ask("Transcribe all text visible in this image.", prompt_version=PROMPT_VERSION, effort="low",
                        image=frame),
            m.spark.ask("List each on-screen text with its start and end time in seconds.",
                        prompt_version=PROMPT_VERSION, effort="low", video=video),
        ):
            print(r.text[:200], r.usage)
    if "transcribe" in steps:
        print(m.transcribe.transcribe(wav))
    if "sam" in steps:
        if not (MEDIA / "boxes.png").exists():
            make_boxes()
        boxes = (MEDIA / "boxes.png").read_bytes()
        for r in (
            m.sam.segment("black rectangle", image=frame),
            m.sam.segment("black rectangle", video=video),
            m.sam.segment("black rectangle", image=boxes),
        ):
            print(len(r.frames), [len(f.objects) for f in r.frames], r.usage)
    if "evidence" in steps:
        record_evidence(m)
    if "screen" in steps:
        record_screen(m)
    if "image" in steps:
        m.image.generate("a plain white tub labelled Brightleaf Daily D")
        shrink_image_fixture()
    if "glimmer" in steps and m.glimmer:
        print(m.glimmer.ask("Say hello.", prompt_version=PROMPT_VERSION))


if __name__ == "__main__":
    main()
