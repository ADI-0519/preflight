import argparse
import sys
from pathlib import Path

from preflight.agent.draft import digest, load_draft, render_draft
from preflight.agent.publisher import run_publisher
from preflight.agent.tools import Toolbox
from preflight.check.precedents import load_precedents
from preflight.cli import models_for
from preflight.models.store import CacheMiss
from preflight.pipeline import SNAPSHOTS

WORK = Path("data/work/agent-demo")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--no-align", action="store_true")
    parser.add_argument("--effort", default="low")
    parser.add_argument("--replay", action="store_true", help="answer every model call from the recording or fail")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    draft = load_draft(args.draft)
    work = WORK / digest(draft)[:12]
    rendered = render_draft(draft, work / "render").media
    models = models_for(args)
    toolbox = Toolbox(
        models, load_precedents(SNAPSHOTS.rulings), out=work / "tools", align=None if args.no_align else "mms"
    )
    try:
        result = run_publisher(
            args.draft.resolve(), rendered.resolve(), models.spark, toolbox, out=work / "transcripts",
            effort=args.effort,
        )
    except CacheMiss as e:
        print(f"The recording for this draft is missing, so it cannot be replayed: {e}", file=sys.stderr)
        return 2
    for turn in result["turns"]:
        for call in turn["calls"]:
            print(f"tool call: {call['name']}({call['arguments']})")
    # rules 1 and 4: what PreFlight found is shown from the tool result, apart from the model's own words
    last = next((c["result"] for t in reversed(result["turns"]) for c in reversed(t["calls"])), {})
    for key in ("notice", "headline", "state", "next_step"):
        if key in last:
            print(f"{key}: {last[key]}")
    if "stopped" in result:
        print(f"stopped: {result['stopped']}")
    print("\nThe agent's summary (model text, not a screening result):")
    print(result["final"])
    print(result["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
