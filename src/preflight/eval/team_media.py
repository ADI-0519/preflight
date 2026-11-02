import argparse
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from preflight.eval.reconstruct import IMAGE_MODEL, VOICE, Builder, Scene, ensure_voice, frame, render_scene
from preflight.eval.split import ROOT, RULING_ID, Split, TeamAd, load_split, load_team_ad

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


def selected_items(split: Split, part: str | None, only: list[str] | None) -> list[str]:
    team = [i for i in (getattr(split, part) if part else split.items) if not RULING_ID.match(i)]
    if unknown := set(only or ()) - set(team):
        # checked before any copy is opened, so a mistyped ID never reads an item from the other part
        raise ValueError(f"not a team item of the selected part: {', '.join(sorted(unknown))}")
    return [i for i in team if not only or i in only]


def built(item_id: str) -> bool:
    target = TEAM_DIR / item_id
    return (target / "meta.json").is_file() and any((target / name).is_file() for name in ("ad.png", "ad.mp4"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the team-written items of a split as an image or video ad.")
    parser.add_argument("--split", default="v1")
    parser.add_argument("--part", choices=["dev", "test"], help="render one part only (default: both)")
    parser.add_argument("--only", nargs="+", help="team item IDs within the selected part")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    try:
        items = selected_items(load_split(args.split), args.part, args.only)
    except ValueError as e:
        parser.error(str(e))
    pending = [load_team_ad(i) for i in items if args.rebuild or not built(i)]
    if not pending:
        return
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is not on PATH")
    # the narration voice is a download, needed only for a video with a voiceover
    voiced = any(ad.format == "video" and ad.voiceover.strip() for ad in pending)
    builder = Builder(voice=ensure_voice() if voiced else None)
    for ad in pending:
        print(f"{ad.item_id}: {build_team(ad, builder).name}", flush=True)


if __name__ == "__main__":
    main()
