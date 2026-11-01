import random
import statistics
from collections.abc import Callable
from dataclasses import dataclass

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


def related(a: str, b: str) -> bool:
    return a == b or a.startswith(b + ".") or b.startswith(a + ".")


def caught(truth: list[BreachingClaim], screenings: list[Screening]) -> tuple[list[bool], list[bool]]:
    rules: dict[tuple[str, str], list[str]] = {}
    for s in screenings:
        for f in s.flags:
            rules.setdefault((s.screening_id, f.claim_id), []).extend(r.rule for r in f.sources if r.kind == "cap_rule")
    flagged = [(words(c.text), rules[s.screening_id, c.claim_id]) for s in screenings for c in s.claims
               if (s.screening_id, c.claim_id) in rules]  # fmt: skip
    found = [[cited for said, cited in flagged if matches(t.claim, said, tight=True)] for t in truth]
    with_rule = [any(related(r, g) for cited in hits for r in cited for g in t.rules)
                 for t, hits in zip(truth, found, strict=True)]  # fmt: skip
    return [bool(h) for h in found], with_rule


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


def score_item(truth: GroundTruth, screenings: list[Screening], kept: list[bool] | None = None) -> ItemScore:
    # kept marks the ground-truth claims the reconstruction carried; a team ad carries all of its own wording
    kept = kept if kept is not None else [True] * len(truth.claims)
    hits, with_rule = caught(truth.claims, screenings)
    return ItemScore(
        item_id=truth.item_id, label=truth.label, claims=len(truth.claims), carried=sum(kept), caught=sum(with_rule),
        caught_carried=sum(h and k for h, k in zip(with_rule, kept, strict=True)), caught_any_rule=sum(hits),
        flags=sum(len(s.flags) for s in screenings),
    )


def interval(
    items: list[ItemScore], hit: Callable[[ItemScore], float], out_of: Callable[[ItemScore], float],
    draws: int = DRAWS, seed: int = SEED,
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
            Metric("flags_per_positive_ad", sum(i.flags for i in positives), len(positives)),
        ]
    if negatives:
        # every flag on a negative ad is a false alarm
        out += [
            metric("negative_ads_flagged", negatives, lambda i: i.flags > 0),
            metric("flags_per_negative_ad", negatives, lambda i: i.flags),
        ]
    return out
