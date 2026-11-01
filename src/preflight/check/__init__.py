from functools import cache

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


def parse(answer: dict, claims: list[Claim], found: Shortlist, rulings: list[Ruling]) -> list[Flag]:
    authorised = {e.register_id: e for e in found.register if e.status == "authorised"}
    dates = {r.ruling_id: r.date for r in rulings}
    judged = [v["claim_id"] for v in answer["verdicts"]]
    # a claim left unjudged would read as no issue
    if sorted(judged) != sorted(c.claim_id for c in claims):
        raise ValueError(f"judge gave verdicts for {judged}, not one for each of the {len(claims)} claims")
    verdicts = {v["claim_id"]: v for v in answer["verdicts"]}
    flags = []
    for claim in claims:
        v = verdicts[claim.claim_id]
        if v["verdict"] == "no_issue":
            continue
        sources: list[SourceRef] = [CapRuleRef(rule=r) for r in v["cap_rules"]]
        sources += [RegisterRef(register_id=i) for i in v.get("register_ids", [])]
        sources += [OnHoldRef(on_hold_id=i) for i in v.get("on_hold_ids", [])]
        sources += [RulingRef(ruling_id=i, date=dates[i]) for i in v.get("ruling_ids", [])]
        suggested = v.get("suggested_register_id")
        # rule 2: section 3 and other non-health claims never get wording
        health = v["verdict"] == "on_hold" or any(r.startswith("15.") for r in v["cap_rules"])
        flags.append(Flag(
            flag_id=f"flag-{len(flags)}",
            claim_id=claim.claim_id,
            kind=v["verdict"],
            reason=v["reason"].strip(),
            # a breach or on-hold verdict citing nothing fails validation here (rule 3)
            sources=tuple(dict.fromkeys(sources)),
            suggested_wording=SuggestedWording.from_entry(authorised[suggested]) if health and suggested else None,
        ))
    return flags


def check(
    screening: Screening, spark: Spark, precedents: PrecedentIndex, *, prompt: str = PROMPT_VERSION,
    effort: str = EFFORT,
) -> Screening:
    s = screening.snapshots
    if precedents.version != s.rulings:
        raise ValueError(f"precedent index {precedents.version} is not the screening's rulings snapshot {s.rulings}")
    claims = list(screening.claims)
    if not claims:
        run, flags = StageRun(stage="check", status="skipped"), []
    else:
        found = shortlist(claims, _register(s.gb_register), _on_hold(s.on_hold))
        rules = list(_rules(s.cap_rules))
        rulings = precedents.top(" ".join(c.text for c in claims), k=PRECEDENTS)
        r = spark.ask(
            question(screening, found, rules, rulings, prompt), prompt_version=prompt, effort=effort,
            schema=output_schema(claims, found, rules, rulings),
        )
        flags = parse(r.data, claims, found, rulings)
        run = StageRun(stage="check", status="done", model=r.model, prompt=prompt, effort=effort)
    checked = screening.model_copy(update={"flags": flags, "stages": (*screening.stages, run)})
    # rules 2 and 3: every reference and suggested wording exists in the snapshots the screening names
    verify_sources(checked)
    return checked
