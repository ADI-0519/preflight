import math
import random
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import NamedTuple

from preflight.eval.check_reconstructions import carried, words
from preflight.eval.registry import Metric
from preflight.eval.split import BreachingClaim, GroundTruth
from preflight.schema import Screening
from preflight.sources.cap import load_cap_rules
from preflight.view import fold

# a quote longer than this many times a ground-truth claim, plus slack words, covers more than that claim
LONGER = 2
SLACK = 5
DRAWS = 2000
SEED = 0


def matches(truth: str, said: list[str], tight: bool) -> bool:
    n = len(words(truth))
    return carried(truth, said) != "missing" and (not tight or len(said) <= max(LONGER * n, n + SLACK))


# CAP renumbered section 3 in April 2025, after these ads ran, so their rulings cite the earlier numbers, as the
# rule titles and wording in their assessments show ("3.40 (Price Comparisons)", "3.42 (Imitation and Denigration)",
# and 3.50 for a claimed approval by a public body, now 3.52)
FORMER_NUMBERS = {
    "A23-1216841": {"3.40": "3.39"},
    "A23-1224570": {"3.42": "3.41"},
    "A24-1251814": {"3.42": "3.41"},
    "A24-1241017": {"3.50": "3.52"},
}


def related(a: str, b: str) -> bool:
    return a == b or a.startswith(b + ".") or b.startswith(a + ".")


def current(rules: list[str], item_id: str) -> list[str]:
    """A ruling's rule numbers in the numbering of the rule pack the judge cites from."""
    former = FORMER_NUMBERS.get(item_id, {})
    return [former.get(r, r) for r in rules]


def fits(rule: str, claim_rules: list[str]) -> bool:
    return any(related(rule, g) for g in claim_rules)


class Caught(NamedTuple):
    any_rule: list[bool]  # a flag matches the claim
    with_rule: list[bool]  # ... and cites one of its rules, or a rule above or below one
    exact_rules: list[bool]  # ... and cites nothing unrelated to the ground-truth claims the flag matches
    all_rules: list[bool]  # ... and also cites every one of the claim's rules
    rules_cited: int  # CAP rules cited on flags that match a ground-truth claim
    rules_related: int  # ... of which related to the rules of the claims that flag matches
    rules_wanted: int  # CAP rules of the ground-truth claims some flag matches
    rules_found: int  # ... of which cited on a flag matching that claim
    by_chance: list[float]  # chance that the flags matching the claim would cite one of its rules if picked at random
    weighted: list[float]  # best share of a matching flag's rules that belong to the claims it carries


@cache
def _screenable(version: str) -> tuple[str, ...]:
    return tuple(r.rule for r in load_cap_rules(version).rules.values() if r.screenable)


def _chance(k: int, claim_rules: list[str], pack: tuple[str, ...]) -> float:
    # k rules drawn without replacement from the rules the judge may cite
    fitting = sum(fits(r, claim_rules) for r in pack)
    return 1 - math.comb(len(pack) - fitting, k) / math.comb(len(pack), k) if k <= len(pack) else 1.0


def caught(truth: list[BreachingClaim], screenings: list[Screening], item_id: str = "") -> Caught:
    rules: dict[tuple[str, str], list[str]] = {}
    for s in screenings:
        for f in s.flags:
            rules.setdefault((s.screening_id, f.claim_id), []).extend(r.rule for r in f.sources if r.kind == "cap_rule")
    flagged = [(words(c.text), rules[s.screening_id, c.claim_id]) for s in screenings for c in s.claims
               if (s.screening_id, c.claim_id) in rules]  # fmt: skip
    wanted = [current(t.rules, item_id) for t in truth]
    # the ground-truth claims each flag matches: one extracted phrase can carry two claims with different rules
    matched = [[i for i, t in enumerate(truth) if matches(t.claim, said, tight=True)] for said, _ in flagged]
    # a flag's rules are judged against the rules of every claim it carries, so citing both claims' rules is right
    union = [[r for i in m for r in wanted[i]] for m in matched]
    hits = [[k for k, m in enumerate(matched) if i in m] for i in range(len(truth))]

    def exact(k: int) -> bool:
        return bool(flagged[k][1]) and all(fits(r, union[k]) for r in flagged[k][1])

    def found(g: str, h: list[int]) -> bool:
        return any(related(g, r) for k in h for r in flagged[k][1])

    pack = _screenable(screenings[0].snapshots.cap_rules) if screenings else ()

    def by_chance(h: list[int], w: list[str]) -> float:
        missed = math.prod(1 - _chance(len(flagged[k][1]), w, pack) for k in h)
        return 1 - missed if h else 0.0

    def weighted(h: list[int], w: list[str]) -> float:
        # a flag that cites one right rule among five earns a fifth of a catch
        shares = [sum(fits(r, union[k]) for r in flagged[k][1]) / len(flagged[k][1])
                  for k in h if any(fits(r, w) for r in flagged[k][1])]  # fmt: skip
        return max(shares, default=0.0)

    return Caught(
        any_rule=[bool(h) for h in hits],
        with_rule=[any(fits(r, w) for k in h for r in flagged[k][1]) for h, w in zip(hits, wanted, strict=True)],
        exact_rules=[
            any(exact(k) and any(fits(r, w) for r in flagged[k][1]) for k in h)
            for h, w in zip(hits, wanted, strict=True)
        ],
        all_rules=[
            any(exact(k) and all(any(related(g, r) for r in flagged[k][1]) for g in w) for k in h)
            for h, w in zip(hits, wanted, strict=True)
        ],
        rules_cited=sum(len(flagged[k][1]) for k, m in enumerate(matched) if m),
        rules_related=sum(fits(r, union[k]) for k, m in enumerate(matched) if m for r in flagged[k][1]),
        rules_wanted=sum(len(w) for h, w in zip(hits, wanted, strict=True) if h),
        rules_found=sum(found(g, h) for h, w in zip(hits, wanted, strict=True) if h for g in w),
        by_chance=[by_chance(h, w) for h, w in zip(hits, wanted, strict=True)],
        weighted=[weighted(h, w) for h, w in zip(hits, wanted, strict=True)],
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
    caught_all_rules: int = 0
    rules_cited: int = 0
    rules_related: int = 0
    rules_wanted: int = 0
    rules_found: int = 0
    lines: int = 0
    unmatched_lines: int = 0
    chance_carried: float = 0.0
    weighted_carried: float = 0.0


def line_counts(truth: list[BreachingClaim], screenings: list[Screening], item_id: str = "") -> tuple[int, int]:
    wanted = [current(t.rules, item_id) for t in truth]
    total = unmatched = 0
    for s in screenings:
        cited = {f.claim_id: [] for f in s.flags}
        for f in s.flags:
            cited[f.claim_id].extend(r.rule for r in f.sources if r.kind == "cap_rule")
        for top, nested in fold(s):
            total += 1
            unmatched += not any(
                matches(t.claim, words(c.text), tight=True)
                and any(related(r, g) for r in cited[c.claim_id] for g in w)
                for c in [top, *nested] for t, w in zip(truth, wanted, strict=True)
            )  # fmt: skip
    return total, unmatched


def score_item(truth: GroundTruth, screenings: list[Screening], kept: list[bool] | None = None) -> ItemScore:
    # kept marks the ground-truth claims the reconstruction carried; a team ad carries all of its own wording
    kept = kept if kept is not None else [True] * len(truth.claims)
    c = caught(truth.claims, screenings, truth.item_id)
    lines, unmatched = line_counts(truth.claims, screenings, truth.item_id)
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
        caught_all_rules=sum(c.all_rules),
        rules_cited=c.rules_cited,
        rules_related=c.rules_related,
        rules_wanted=c.rules_wanted,
        rules_found=c.rules_found,
        lines=lines,
        unmatched_lines=unmatched,
        chance_carried=round(sum(p for p, k in zip(c.by_chance, kept, strict=True) if k), 3),
        weighted_carried=round(sum(w for w, k in zip(c.weighted, kept, strict=True) if k), 3),
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


def at_most(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def exact(hits: int, n: int) -> tuple[float, float]:
    # Clopper-Pearson: the proportions whose binomial tail beyond the count holds 2.5% on each side
    def solve(k: int, target: float) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(50):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if at_most(k, n, mid) > target else (lo, mid)
        return lo

    low = 0.0 if hits == 0 else solve(hits - 1, 0.975)
    high = 1.0 if hits == n else solve(hits, 0.025)
    return round(low, 3), round(high, 3)


def metric(name: str, items: list[ItemScore], hit: Callable, out_of: Callable = lambda i: 1) -> Metric:
    # claims, lines and rules cluster within an ad, so the interval resamples ads
    return Metric(name, round(sum(map(hit, items)), 3), sum(map(out_of, items)), *interval(items, hit, out_of))


def per_ad(name: str, items: list[ItemScore], hit: Callable[[ItemScore], bool]) -> Metric:
    # one yes or no per ad is a plain binomial count, and a bootstrap of 0 of n gives the false certainty [0, 0]
    hits = sum(map(hit, items))
    return Metric(name, hits, len(items), *exact(hits, len(items)))


def metrics(items: list[ItemScore]) -> list[Metric]:
    positives = [i for i in items if i.label == "positive"]
    negatives = [i for i in items if i.label == "negative"]
    out = []
    if positives:
        out += [
            per_ad("ad_recall", positives, lambda i: i.caught > 0),
            metric("claim_recall", positives, lambda i: i.caught, lambda i: i.claims),
            metric("claim_recall_carried", positives, lambda i: i.caught_carried, lambda i: i.carried),
            # what the same flags would score citing as many rules picked at random: the floor the headline sits on
            metric("claim_recall_carried_by_chance", positives, lambda i: i.chance_carried, lambda i: i.carried),
            metric("claim_recall_carried_weighted", positives, lambda i: i.weighted_carried, lambda i: i.carried),
            metric("claim_recall_any_rule", positives, lambda i: i.caught_any_rule, lambda i: i.claims),
            metric("claim_recall_exact_rules", positives, lambda i: i.caught_exact_rules, lambda i: i.claims),
            metric("claim_recall_all_rules", positives, lambda i: i.caught_all_rules, lambda i: i.claims),
            metric("rule_precision", positives, lambda i: i.rules_related, lambda i: i.rules_cited),
            metric("rule_recall", positives, lambda i: i.rules_found, lambda i: i.rules_wanted),
            Metric("flags_per_positive_ad", sum(i.flags for i in positives), len(positives)),
            Metric("flagged_lines_per_positive_ad", sum(i.lines for i in positives), len(positives)),
            Metric("unmatched_lines_per_positive_ad", sum(i.unmatched_lines for i in positives), len(positives)),
        ]
    if negatives:
        # every flag on a negative ad is a false alarm
        out += [
            per_ad("negative_ads_flagged", negatives, lambda i: i.flags > 0),
            metric("flags_per_negative_ad", negatives, lambda i: i.flags),
        ]
    return out
