import random
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

from preflight.eval.check_reconstructions import carried, words
from preflight.eval.registry import Metric
from preflight.eval.split import BreachingClaim, GroundTruth
from preflight.schema import Screening

# a quote longer than this many times a ground-truth claim, plus slack words, covers more than that claim
LONGER = 2
SLACK = 5
DRAWS = 2000
SEED = 0


def matches(truth: str, said: list[str], tight: bool) -> bool:
    n = len(words(truth))
    return carried(truth, said) != "missing" and (not tight or len(said) <= max(LONGER * n, n + SLACK))


# CAP renumbered rules 3.39 to 3.43 after these ads ran, so their rulings cite the earlier numbers, as the rule
# titles in their assessments show ("3.40 (Price Comparisons)", "3.42 (Imitation and Denigration)")
FORMER_NUMBERS = {"3.40": "3.39", "3.42": "3.41"}
CITES_FORMER_NUMBERS = frozenset({"A23-1216841", "A23-1224570", "A24-1251814"})


def related(a: str, b: str) -> bool:
    return a == b or a.startswith(b + ".") or b.startswith(a + ".")


def current(rules: list[str], item_id: str) -> list[str]:
    """A ruling's rule numbers in the numbering of the rule pack the judge cites from."""
    return [FORMER_NUMBERS.get(r, r) for r in rules] if item_id in CITES_FORMER_NUMBERS else list(rules)


class Caught(NamedTuple):
    any_rule: list[bool]  # a flag matches the claim
    with_rule: list[bool]  # ... and cites one of its rules, or a rule above or below one
    exact_rules: list[bool]  # ... and cites nothing but its rules, or rules above or below them
    rules_cited: int  # CAP rules cited on flags that match a ground-truth claim
    rules_related: int  # ... of which related to that claim's rules


def caught(truth: list[BreachingClaim], screenings: list[Screening], item_id: str = "") -> Caught:
    rules: dict[tuple[str, str], list[str]] = {}
    for s in screenings:
        for f in s.flags:
            rules.setdefault((s.screening_id, f.claim_id), []).extend(r.rule for r in f.sources if r.kind == "cap_rule")
    flagged = [(words(c.text), rules[s.screening_id, c.claim_id]) for s in screenings for c in s.claims
               if (s.screening_id, c.claim_id) in rules]  # fmt: skip
    found = [[cited for said, cited in flagged if matches(t.claim, said, tight=True)] for t in truth]
    wanted = [current(t.rules, item_id) for t in truth]

    def fits(rule: str, claim_rules: list[str]) -> bool:
        return any(related(rule, g) for g in claim_rules)

    pairs = [(cited, w) for hits, w in zip(found, wanted, strict=True) for cited in hits]
    return Caught(
        any_rule=[bool(h) for h in found],
        with_rule=[any(fits(r, w) for cited in h for r in cited) for h, w in zip(found, wanted, strict=True)],
        exact_rules=[
            any(cited and all(fits(r, w) for r in cited) for cited in h) for h, w in zip(found, wanted, strict=True)
        ],  # fmt: skip
        rules_cited=sum(len(cited) for cited, _ in pairs),
        rules_related=sum(fits(r, w) for cited, w in pairs for r in cited),
    )


@dataclass(frozen=True)
class ItemScore:
    item_id: str
    label: str
    claims: int
    carried: int
    caught: int
    caught_carried: int
    caught_any_rule: int
    flags: int
    caught_exact_rules: int = 0
    rules_cited: int = 0
    rules_related: int = 0


def score_item(truth: GroundTruth, screenings: list[Screening], kept: list[bool] | None = None) -> ItemScore:
    # kept marks the ground-truth claims the reconstruction carried; a team ad carries all of its own wording
    kept = kept if kept is not None else [True] * len(truth.claims)
    c = caught(truth.claims, screenings, truth.item_id)
    return ItemScore(
        item_id=truth.item_id,
        label=truth.label,
        claims=len(truth.claims),
        carried=sum(kept),
        caught=sum(c.with_rule),
        caught_carried=sum(h and k for h, k in zip(c.with_rule, kept, strict=True)),
        caught_any_rule=sum(c.any_rule),
        flags=sum(len(s.flags) for s in screenings),
        caught_exact_rules=sum(c.exact_rules),
        rules_cited=c.rules_cited,
        rules_related=c.rules_related,
    )


def interval(
    items: list[ItemScore],
    hit: Callable[[ItemScore], float],
    out_of: Callable[[ItemScore], float],
    draws: int = DRAWS,
    seed: int = SEED,
) -> tuple[float, float]:
    rng = random.Random(seed)
    stats = []
    for _ in range(draws):
        sample = rng.choices(items, k=len(items))
        total = sum(map(out_of, sample))
        # a resample with nothing to divide by says nothing about the ratio
        if total:
            stats.append(sum(map(hit, sample)) / total)
    cuts = statistics.quantiles(stats, n=40, method="inclusive")
    return round(cuts[0], 3), round(cuts[-1], 3)


def metric(name: str, items: list[ItemScore], hit: Callable, out_of: Callable = lambda i: 1) -> Metric:
    return Metric(name, sum(map(hit, items)), sum(map(out_of, items)), *interval(items, hit, out_of))


def metrics(items: list[ItemScore]) -> list[Metric]:
    positives = [i for i in items if i.label == "positive"]
    negatives = [i for i in items if i.label == "negative"]
    out = []
    if positives:
        out += [
            metric("ad_recall", positives, lambda i: i.caught > 0),
            metric("claim_recall", positives, lambda i: i.caught, lambda i: i.claims),
            metric("claim_recall_carried", positives, lambda i: i.caught_carried, lambda i: i.carried),
            metric("claim_recall_any_rule", positives, lambda i: i.caught_any_rule, lambda i: i.claims),
            metric("claim_recall_exact_rules", positives, lambda i: i.caught_exact_rules, lambda i: i.claims),
            Metric("rule_precision", sum(i.rules_related for i in positives), sum(i.rules_cited for i in positives)),
            Metric("flags_per_positive_ad", sum(i.flags for i in positives), len(positives)),
        ]
    if negatives:
        # every flag on a negative ad is a false alarm
        out += [
            metric("negative_ads_flagged", negatives, lambda i: i.flags > 0),
            metric("flags_per_negative_ad", negatives, lambda i: i.flags),
        ]
    return out
