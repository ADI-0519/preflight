import argparse
import sys
from pathlib import Path

from preflight.agent import approve
from preflight.agent.fix import fix_draft
from preflight.check.precedents import load_precedents
from preflight.models import from_env
from preflight.pipeline import SNAPSHOTS, screen_target

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
    commands.add_parser("mcp", help="serve screen_ad and fix_ad as MCP tools over stdio")
    args = parser.parse_args(argv)
    if args.command == "mcp":
        try:
            from preflight.agent.mcp_server import main as serve
        except ModuleNotFoundError as e:
            if (e.name or "").split(".")[0] != "mcp":
                raise
            print("install the mcp extra: uv sync --extra mcp", file=sys.stderr)
            return 2
        serve()
        return 0
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
    align = None if args.no_align else "mms"
    try:
        screening, json_path, html_path = screen_target(args.target, from_env(), precedents, args.out, align=align)
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        print(e, file=sys.stderr)
        return 2
    print(screening.headline)
    print(json_path)
    print(html_path)
    checked = any(r.stage == "check" and r.status == "done" for r in screening.stages)
    return 1 if not checked or any(r.status == "failed" for r in screening.stages) else 0


def run_fix(args, precedents) -> int:
    try:
        result = fix_draft(
            args.draft, from_env(), precedents, args.out, rounds=args.rounds,
            align=None if args.no_align else "mms",
        )
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        print(e, file=sys.stderr)
        return 2
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
