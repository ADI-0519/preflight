import argparse
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from preflight.eval.reconstruct import IMAGE_MODEL, VOICE, Builder, Scene, ensure_voice, frame, render_scene
from preflight.eval.split import ROOT, RULING_ID, TeamAd, load_split, load_team_ad

TEAM_DIR = ROOT / "data" / "raw" / "team"
LABEL = "Team-written test ad"
STILL = "A plain unbranded {product} pack on a simple tabletop, soft daylight, studio product shot"


def build_team(ad: TeamAd, builder: Builder, out_dir: Path = TEAM_DIR) -> Path:
    target = out_dir / ad.item_id
    target.mkdir(parents=True, exist_ok=True)
    still = target / "still.png"
    # the picture carries no wording, so the ad says only the register wording it was written with
    fallback = builder.still(STILL.format(product=ad.product), still)
    scene = Scene(duration_seconds=6, image_prompt="", on_screen_text=ad.on_screen_text, voiceover=ad.voiceover)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        audio = None
        if ad.format == "video" and ad.voiceover.strip():
            audio = work / "voice.wav"
            builder.speak(ad.voiceover, audio)
        clip = render_scene(still, scene, audio, work / "ad.mp4", ad.format, label=LABEL)
        out = target / ("ad.mp4" if ad.format == "video" else "ad.png")
        if ad.format == "video":
            shutil.copy(clip, out)
        else:
            frame(clip, out)
    meta = {
        "item_id": ad.item_id, "label": LABEL, "format": ad.format, "fallback_still": fallback,
        "models": {"image": IMAGE_MODEL, "voice": f"piper:{VOICE}"},
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (target / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the team-written items of a split as an image or video ad.")
    parser.add_argument("--split", default="v1")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is not on PATH")
    builder = Builder(voice=ensure_voice())
    for item_id in (i for i in load_split(args.split).items if not RULING_ID.match(i)):
        if (TEAM_DIR / item_id / "meta.json").exists() and not args.rebuild:
            continue
        print(f"{item_id}: {build_team(load_team_ad(item_id), builder).name}", flush=True)


if __name__ == "__main__":
    main()
