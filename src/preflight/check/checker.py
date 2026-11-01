"""Evidence-backed claim checking against repository snapshots."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date as Date
from math import log
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from preflight.eval.split import load_split
from preflight.models import Spark
from preflight.schema import (
    CapRuleRef,
    Claim,
    Flag,
    OnHoldRef,
    RegisterRef,
    RulingRef,
    SourceRef,
    StageRun,
    SuggestedWording,
)
from preflight.sources.cap import CapRulePack
from preflight.sources.on_hold import OnHoldClaim
from preflight.sources.register import RegisterEntry
from preflight.sources.rulings import Ruling

PROMPT_VERSION = "judge-1"
EFFORT = "medium"
_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Precedent:
    ruling_id: str
    date: Date
    advertiser: str
    rules: tuple[str, ...]
    text: str

    @classmethod
    def from_ruling(cls, ruling: Ruling) -> Precedent:
        return cls(
            ruling_id=ruling.ruling_id,
            date=ruling.date,
            advertiser=ruling.advertiser,
            rules=tuple(dict.fromkeys([*ruling.cap_rules, *ruling.bcap_rules])),
            text="\n".join(part for part in (ruling.ad_description, ruling.issue, ruling.assessment) if part),
        )


class PrecedentIndex:
    """Small dependency-free BM25 index with an explicit leakage gate."""

    def __init__(self, records: tuple[Precedent, ...], *, excluded_ids: frozenset[str] = frozenset()):
        excluded = load_split("v1").excluded_ruling_ids() | set(excluded_ids)
        overlap = {record.ruling_id for record in records} & excluded
        if overlap:
            raise ValueError(f"precedent index contains held-back ruling(s): {', '.join(sorted(overlap))}")
        self.records = records
        tokens = tuple(_tokens(record.text) for record in records)
        self._counts = tuple(Counter(document) for document in tokens)
        self._lengths = tuple(len(document) for document in tokens)
        self._average_length = sum(self._lengths) / len(records) if records else 0.0
        self._document_frequency = Counter(token for counts in self._counts for token in counts)

    @classmethod
    def from_rulings(cls, rulings: list[Ruling], excluded_ids: set[str] | frozenset[str]) -> PrecedentIndex:
        return cls(tuple(Precedent.from_ruling(ruling) for ruling in rulings), excluded_ids=frozenset(excluded_ids))

    def search(self, query: str, limit: int = 5) -> list[Precedent]:
        if limit < 1:
            return []
        query_tokens = set(_tokens(query))
        if not query_tokens:
            return []
        total = len(self.records)
        scored = []
        for index, counts in enumerate(self._counts):
            score = 0.0
            for token in query_tokens:
                if token not in counts:
                    continue
                idf = log(1 + (total - self._document_frequency[token] + 0.5) / (self._document_frequency[token] + 0.5))
                frequency = counts[token]
                length_factor = 1 - 0.75 + 0.75 * self._lengths[index] / self._average_length
                score += idf * frequency * 2.2 / (frequency + 1.2 * length_factor)
            if score:
                scored.append((score, self.records[index].date, self.records[index]))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [record for _, _, record in scored[:limit]]


def _tokens(value: str) -> list[str]:
    return _WORD.findall(value.lower())


def shortlist(entries: list[RegisterEntry], claim: Claim, limit: int = 8) -> list[RegisterEntry]:
    """Return deterministic register candidates; no model call is made per entry."""

    query = _tokens(" ".join(part for part in (claim.substance, claim.text) if part))
    if not query:
        return []
    query_set = set(query)
    scored: list[tuple[int, int, RegisterEntry]] = []
    for entry in entries:
        entry_tokens = set(_tokens(" ".join(part for part in (entry.substance, entry.wording) if part)))
        overlap = len(query_set & entry_tokens)
        substance_match = bool(
            claim.substance and entry.substance and _tokens(claim.substance) == _tokens(entry.substance)
        )
        if overlap or substance_match:
            scored.append((int(substance_match), overlap, entry))
    scored.sort(key=lambda item: (item[0], item[1], item[2].register_id), reverse=True)
    return [entry for _, _, entry in scored[:limit]]


def _source_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["register", "on_hold", "cap_rule", "ruling"]},
            "register_id": {"type": ["string", "null"]},
            "on_hold_id": {"type": ["string", "null"]},
            "rule": {"type": ["string", "null"]},
            "ruling_id": {"type": ["string", "null"]},
            "date": {"type": ["string", "null"]},
        },
        "required": ["kind", "register_id", "on_hold_id", "rule", "ruling_id", "date"],
        "additionalProperties": False,
    }


JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                    "decision": {"type": "string", "enum": ["no_flag", "possible_breach", "on_hold", "needs_review"]},
                    "reason": {"type": "string"},
                    "sources": {"type": "array", "items": _source_schema()},
                    "register_id": {"type": ["string", "null"]},
                },
                "required": ["claim_id", "decision", "reason", "sources", "register_id"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["decisions"],
    "additionalProperties": False,
}


class _Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["register", "on_hold", "cap_rule", "ruling"]
    register_id: str | None = None
    on_hold_id: str | None = None
    rule: str | None = None
    ruling_id: str | None = None
    date: Date | None = None


class _Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    decision: Literal["no_flag", "possible_breach", "on_hold", "needs_review"]
    reason: str = Field(min_length=1)
    sources: list[_Source]
    register_id: str | None = None


class _JudgeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[_Decision]


def _prompt(
    claims: list[Claim],
    candidates: dict[str, list[RegisterEntry]],
    on_hold: list[OnHoldClaim],
    cap: CapRulePack,
    precedents: dict[str, list[Precedent]],
) -> str:
    prompt = Path(__file__).resolve().parents[3] / "prompts" / "check_judge_v1.txt"
    lines = [prompt.read_text(encoding="utf-8"), "\nCAP RULES:"]
    lines.extend(
        f"- {rule.rule}: {rule.summary} (screenable={rule.screenable})"
        for rule in cap.rules.values()
        if rule.screenable
    )
    lines.append("\nON-HOLD CANDIDATES:")
    lines.extend(f"- {item.on_hold_id}: {item.substance}; {item.health_relationship or ''}" for item in on_hold)
    for claim in claims:
        lines.extend(
            [
                f"\nCLAIM {claim.claim_id}: {claim.text!r} ({claim.kind}; substance={claim.substance!r})",
                "REGISTER CANDIDATES:",
            ]
        )
        lines.extend(
            f"- {entry.register_id} [{entry.status}] {entry.substance}: {entry.wording}"
            for entry in candidates[claim.claim_id]
        )
        lines.append("PRECEDENTS:")
        lines.extend(
            f"- {item.ruling_id} ({item.date.isoformat()}), rules {', '.join(item.rules)}: {item.text[:500]}"
            for item in precedents[claim.claim_id]
        )
    return "\n".join(lines)


def _source(
    value: _Source, allowed_register: set[str], allowed_hold: set[str], allowed_rulings: set[str], cap: CapRulePack
) -> SourceRef:
    if value.kind == "register":
        if value.register_id not in allowed_register:
            raise ValueError(f"judge cited register entry outside its shortlist: {value.register_id!r}")
        return RegisterRef(register_id=value.register_id)
    if value.kind == "on_hold":
        if value.on_hold_id not in allowed_hold:
            raise ValueError(f"judge cited unknown on-hold entry: {value.on_hold_id!r}")
        return OnHoldRef(on_hold_id=value.on_hold_id)
    if value.kind == "cap_rule":
        if value.rule not in cap.rules or not cap.rules[value.rule].screenable:
            raise ValueError(f"judge cited unknown or non-screenable CAP rule: {value.rule!r}")
        return CapRuleRef(rule=value.rule)
    if value.ruling_id not in allowed_rulings or value.date is None:
        raise ValueError(f"judge cited unknown ruling precedent: {value.ruling_id!r}")
    return RulingRef(ruling_id=value.ruling_id, date=value.date)


@dataclass(frozen=True)
class CheckResult:
    flags: tuple[Flag, ...]
    stage: StageRun


def check_claims(
    claims: list[Claim],
    register: list[RegisterEntry],
    on_hold: list[OnHoldClaim],
    cap: CapRulePack,
    spark: Spark,
    *,
    precedents: PrecedentIndex | None = None,
) -> CheckResult:
    """Check claims and assemble only evidence-backed, snapshot-grounded flags."""

    candidates = {claim.claim_id: shortlist(register, claim) for claim in claims}
    holding = [
        item
        for claim in claims
        for item in on_hold
        if claim.substance and _tokens(claim.substance) == _tokens(item.substance)
    ]
    precedent_map = {claim.claim_id: precedents.search(claim.text) if precedents else [] for claim in claims}
    response = spark.ask(
        _prompt(claims, candidates, holding, cap, precedent_map),
        prompt_version=PROMPT_VERSION,
        effort=EFFORT,
        schema=JUDGE_SCHEMA,
    )
    try:
        parsed = _JudgeResponse.model_validate(response.data)
    except ValidationError as error:
        raise ValueError(f"checker returned an invalid response: {error}") from error
    expected = {claim.claim_id for claim in claims}
    claims_by_id = {claim.claim_id: claim for claim in claims}
    seen = set()
    flags = []
    register_by_id = {entry.register_id: entry for entry in register}
    for decision in parsed.decisions:
        if decision.claim_id not in expected or decision.claim_id in seen:
            raise ValueError(f"checker did not return exactly one decision per claim: {decision.claim_id}")
        seen.add(decision.claim_id)
        if decision.decision == "needs_review":
            raise ValueError(f"checker requires human review for {decision.claim_id}; screening is incomplete")
        if decision.decision == "no_flag":
            if decision.sources or decision.register_id is not None:
                raise ValueError(f"no_flag decision for {decision.claim_id} contains sources or wording")
            continue
        claim = claims_by_id[decision.claim_id]
        allowed_hold = {
            item.on_hold_id
            for item in on_hold
            if claim.substance and _tokens(claim.substance) == _tokens(item.substance)
        }
        allowed_rulings = {item.ruling_id for item in precedent_map[decision.claim_id]}
        ruling_dates = {item.ruling_id: item.date for item in precedent_map[decision.claim_id]}
        for source in decision.sources:
            if source.kind == "ruling" and ruling_dates.get(source.ruling_id) != source.date:
                raise ValueError(f"judge cited an incorrect ruling date: {source.ruling_id!r}")
        sources = tuple(
            _source(
                source,
                {entry.register_id for entry in candidates[decision.claim_id]},
                allowed_hold,
                allowed_rulings,
                cap,
            )
            for source in decision.sources
        )
        if not sources:
            raise ValueError(f"flag decision for {decision.claim_id} has no source")
        kind = "on_hold" if decision.decision == "on_hold" else "possible_breach"
        wording = None
        if decision.register_id is not None:
            entry = register_by_id.get(decision.register_id)
            if entry is None or entry not in candidates[decision.claim_id] or entry.status != "authorised":
                raise ValueError(
                    f"checker suggested a register entry that is not an authorised candidate: {decision.register_id}"
                )
            wording = SuggestedWording.from_entry(entry)
        flags.append(
            Flag(
                flag_id=f"flag-{len(flags)}",
                claim_id=decision.claim_id,
                kind=kind,
                reason=decision.reason.strip(),
                sources=sources,
                suggested_wording=wording,
            )
        )
    if seen != expected:
        raise ValueError(f"checker omitted claim decisions: {', '.join(sorted(expected - seen))}")
    return CheckResult(
        flags=tuple(flags),
        stage=StageRun(stage="check", status="done", model=response.model, prompt=PROMPT_VERSION, effort=EFFORT),
    )
