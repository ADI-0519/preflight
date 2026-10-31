import subprocess
import sys
from pathlib import Path

from preflight.models import Store, from_env

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


def main() -> None:
    steps = sys.argv[1:]
    if "media" in steps:
        make_media()
    m = from_env(Store(FIXTURES, "cache"))
    frame, video = (MEDIA / "frame.png").read_bytes(), MEDIA / "ad.mp4"
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


if __name__ == "__main__":
    main()
