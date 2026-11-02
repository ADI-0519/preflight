import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from preflight.agent.fix import FixResult, fix_draft
from preflight.check.precedents import PrecedentIndex
from preflight.models import Models
from preflight.pipeline import screen_target
from preflight.schema import Evidence, Flag, Screening, SourceRef
from preflight.view import build_view, incomplete_stages

log = logging.getLogger(__name__)

# rule 6: anchored to the repo, so an MCP client started elsewhere still writes into the git-ignored data/work
AGENT_DIR = Path(__file__).resolve().parents[3] / "data" / "work" / "agent"

# rule 4: a person approves and publishes, so there is no tool for either
TOOLS = [
    {
        "type": "function",
        "name": "screen_ad",
        "description": (
            "Screens a draft ad against the GB nutrition and health claims register, the CAP Code and past ASA "
            "rulings before it is published. Returns flagged lines with their CAP rules, sources, evidence and "
            "any authorised register wording. This is screening, not legal advice."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string", "description": "a path to a video or image file, or an http(s) URL of a page",
                },
            },
            "required": ["target"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "fix_ad",
        "description": (
            "Screens a draft and replaces flagged lines with authorised register wording, re-screening until no "
            "issues are found or a person is needed. It never approves the ad; a person must approve the result."
        ),
        "parameters": {
            "type": "object",
            "properties": {"draft": {"type": "string", "description": "a path to a draft YAML file"}},
            "required": ["draft"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

# rule 4: no runnable approval command, since an agent with a shell could run it under a person's name
AWAITING = (
    "A person on the team must review the fixed draft and record their own approval in PreFlight. "
    "An agent cannot approve or publish it."
)
INCOMPLETE = (
    "A screening stage did not finish, so the result is incomplete. A person must look at it before anything else."
)
OPEN = "A person must decide on the open lines. Each flag says why it was handed over."


def source_text(source: SourceRef) -> str:
    match source.kind:
        case "register":
            return source.register_id
        case "on_hold":
            return f"on hold {source.on_hold_id}"
        case "cap_rule":
            return f"CAP {source.rule}"
        case "ruling":
            return source.ruling_id


def evidence_text(screening: Screening, evidence: Evidence) -> str:
    match evidence.kind:
        case "transcript":
            found = next(s for s in screening.segments if s.segment_id == evidence.segment_id)
            return f"transcript {found.start}–{found.end} s"
        case "on_screen":
            found = next(t for t in screening.on_screen if t.text_id == evidence.text_id)
            return f"on screen {found.start}–{found.end} s"
        case "region":
            return f"picture at {evidence.frame_time} s"


def flag_summary(screening: Screening, flag: Flag) -> dict:
    claim = next(c for c in screening.claims if c.claim_id == flag.claim_id)
    wording = flag.suggested_wording
    return {
        "flag_id": flag.flag_id,
        "kind": flag.kind,
        "claim": claim.text,
        "reason": flag.reason,
        "sources": [source_text(s) for s in flag.sources],
        "evidence": [evidence_text(screening, e) for e in claim.evidence],
        # rule 2: register wording as the schema holds it, never rewritten
        "suggested_wording": wording and {"register_id": wording.register_id, "wording": wording.wording},
    }


def open_lines(result: FixResult) -> list[dict]:
    # rule 3: a handed-over flag keeps its sources and evidence
    flags = {f.flag_id: f for f in result.screening.flags}
    return [
        group | {"flags": [
            flag_summary(result.screening, flags[f["flag_id"]]) | {"handed_over": f["reason"]} for f in group["flags"]
        ]}
        for group in result.open
    ]


def next_step(result: FixResult) -> str:
    if result.state == "awaiting_approval":
        return AWAITING
    return INCOMPLETE if incomplete_stages(result.screening) else OPEN


@dataclass
class Toolbox:
    models: Models
    precedents: PrecedentIndex
    out: Path = AGENT_DIR
    align: Literal["mms"] | None = "mms"

    def call(self, name: str, arguments: dict) -> dict:
        try:
            match name:
                case "screen_ad":
                    return self.screen_ad(arguments["target"])
                case "fix_ad":
                    return self.fix_ad(arguments["draft"])
            return {"error": f"unknown tool: {name}"}
        # an agent should see any failure as a result it can report, never as a dropped call
        except Exception as e:
            # rule 6: exception messages can hold ad text, so only the class is logged
            log.warning("tool %s failed: %s", name, type(e).__name__)
            return {"error": str(e)}

    def screen_ad(self, target: str) -> dict:
        screening, json_path, html_path = screen_target(
            target, self.models, self.precedents, self.out / "screenings", align=self.align
        )
        view = build_view(screening)
        return {
            "screening_id": screening.screening_id,
            "notice": screening.notice,
            "headline": screening.headline,
            "incomplete_stages": view["incomplete_stages"],
            "lines": view["lines"],
            "may_say": view["may_say"],
            "report": str(html_path),
            "json": str(json_path),
        }

    def fix_ad(self, draft: str) -> dict:
        result = fix_draft(Path(draft), self.models, self.precedents, self.out / "fixes", align=self.align)
        return {
            "state": result.state,
            "notice": result.screening.notice,
            "headline": result.screening.headline,
            "screening_id": result.screening.screening_id,
            "log": str(result.log),
            "incomplete_stages": incomplete_stages(result.screening),
            "open": open_lines(result),
            "next_step": next_step(result),
        }
