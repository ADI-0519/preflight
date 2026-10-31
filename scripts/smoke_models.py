# /// script
# requires-python = ">=3.12"
# dependencies = ["openai>=1.60", "httpx", "python-dotenv"]
# ///
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

BASE_URL = "https://api.meta.ai/v1"
OUT = Path("data/raw/smoke")
FONT = "C\\:/Windows/Fonts/arial.ttf"

# fictional brand and claims, written by us for this test
VOICEOVER = (
    "Meet Brightleaf Daily D. Vitamin D contributes to the normal function of the immune system. "
    "Thousands of mums say they feel more energised within a week. "
    "Clinically proven to beat winter tiredness. Brightleaf. Feel brighter every day."
)
OVERLAYS = [
    (0, 10, "Supports your immune system"),
    (10, 20, "Clinically proven*"),
    (20, 30, "Feel brighter in 7 days"),
]


def run(*cmd: str) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def make_media() -> dict[str, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    speech, audio = OUT / "speech.wav", OUT / "ad_audio.wav"
    video, still, bottle = OUT / "ad.mp4", OUT / "ad_frame.png", OUT / "bottle.png"
    run(
        "powershell", "-NoProfile", "-Command",
        "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{speech.resolve()}'); $s.Speak(\"{VOICEOVER}\"); $s.Dispose()",
    )
    # quiet chord under the speech stands in for music
    run(
        "ffmpeg", "-y", "-i", str(speech),
        "-f", "lavfi", "-i", "sine=f=220:d=30", "-f", "lavfi", "-i", "sine=f=277:d=30",
        "-f", "lavfi", "-i", "sine=f=330:d=30",
        "-filter_complex",
        "[1][2][3]amix=inputs=3,volume=0.25[m];[0]apad=whole_dur=30[v];[v][m]amix=inputs=2:duration=first",
        "-t", "30", "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(audio),
    )
    drawtext = ",".join(
        f"drawtext=fontfile='{FONT}':text='{text}':fontsize=64:fontcolor=white:box=1:boxcolor=black@0.5:"
        f"x=(w-text_w)/2:y=h*0.7:enable='between(t,{start},{end})'"
        for start, end, text in OVERLAYS
    )
    disclaimer = (
        f"drawtext=fontfile='{FONT}':text='*survey of 120 customers, 2026':fontsize=22:fontcolor=white:"
        "x=40:y=h-50:enable='between(t,10,20)'"
    )
    run(
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x2e7d32:s=1280x720:r=25:d=30", "-i", str(audio),
        "-vf", f"{drawtext},{disclaimer}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(video),
    )
    run("ffmpeg", "-y", "-ss", "12", "-i", str(video), "-frames:v", "1", str(still))
    return {"audio": audio, "video": video, "still": still, "bottle": bottle}


def data_url(path: Path, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def timed(name: str, results: dict, fn):
    start = time.perf_counter()
    try:
        value = fn()
        results[name] = {"ok": True, "seconds": round(time.perf_counter() - start, 2), **value}
    except Exception as e:
        results[name] = {"ok": False, "seconds": round(time.perf_counter() - start, 2), "error": repr(e)}
    print(name, "ok" if results[name]["ok"] else results[name]["error"], flush=True)


def usage(response) -> dict:
    return response.usage.model_dump() if response.usage else {}


def spark_structured(client: OpenAI) -> dict:
    schema = {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "kind": {"type": "string", "enum": ["health", "nutrition", "other"]},
                    },
                    "required": ["text", "kind"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["claims"],
        "additionalProperties": False,
    }
    r = client.responses.create(
        model="muse-spark-1.3",
        input=f"List every claim in this ad script.\n\n{VOICEOVER}",
        text={"format": {"type": "json_schema", "name": "claims", "schema": schema, "strict": True}},
    )
    return {"model": r.model, "output": json.loads(r.output_text), "usage": usage(r)}


def spark_image(client: OpenAI, still: Path) -> dict:
    r = client.responses.create(
        model="muse-spark-1.3",
        input=[{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "Transcribe all text visible in this image, exactly."},
            {"type": "input_image", "image_url": data_url(still, "image/png")},
        ]}],
    )
    return {"model": r.model, "output": r.output_text, "usage": usage(r)}


def upload(client: OpenAI, path: Path) -> str:
    with path.open("rb") as f:
        return client.files.create(file=f, purpose="user_data").id


def spark_video(client: OpenAI, file_id: str) -> dict:
    r = client.responses.create(
        model="muse-spark-1.3",
        input=[{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": (
                "List each on-screen text with its start and end time in seconds, "
                "then each spoken claim with its approximate time."
            )},
            {"type": "input_file", "file_id": file_id},
        ]}],
    )
    return {"model": r.model, "output": r.output_text, "usage": usage(r)}


def transcribe(key: str, audio: Path) -> dict:
    request = {"mode": "DIARIZATION", "model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV"}
    r = httpx.post(
        f"{BASE_URL}/asr/transcribe",
        headers={"Authorization": f"Bearer {key}"},
        files={
            "request": (None, json.dumps(request), "application/json"),
            "audio": (audio.name, audio.read_bytes(), "audio/wav"),
        },
        timeout=120,
    )
    r.raise_for_status()
    return {"output": r.json()}


def sam(client: OpenAI, prompt: str, media: dict) -> dict:
    lines, first_frame_at, start = [], None, time.perf_counter()
    with client.responses.stream(
        model="sam-3.1",
        input=[{"type": "message", "role": "user", "content": [{"type": "input_text", "text": prompt}, media]}],
        metadata={"include_confidence": "true"},
    ) as stream:
        for event in stream:
            if event.type == "response.output_text.delta":
                first_frame_at = first_frame_at or round(time.perf_counter() - start, 2)
                lines.append(event.delta)
        final = stream.get_final_response()
    # masks are long base85 payloads; keep them on disk, not in the summary
    (OUT / f"sam_{media['type']}.txt").write_text("".join(lines), encoding="utf-8")
    return {"frames": len(lines), "first_frame_seconds": first_frame_at, "sample": [line[:300] for line in lines[:3]],
            "usage": usage(final)}


def image_generate(client: OpenAI, bottle: Path) -> dict:
    r = client.images.generate(
        model="muse-image-1.0",
        prompt="product photo of a vitamin D gummy supplement bottle labelled 'Brightleaf Daily D', white background",
        n=1,
        # webp is the default, and the edit endpoint rejects a webp sent as png
        output_format="png",
    )
    bottle.write_bytes(base64.b64decode(r.data[0].b64_json))
    return {"file": str(bottle)}


def image_edit(client: OpenAI, bottle: Path) -> dict:
    with bottle.open("rb") as f:
        r = client.images.edit(
            model="muse-image-1.0",
            prompt="add the words 'Boosts immunity' to the label, keep everything else the same",
            image=f,
            n=1,
        )
    edited = OUT / "bottle_edit.png"
    edited.write_bytes(base64.b64decode(r.data[0].b64_json))
    return {"file": str(edited)}


def main() -> None:
    media = make_media()
    if "--media-only" in sys.argv:
        return
    load_dotenv()
    key = os.environ["META_API_KEY"]
    client = OpenAI(base_url=BASE_URL, api_key=key)
    results: dict = {}
    timed("models_list", results, lambda: {"ids": sorted(m.id for m in client.models.list())})
    timed("spark_structured", results, lambda: spark_structured(client))
    timed("spark_image", results, lambda: spark_image(client, media["still"]))
    video_id = upload(client, media["video"])
    timed("spark_video", results, lambda: spark_video(client, video_id))
    timed("transcribe", results, lambda: transcribe(key, media["audio"]))
    timed("sam_image", results, lambda: sam(
        client, "text overlay", {"type": "input_image", "image_url": data_url(media["still"], "image/png")}))
    timed("sam_video", results, lambda: sam(client, "text overlay", {"type": "input_video", "file_id": video_id}))
    timed("image_generate", results, lambda: image_generate(client, media["bottle"]))
    if results["image_generate"]["ok"]:
        timed("image_edit", results, lambda: image_edit(client, media["bottle"]))
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
