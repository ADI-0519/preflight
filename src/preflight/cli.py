import argparse
import sys
from pathlib import Path

from preflight.agent import DraftScreener, approve, fix, load_draft, new_fix_id
from preflight.check.precedents import load_precedents
from preflight.ingest import capture, ingest
from preflight.models import from_env
from preflight.pipeline import SNAPSHOTS, default_id, screen
from preflight.report import render_html

OUT_DIR = Path("data/work/screenings")
FIX_DIR = Path("data/work/fixes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="preflight")
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("screen", help="screen one ad and write a JSON screening and an HTML report")
    one.add_argument("target", help="a video or image file, or an http(s) URL of a page")
    one.add_argument("--out", type=Path, default=OUT_DIR)
    one.add_argument("--no-align", action="store_true", help="keep each transcription turn's timing")
    fixing = commands.add_parser("fix", help="screen a draft ad and replace flagged lines with register wording")
    fixing.add_argument("draft", type=Path, help="a draft YAML file: format, scenes, stills")
    fixing.add_argument("--rounds", type=int, default=3)
    fixing.add_argument("--out", type=Path, default=FIX_DIR)
    fixing.add_argument("--no-align", action="store_true", help="keep each transcription turn's timing")
    approval = commands.add_parser("approve", help="record a person's approval of a fix that ended awaiting approval")
    approval.add_argument("log", type=Path)
    approval.add_argument("--by", required=True)
    approval.add_argument("--note", default="")
    args = parser.parse_args(argv)
    if args.command == "approve":
        try:
            approve(args.log, args.by, args.note)
        except (ValueError, FileNotFoundError) as e:
            print(e, file=sys.stderr)
            return 2
        print(f"approved by {args.by.strip()}")
        return 0
    try:
        precedents = load_precedents(SNAPSHOTS.rulings)
    except (ValueError, FileNotFoundError):
        print(f"The rulings corpus for {SNAPSHOTS.rulings} is missing from data/raw/; fetch it first.", file=sys.stderr)
        return 2
    if args.command == "fix":
        return run_fix(args, precedents)
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


def run_fix(args, precedents) -> int:
    try:
        draft = load_draft(args.draft)
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        print(e, file=sys.stderr)
        return 2
    models = from_env()
    work_dir = args.out / new_fix_id(draft)
    screener = DraftScreener(models, precedents, work_dir, align=None if args.no_align else "mms")
    result = fix(
        draft, screen_draft=screener, image=models.image, rounds=args.rounds, log=work_dir / "audit.jsonl",
        work_dir=work_dir,
    )
    print(result.state)
    print(result.screening.headline)
    for group in result.open:
        print(f'- "{group["text"]}": {", ".join(sorted({f["reason"] for f in group["flags"]}))}')
        for f in group["flags"]:
            print(f"    {f['flag_id']} ({f['kind']}): {f['why']}")
    print(result.log)
    return 0 if result.state == "awaiting_approval" else 1


if __name__ == "__main__":
    raise SystemExit(main())
