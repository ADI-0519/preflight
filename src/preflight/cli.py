import argparse
import sys
from pathlib import Path

from preflight.check.precedents import load_precedents
from preflight.ingest import capture, ingest
from preflight.models import from_env
from preflight.pipeline import SNAPSHOTS, default_id, screen
from preflight.report import render_html

OUT_DIR = Path("data/work/screenings")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="preflight")
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("screen", help="screen one ad and write a JSON screening and an HTML report")
    one.add_argument("target", help="a video or image file, or an http(s) URL of a page")
    one.add_argument("--out", type=Path, default=OUT_DIR)
    one.add_argument("--no-align", action="store_true", help="keep each transcription turn's timing")
    args = parser.parse_args(argv)
    try:
        precedents = load_precedents(SNAPSHOTS.rulings)
    except (ValueError, FileNotFoundError):
        print(f"The rulings corpus for {SNAPSHOTS.rulings} is missing from data/raw/; fetch it first.", file=sys.stderr)
        return 2
    try:
        done = capture(args.target) if args.target.startswith(("http://", "https://")) else ingest(Path(args.target))
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        print(e, file=sys.stderr)
        return 2
    screening = screen(
        done, from_env(), precedents, default_id(done), align=None if args.no_align else "mms"
    )
    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.out / screening.screening_id
    stem.with_suffix(".json").write_text(screening.model_dump_json(indent=1), encoding="utf-8")
    crops = done.frames[0].path.parent.parent
    stem.with_suffix(".html").write_text(render_html(screening, crops), encoding="utf-8")
    print(screening.headline)
    print(stem.with_suffix(".json"))
    print(stem.with_suffix(".html"))
    return 1 if any(r.status == "failed" for r in screening.stages) else 0


if __name__ == "__main__":
    raise SystemExit(main())
