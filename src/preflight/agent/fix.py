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
    nominal_bounds,
    render_draft,
    scene_at,
    with_line,
    with_still,
)
from preflight.check.precedents import PrecedentIndex
from preflight.ingest import ingest
from preflight.models import Image, Models
from preflight.models.store import digest as bytes_digest
from preflight.pipeline import screen
from preflight.schema import Claim, Flag, Screening, verify_sources

# a line must hold at least this share of the claim's words to be its source
MIN_SCORE = 0.6
# and must beat the next best line by this much, or the flag goes to a person
MIN_MARGIN = 0.15
STILL_EDIT_PROMPT = (
    "Remove this claim from the image wherever it appears: {claim}. "
    "Keep everything else as it is and add no new text, letters, labels or logos."
)
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
    open: list[dict]


class DraftScreener:
    def __init__(
        self, models: Models, precedents: PrecedentIndex, work_dir: Path, align: Literal["mms"] | None = "mms"
    ):
        self.models, self.precedents, self.work_dir, self.align = models, precedents, work_dir, align
        self.scene_bounds: tuple[tuple[float, float], ...] | None = None

    def __call__(self, draft: Draft, screening_id: str, previous_id: str | None) -> Screening:
        rendered = render_draft(draft, self.work_dir / "renders" / screening_id)
        self.scene_bounds = rendered.scene_bounds
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


def evidence_time(screening: Screening, claim: Claim) -> float | None:
    texts = {t.text_id: t for t in screening.on_screen}
    for e in claim.evidence:
        if e.kind == "region":
            return e.frame_time
        if e.kind == "on_screen":
            return texts[e.text_id].start
    return None


@dataclass
class Round:
    draft: Draft
    substitutions: list[dict]
    still_edits: list[dict]
    superseded: list[str]
    for_person: list[dict]


def plan_round(
    draft: Draft, screening: Screening, image: Image, work_dir: Path,
    bounds: tuple[tuple[float, float], ...] | None,
) -> Round:
    claims = {c.claim_id: c for c in screening.claims}
    done = Round(draft, [], [], [], [])
    replaced: set[Address] = set()
    edited: set[int] = set()
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
        time = evidence_time(screening, claim)
        # a claim that fits two lines equally is ambiguous text, so only a claim no line holds is in the picture
        in_text = bool(scored) and scored[0][0] >= MIN_SCORE
        if wording is None and not in_text and time is not None:
            scene = scene_at(draft, time, bounds or nominal_bounds(draft))
            if scene in edited:
                done.superseded.append(flag.flag_id)
                continue
            edited.add(scene)
            done.still_edits.append(edit_still(done, flag, claim, scene, image, work_dir))
            continue
        done.for_person.append(hand_off(flag, NO_WORDING if wording is None else NOT_LOCATED, address))
    # last line first, so a wording that holds two sentences cannot shift the addresses still to be edited
    for sub in sorted(done.substitutions, key=lambda s: Address.parse(s["line"]), reverse=True):
        done.draft = with_line(done.draft, Address.parse(sub["line"]), sub["after"])
    return done


def hand_off(flag: Flag, reason: str, address: Address | None) -> dict:
    return {"flag_id": flag.flag_id, "reason": reason, "line": address and str(address)}


def open_lines(screening: Screening, draft: Draft, for_person: list[dict]) -> list[dict]:
    # the extractor can return a claim and a phrase inside it, so flags are grouped by the draft line they sit on
    flags = {f.flag_id: f for f in screening.flags}
    claims = {c.claim_id: c for c in screening.claims}
    texts = {str(a): t for a, t in lines(draft).items()}
    grouped: dict[str, dict] = {}
    for item in for_person:
        flag = flags[item["flag_id"]]
        key = item["line"] or flag.flag_id
        group = grouped.setdefault(key, {
            "line": item["line"], "text": texts[item["line"]] if item["line"] else claims[flag.claim_id].text,
            "flags": [],
        })
        group["flags"].append({
            "flag_id": flag.flag_id, "kind": flag.kind, "why": flag.reason, "reason": item["reason"],
        })
    return list(grouped.values())


def edit_still(done: Round, flag: Flag, claim: Claim, scene: int, image: Image, work_dir: Path) -> dict:
    before = done.draft.scenes[scene].still.read_bytes()
    prompt = STILL_EDIT_PROMPT.format(claim=claim.text)
    after = image.edit(before, prompt)
    path = work_dir / "stills" / f"{bytes_digest(after)[:16]}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(after)
    done.draft = with_still(done.draft, scene, path)
    return {
        "flag_id": flag.flag_id, "scene": scene, "before": bytes_digest(before), "after": bytes_digest(after),
        "prompt": prompt,
    }


def append(log: Path, record: dict) -> None:
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def fix(
    draft: Draft, *, screen_draft: ScreenDraft, image: Image, rounds: int = 3, log: Path, work_dir: Path
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
            "substitutions": [], "still_edits": [], "superseded": [], "for_person": [],
        }
        planned = None
        if is_clean(screening):
            state = "awaiting_approval"
        elif n == rounds:
            claims = {c.claim_id: c for c in screening.claims}
            record["for_person"] = [
                hand_off(f, ROUND_LIMIT, locate(scores(claims[f.claim_id], draft))) for f in screening.flags
            ]
            state = "needs_person"
        else:
            planned = plan_round(draft, screening, image, work_dir, getattr(screen_draft, "scene_bounds", None))
            record |= {
                "substitutions": planned.substitutions, "still_edits": planned.still_edits,
                "superseded": planned.superseded, "for_person": planned.for_person,
            }
            state = None if planned.substitutions or planned.still_edits else "needs_person"
        append(log, record)
        if state:
            left = open_lines(screening, draft, record["for_person"]) if state == "needs_person" else []
            append(log, {
                "event": "state", "state": state, "screening_id": screening_id, "at": now(),
                "draft": draft.model_dump(mode="json"), "open": left,
            })
            return FixResult(state, screening, draft, log, left)
        draft, previous = planned.draft, screening_id
    raise AssertionError("the last round always ends the loop")


def read_log(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]


def approve(log: Path, by: str, note: str = "") -> dict:
    # rule 4: the only place an ad is marked approved, and it records who did it
    if not by.strip():
        raise ValueError("an approval names the person who approved")
    records = read_log(log)
    if any(r["event"] == "approved" for r in records):
        raise ValueError("this fix is already approved")
    if not records or records[-1].get("state") != "awaiting_approval":
        raise ValueError("only a fix that ended awaiting approval can be approved")
    record = {
        "event": "approved", "by": by.strip(), "at": now(), "screening_id": records[-1]["screening_id"], "note": note,
    }
    append(log, record)
    return record
