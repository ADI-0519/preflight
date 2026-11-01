import json
from datetime import UTC, datetime
from pathlib import Path

from preflight.agent.tools import TOOLS, Toolbox
from preflight.claims import PROMPTS
from preflight.models import Spark

PROMPT_VERSION = "publisher_v1"
INSTRUCTIONS = (PROMPTS / f"{PROMPT_VERSION}.txt").read_text(encoding="utf-8")
# ids and paths carry the time of the run, so sending them back would change every later turn's cache key
UNSENT = ("screening_id", "report", "json", "log")
# a screen, a fix and a summary, with room for one retry of each tool
MAX_TURNS = 6


def run_tool(toolbox: Toolbox, call: dict) -> tuple[object, dict]:
    try:
        arguments = json.loads(call["arguments"])
    except json.JSONDecodeError:
        return call["arguments"], {"error": "the arguments are not valid JSON"}
    if not isinstance(arguments, dict):
        return arguments, {"error": "the arguments must be a JSON object"}
    return arguments, toolbox.call(call["name"], arguments)


def run_publisher(
    draft: Path, rendered: Path, spark: Spark, toolbox: Toolbox, *, out: Path, max_turns: int = MAX_TURNS,
    effort: str = "low",
) -> dict:
    task = f"Publish the draft ad at {draft}. Its rendered video is at {rendered}."
    messages = [{"type": "message", "role": "user", "content": task}]
    turns = []
    transcript = {"prompt_version": PROMPT_VERSION, "effort": effort, "draft": str(draft)}
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{datetime.now(UTC):%Y%m%dT%H%M%S}.json"
    try:
        for _ in range(max_turns):
            turn = spark.respond(
                messages, tools=TOOLS, prompt_version=PROMPT_VERSION, effort=effort, instructions=INSTRUCTIONS
            )
            messages.extend(turn.output)
            calls = []
            for call in turn.calls:
                arguments, result = run_tool(toolbox, call)
                calls.append({"name": call["name"], "arguments": arguments, "result": result})
                sent = {k: v for k, v in result.items() if k not in UNSENT}
                messages.append({
                    "type": "function_call_output", "call_id": call["call_id"], "output": json.dumps(sent),
                })
            turns.append({"calls": calls, "text": turn.text, "usage": turn.usage})
            if not calls:
                break
        else:
            transcript["stopped"] = "turn limit"
    finally:
        # paid calls made before a failure stay on record
        transcript |= {
            "turns": turns, "final": turns[-1]["text"] if turns else "",
            "tool_calls": sum(len(t["calls"]) for t in turns),
        }
        path.write_text(json.dumps(transcript, indent=1, ensure_ascii=False), encoding="utf-8")
    return transcript | {"path": str(path)}
