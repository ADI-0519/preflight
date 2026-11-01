import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache

from preflight.schema import Claim
from preflight.sources.on_hold import OnHoldClaim
from preflight.sources.register import RegisterEntry

CAP_PER_TERM = 30
MIN_SCAN_LENGTH = 4

ALIASES: dict[str, tuple[str, ...]] = {
    "vitamin b1": ("thiamin", "thiamine"),
    "vitamin b2": ("riboflavin",),
    "vitamin b3": ("niacin",),
    "vitamin b5": ("pantothenic acid",),
    "vitamin b6": ("pyridoxine",),
    "vitamin b7": ("biotin",),
    "vitamin b9": ("folate", "folic acid"),
    "vitamin b12": ("cobalamin",),
    "vitamin d": ("cholecalciferol",),
    "omega-3": ("dha", "epa"),
    "ashwagandha": ("withania somnifera",),
    "lion's mane": ("hericium erinaceus",),
    "turmeric": ("curcuma longa", "curcumin"),
    "rhodiola": ("rhodiola rosea",),
    "saffron": ("crocus sativus",),
    "valerian": ("valeriana officinalis",),
    "chamomile": ("matricaria",),
}

_PARENTHETICAL = re.compile(r"\(([^)]*)\)")
_LIST_NUMBER = re.compile(r"^\d+\.\s*")


@dataclass(frozen=True)
class Shortlist:
    register: tuple[RegisterEntry, ...]
    on_hold: tuple[OnHoldClaim, ...]


def _normalise(text: str) -> str:
    return " ".join(text.replace("‘", "'").replace("’", "'").casefold().split())


@cache
def _phrase(phrase: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)")


def _has(phrase: str, text: str) -> bool:
    return _phrase(phrase).search(text) is not None


@cache
def _names(substance: str) -> frozenset[str]:
    names = set()
    for line in substance.splitlines():
        line = _LIST_NUMBER.sub("", _normalise(line))
        names.update(_normalise(p) for p in _PARENTHETICAL.findall(line))
        names.add(_normalise(_PARENTHETICAL.sub(" ", line)))
    return frozenset(n for n in names if n)


@cache
def _alias_pairs() -> dict[str, frozenset[str]]:
    pairs: dict[str, set[str]] = {}
    for key, alternatives in ALIASES.items():
        for alternative in alternatives:
            pairs.setdefault(key, set()).add(alternative)
            pairs.setdefault(alternative, set()).add(key)
    return {k: frozenset(v) for k, v in pairs.items()}


def _expand(term: str) -> set[str]:
    group = {term}
    for name, others in _alias_pairs().items():
        if _has(name, term):
            group |= others
    return group


def _matches(group: set[str], substance: str) -> bool:
    text = _normalise(substance)
    names = _names(substance)
    return any(_has(t, text) or any(_has(n, t) for n in names) for t in group)


def _terms(claims: Sequence[Claim], register: Sequence[RegisterEntry]) -> list[str]:
    terms = {_normalise(c.substance) for c in claims if c.substance}
    texts = [_normalise(c.text) for c in claims]
    for name in {n for e in register if e.substance for n in _names(e.substance) if len(n) >= MIN_SCAN_LENGTH}:
        if any(_has(name, text) for text in texts):
            terms.add(name)
    return sorted(terms)


def shortlist(claims: Sequence[Claim], register: Sequence[RegisterEntry], on_hold: Sequence[OnHoldClaim]) -> Shortlist:
    kept_register: set[str] = set()
    kept_on_hold: set[str] = set()
    for group in (_expand(t) for t in _terms(claims, register)):
        found = [e for e in register if e.substance and _matches(group, e.substance)]
        kept_register |= {e.register_id for e in found if e.status == "authorised"}
        others = sorted((e for e in found if e.status != "authorised"), key=lambda e: len(e.substance))
        kept_register |= {e.register_id for e in others[:CAP_PER_TERM]}
        held = sorted((h for h in on_hold if _matches(group, h.substance)), key=lambda h: len(h.substance))
        kept_on_hold |= {h.on_hold_id for h in held[:CAP_PER_TERM]}
    return Shortlist(
        register=tuple(e for e in register if e.register_id in kept_register),
        on_hold=tuple(h for h in on_hold if h.on_hold_id in kept_on_hold),
    )
