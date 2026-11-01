import argparse
from pathlib import Path

from preflight.agent.draft import digest, load_draft, render_draft
from preflight.agent.publisher import run_publisher
from preflight.agent.tools import Toolbox
from preflight.check.precedents import load_precedents
from preflight.models import from_env
from preflight.pipeline import SNAPSHOTS

WORK = Path("data/work/agent-demo")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--no-align", action="store_true")
    parser.add_argument("--effort", default="low")
    args = parser.parse_args()
    draft = load_draft(args.draft)
    work = WORK / digest(draft)[:12]
    rendered = render_draft(draft, work / "render").media
    models = from_env()
    toolbox = Toolbox(
        models, load_precedents(SNAPSHOTS.rulings), out=work / "tools", align=None if args.no_align else "mms"
    )
    result = run_publisher(
        args.draft.resolve(), rendered.resolve(), models.spark, toolbox, out=work / "transcripts",
        effort=args.effort,
    )
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


if __name__ == "__main__":
    main()
