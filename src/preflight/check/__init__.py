from functools import cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from preflight.check.precedents import PrecedentIndex
from preflight.check.shortlist import Shortlist, shortlist
from preflight.claims import PROMPTS, listing
from preflight.models import Spark
from preflight.schema import (
    CapRuleRef,
    Claim,
    Flag,
    OnHoldRef,
    RegisterRef,
    RulingRef,
    Screening,
    SourceRef,
    StageRun,
    SuggestedWording,
    verify_sources,
)
from preflight.sources.cap import CapRule, load_cap_rules
from preflight.sources.on_hold import load_on_hold
from preflight.sources.register import load_register
from preflight.sources.rulings import Ruling

PROMPT_VERSION = "judge_v3"
EFFORT = "high"
PRECEDENTS = 3
# a ruling's assessment runs to several thousand words; its opening carries the finding
RULING_CHARS = 3000


@cache
def _register(version: str):
    return tuple(load_register(version))


@cache
def _on_hold(version: str):
    return tuple(load_on_hold(version))


@cache
def _rules(version: str) -> tuple[CapRule, ...]:
    return tuple(r for r in load_cap_rules(version).rules.values() if r.screenable)


def ids(values: list[str]) -> dict:
    return {"type": "array", "items": {"type": "string", "enum": values}}


def output_schema(claims: list[Claim], found: Shortlist, rules: list[CapRule], rulings: list[Ruling]) -> dict:
    verdict = {
        "claim_id": {"type": "string", "enum": [c.claim_id for c in claims]},
        "verdict": {"type": "string", "enum": ["possible_breach", "on_hold", "no_issue"]},
        "cap_rules": ids([r.rule for r in rules]),
    }
    # a list with nothing to cite is left out, since an enum may not be empty
    if found.register:
        verdict["register_ids"] = ids([e.register_id for e in found.register])
    if found.on_hold:
        verdict["on_hold_ids"] = ids([c.on_hold_id for c in found.on_hold])
    if rulings:
        verdict["ruling_ids"] = ids([r.ruling_id for r in rulings])
    verdict["reason"] = {"type": "string"}
    authorised = [e.register_id for e in found.register if e.status == "authorised"]
    if authorised:
        # rule 2: the model picks an entry; its wording is copied from the register
        verdict["suggested_register_id"] = {"type": ["string", "null"], "enum": [*authorised, None]}
    item = {"type": "object", "properties": verdict, "required": list(verdict), "additionalProperties": False}
    # one item schema for all claims: the API caps a schema at 3,000 enum values in total
    verdicts = {"type": "array", "items": item}
    return {
        "type": "object",
        "properties": {"verdicts": verdicts},
        "required": ["verdicts"],
        "additionalProperties": False,
    }


def question(screening: Screening, found: Shortlist, rules: list[CapRule], rulings: list[Ruling], prompt: str) -> str:
    out = [(PROMPTS / f"{prompt}.txt").read_text(encoding="utf-8")]
    out += ["Claims:"]
    for c in screening.claims:
        out.append(f'{c.claim_id} ({c.kind}, substance: {c.substance or "none named"}): "{c.text}"')
    out += ["", listing(list(screening.segments), list(screening.on_screen), list(screening.tracks))]
    out += ["", "CAP Code rules:"]
    out += [f"{r.rule}: {r.summary} Breach looks like: {r.breach_evidence}" for r in rules]
    out += ["", "Register entries:"]
    out += [f'{e.register_id} [{e.status}; {e.substance}]: "{e.wording}"' for e in found.register] or ["none"]
    out += ["", "On-hold entries:"]
    out += [
        f"{c.on_hold_id} [on hold; {' '.join(c.substance.split())}]: {c.health_relationship or 'no relationship given'}"
        for c in found.on_hold
    ] or ["none"]
    out += ["", "Past rulings:"]
    for r in rulings:
        out += [
            f"{r.ruling_id} ({r.date:%d %B %Y}; CAP rules {', '.join(r.cap_rules) or 'none listed'})",
            f"Ad description: {r.ad_description[:RULING_CHARS]}",
            f"Assessment: {r.assessment[:RULING_CHARS]}",
        ]
    if not rulings:
        out.append("none")
    return "\n".join(out)


class _Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claim_id: str
    verdict: Literal["possible_breach", "on_hold", "no_issue"]
    cap_rules: list[str]
    register_ids: list[str] = Field(default_factory=list)
    on_hold_ids: list[str] = Field(default_factory=list)
    ruling_ids: list[str] = Field(default_factory=list)
    suggested_register_id: str | None = None
    reason: str = Field(min_length=1)


class _Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdicts: list[_Verdict]


def parse(
    answer: dict, claims: list[Claim], found: Shortlist, rulings: list[Ruling], rules: list[CapRule],
) -> list[Flag]:
    # Cached and replayed responses must obey the same contract as a live answer.
    parsed = _Answer.model_validate(answer)
    authorised = {e.register_id: e for e in found.register if e.status == "authorised"}
    dates = {r.ruling_id: r.date for r in rulings}
    allowed_rules = {r.rule for r in rules}
    judged = [v.claim_id for v in parsed.verdicts]
    # a claim left unjudged would read as no issue
    if sorted(judged) != sorted(c.claim_id for c in claims):
        raise ValueError(f"judge gave verdicts for {judged}, not one for each of the {len(claims)} claims")
    verdicts = {v.claim_id: v for v in parsed.verdicts}
    flags = []
    for claim in claims:
        v = verdicts[claim.claim_id]
        if v.verdict == "no_issue":
            if v.cap_rules or v.register_ids or v.on_hold_ids or v.ruling_ids or v.suggested_register_id:
                raise ValueError(f"no_issue verdict for {claim.claim_id} contains sources or suggested wording")
            continue
        if set(v.cap_rules) - allowed_rules:
            raise ValueError(f"{claim.claim_id} cites a CAP rule outside the screenable candidates")
        candidates = shortlist([claim], found.register, found.on_hold)
        if set(v.register_ids) - {e.register_id for e in candidates.register}:
            raise ValueError(f"{claim.claim_id} cites a register entry outside its candidates")
        if set(v.on_hold_ids) - {e.on_hold_id for e in candidates.on_hold}:
            raise ValueError(f"{claim.claim_id} cites an on-hold entry outside its candidates")
        if set(v.ruling_ids) - dates.keys():
            raise ValueError(f"{claim.claim_id} cites a ruling outside the retrieved candidates")
        sources: list[SourceRef] = [CapRuleRef(rule=r) for r in v.cap_rules]
        sources += [RegisterRef(register_id=i) for i in v.register_ids]
        sources += [OnHoldRef(on_hold_id=i) for i in v.on_hold_ids]
        sources += [RulingRef(ruling_id=i, date=dates[i]) for i in v.ruling_ids]
        suggested = v.suggested_register_id
        # rule 2: section 3 and other non-health claims never get wording
        health = v.verdict == "on_hold" or any(r.startswith("15.") for r in v.cap_rules)
        if health and suggested and suggested not in {
            e.register_id for e in candidates.register if e.status == "authorised"
        }:
            raise ValueError(f"{claim.claim_id} suggests register wording outside its authorised candidates")
        flags.append(Flag(
            flag_id=f"flag-{len(flags)}",
            claim_id=claim.claim_id,
            kind=v.verdict,
            reason=v.reason,
            # a breach or on-hold verdict citing nothing fails validation here (rule 3)
            sources=tuple(dict.fromkeys(sources)),
            suggested_wording=SuggestedWording.from_entry(authorised[suggested]) if health and suggested else None,
        ))
    return flags


def check(
    screening: Screening, spark: Spark, precedents: PrecedentIndex, *, prompt: str = PROMPT_VERSION,
    effort: str = EFFORT,
) -> Screening:
    if screening.flags or any(r.stage == "check" for r in screening.stages):
        raise ValueError("screening already contains flags or a check stage")
    s = screening.snapshots
    if precedents.version != s.rulings:
        raise ValueError(f"precedent index {precedents.version} is not the screening's rulings snapshot {s.rulings}")
    claims = list(screening.claims)
    if not claims:
        extracted = any(r.stage == "claims" and r.status == "done" for r in screening.stages)
        run, flags = StageRun(stage="check", status="done" if extracted else "skipped"), []
    else:
        found = shortlist(claims, _register(s.gb_register), _on_hold(s.on_hold))
        rules = list(_rules(s.cap_rules))
        rulings = precedents.top(" ".join(c.text for c in claims), k=PRECEDENTS)
        r = spark.ask(
            question(screening, found, rules, rulings, prompt), prompt_version=prompt, effort=effort,
            schema=output_schema(claims, found, rules, rulings),
        )
        flags = parse(r.data, claims, found, rulings, rules)
        run = StageRun(stage="check", status="done", model=r.model, prompt=prompt, effort=effort)
    checked = screening.model_copy(update={"flags": flags, "stages": (*screening.stages, run)})
    # rules 2 and 3: every reference and suggested wording exists in the snapshots the screening names
    verify_sources(checked)
    return checked
