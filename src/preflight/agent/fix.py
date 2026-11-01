import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from preflight.agent.draft import (
    Address,
    Draft,
    digest,
    lines,
    render_draft,
    with_line,
)
from preflight.check.precedents import PrecedentIndex
from preflight.ingest import ingest
from preflight.models import Models
from preflight.pipeline import screen
from preflight.schema import Claim, Screening, verify_sources

# a line must hold at least this share of the claim's words to be its source
MIN_SCORE = 0.6
# and must beat the next best line by this much, or the flag goes to a person
MIN_MARGIN = 0.15
NO_WORDING = "no authorised wording"
NOT_LOCATED = "could not locate the claim in the draft"
ROUND_LIMIT = "round limit reached"

ScreenDraft = Callable[[Draft, str, str | None], Screening]


@dataclass
class FixResult:
    state: Literal["awaiting_approval", "needs_person"]
    screening: Screening
    draft: Draft
    log: Path


class DraftScreener:
    def __init__(
        self, models: Models, precedents: PrecedentIndex, work_dir: Path, align: Literal["mms"] | None = "mms"
    ):
        self.models, self.precedents, self.work_dir, self.align = models, precedents, work_dir, align

    def __call__(self, draft: Draft, screening_id: str, previous_id: str | None) -> Screening:
        rendered = render_draft(draft, self.work_dir / "renders" / screening_id)
        done = ingest(rendered.media, self.work_dir / "ingest")
        return screen(done, self.models, self.precedents, screening_id, align=self.align)


def new_fix_id(draft: Draft) -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{digest(draft)[:12]}"


def is_clean(screening: Screening) -> bool:
    # rules 1 and 3: a screening with a failed stage is incomplete, never clean
    return not screening.flags and all(r.status != "failed" for r in screening.stages)


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def scores(claim: Claim, draft: Draft) -> list[tuple[float, Address]]:
    kinds = {e.kind for e in claim.evidence}
    wanted = {"voiceover" for k in kinds if k == "transcript"} | {"caption" for k in kinds if k != "transcript"}
    words = tokens(claim.text)
    return sorted(
        (
            (len(words & tokens(text)) / len(words) if words else 0.0, address)
            for address, text in lines(draft).items()
            if address.kind in wanted
        ),
        reverse=True,
    )


def locate(scored: list[tuple[float, Address]]) -> Address | None:
    if not scored or scored[0][0] < MIN_SCORE:
        return None
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    return scored[0][1] if scored[0][0] - runner_up >= MIN_MARGIN else None


@dataclass
class Round:
    draft: Draft
    substitutions: list[dict]
    superseded: list[str]
    for_person: list[dict]


def plan_round(draft: Draft, screening: Screening) -> Round:
    claims = {c.claim_id: c for c in screening.claims}
    done = Round(draft, [], [], [])
    replaced: set[Address] = set()
    for flag in screening.flags:
        claim = claims[flag.claim_id]
        scored = scores(claim, draft)
        address = locate(scored)
        wording = flag.suggested_wording
        if address and wording:
            if address in replaced:
                done.superseded.append(flag.flag_id)
                continue
            replaced.add(address)
            # rule 2: the only text written into a draft is a register entry's wording
            done.substitutions.append({
                "flag_id": flag.flag_id, "claim_id": claim.claim_id, "register_id": wording.register_id,
                "line": str(address), "before": lines(draft)[address], "after": wording.wording,
            })
            continue
        done.for_person.append({"flag_id": flag.flag_id, "reason": NO_WORDING if wording is None else NOT_LOCATED})
    # last line first, so a wording that holds two sentences cannot shift the addresses still to be edited
    for sub in sorted(done.substitutions, key=lambda s: Address.parse(s["line"]), reverse=True):
        done.draft = with_line(done.draft, Address.parse(sub["line"]), sub["after"])
    return done


def append(log: Path, record: dict) -> None:
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def fix(
    draft: Draft, *, screen_draft: ScreenDraft, rounds: int = 3, log: Path, work_dir: Path
) -> FixResult:
    work_dir.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    fix_id = work_dir.name
    previous = None
    for n in range(rounds + 1):
        screening_id = f"{fix_id}-{n}"
        screening = screen_draft(draft, screening_id, previous)
        if screening.previous_id != previous:
            screening = screening.model_copy(update={"previous_id": previous})
        verify_sources(screening)
        (work_dir / f"{screening_id}.json").write_text(screening.model_dump_json(indent=1), encoding="utf-8")
        record = {
            "event": "round", "fix_id": fix_id, "round": n, "at": now(), "digest": digest(draft),
            "draft": draft.model_dump(mode="json"), "screening_id": screening_id, "headline": screening.headline,
            "flags": [f.flag_id for f in screening.flags],
            "substitutions": [], "superseded": [], "for_person": [],
        }
        planned = None
        if is_clean(screening):
            state = "awaiting_approval"
        elif n == rounds:
            record["for_person"] = [{"flag_id": f.flag_id, "reason": ROUND_LIMIT} for f in screening.flags]
            state = "needs_person"
        else:
            planned = plan_round(draft, screening)
            record |= {
                "substitutions": planned.substitutions,
                "superseded": planned.superseded, "for_person": planned.for_person,
            }
            state = None if planned.substitutions else "needs_person"
        append(log, record)
        if state:
            append(log, {
                "event": "state", "state": state, "screening_id": screening_id, "at": now(),
                "draft": draft.model_dump(mode="json"),
            })
            return FixResult(state, screening, draft, log)
        draft, previous = planned.draft, screening_id
    raise AssertionError("the last round always ends the loop")

