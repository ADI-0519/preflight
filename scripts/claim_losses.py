import argparse
import re
from collections import defaultdict
from difflib import SequenceMatcher

from preflight.eval.check_reconstructions import NEAR, carried, words
from preflight.eval.claim_recall import WORK, media_of
from preflight.eval.run import kept
from preflight.eval.score import caught, current, fits, holds, matches
from preflight.eval.split import load_ground_truth
from preflight.schema import Screening

MEDIA_STEM = re.compile(r"-(ad|reconstruction(-\d+)?)$")

STEPS = (
    "not read",
    "shown in pieces across screenings",
    "shown in pieces on one ad's screens",
    "not extracted",
    "pieces extracted only",
    "not flagged",
    "flagged with another rule",
    "flagged, quote too long to score",
)


def saved_screenings(run_id: str) -> dict[str, list[Screening]]:
    found: dict[str, list[Screening]] = defaultdict(list)
    for path in sorted((WORK / run_id).glob(f"{run_id}-*.json")):
        # files are named <run_id>-<item_id>-<media stem>; the stem is ad, reconstruction or reconstruction-1
        item_id = MEDIA_STEM.sub("", path.stem.removeprefix(f"{run_id}-"))
        found[item_id].append(Screening.model_validate_json(path.read_text(encoding="utf-8")))
    return found


def piece(claim: str, said: list[str]) -> bool:
    return len(said) >= 2 and carried(" ".join(said), words(claim)) != "missing"


def covered(claim: str, pieces: list[list[str]]) -> bool:
    target = words(claim)
    seen = set()
    for said in pieces:
        for b in SequenceMatcher(None, target, said, autojunk=False).get_matching_blocks():
            seen.update(range(b.a, b.a + b.size))
    return len(seen) >= NEAR * len(target)


def flagged_rules(s: Screening) -> dict[str, list[str]]:
    rules: dict[str, list[str]] = defaultdict(list)
    for f in s.flags:
        rules[f.claim_id].extend(r.rule for r in f.sources if r.kind == "cap_rule")
    return rules


def lost_at(claim: str, rules: list[str], screenings: list[Screening]) -> str:
    # on screen, a claim counts as read only when one text shows it whole; concatenated texts would rejoin a split
    read = any(
        carried(claim, [w for g in s.segments for w in words(g.text)]) != "missing"
        or any(carried(claim, words(t.text)) != "missing" for t in s.on_screen)
        for s in screenings
    )
    if not read:
        # texts are matched as pieces in any order, since cards and on-screen texts are not stored in reading order
        if any(covered(claim, [words(t.text) for t in s.on_screen]) for s in screenings):
            return "shown in pieces on one ad's screens"
        texts = [words(t.text) for s in screenings for t in s.on_screen]
        return "shown in pieces across screenings" if covered(claim, texts) else "not read"
    whole = [(s, c) for s in screenings for c in s.claims if matches(claim, words(c.text), tight=False)]
    if not whole:
        parts = any(piece(claim, words(c.text)) for s in screenings for c in s.claims)
        return "pieces extracted only" if parts else "not extracted"
    cited = [r for s, c in whole for r in flagged_rules(s).get(c.claim_id, [])]
    if not any(c.claim_id in flagged_rules(s) for s, c in whole):
        return "not flagged"
    if not any(fits(r, rules) for r in cited):
        return "flagged with another rule"
    return "flagged, quote too long to score"


def pieces_caught(claim: str, rules: list[str], screenings: list[Screening]) -> bool:
    flagged = [words(c.text) for s in screenings for c in s.claims
               if any(fits(r, rules) for r in flagged_rules(s).get(c.claim_id, []))]  # fmt: skip
    return covered(claim, [said for said in flagged if holds(claim, said)])


def misses(run_id: str) -> None:
    # a plain run's carried claims it did not catch, by the step at which each dropped out; no model calls
    steps: dict[str, list[str]] = defaultdict(list)
    for item_id, screenings in sorted(saved_screenings(run_id).items()):
        # rule 5: split v2 dev only
        truth = load_ground_truth("v2", item_id)
        hit = caught(truth.claims, screenings, item_id).with_rule
        held = kept(truth) or [True] * len(truth.claims)
        for i, (t, h, k) in enumerate(zip(truth.claims, hit, held, strict=True)):
            if k and not h:
                steps[lost_at(t.claim, current(t.rules, item_id), screenings)].append(f"{item_id}/{i}")
    print(f"{run_id}: {sum(map(len, steps.values()))} carried claims missed")
    for step in STEPS:
        if ids := steps.get(step):
            print(f"  {step}: {len(ids)}  {' '.join(ids)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Find the step at which each claim a stress run lost dropped out.")
    parser.add_argument("plain", metavar="PLAIN_RUN")
    parser.add_argument("stress", metavar="STRESS_RUN", nargs="?")
    parser.add_argument("--misses", action="store_true", help="break down the plain run's own misses instead")
    args = parser.parse_args()
    if args.misses or not args.stress:
        return misses(args.plain)
    plain, stress = saved_screenings(args.plain), saved_screenings(args.stress)
    steps: dict[tuple[str, str], list[str]] = defaultdict(list)
    loose = defaultdict(list)
    for item_id, after in sorted(stress.items()):
        # rule 5: stress runs screen split v2 dev only
        truth = load_ground_truth("v2", item_id)
        # a carousel is screened as a slideshow, so the format comes from the plain reconstruction
        fmt = "video" if media_of(item_id)[0].suffix == ".mp4" else "stills"
        before = caught(truth.claims, plain[item_id], item_id).with_rule
        now = caught(truth.claims, after, item_id).with_rule
        for i, (t, b, a, k) in enumerate(zip(truth.claims, before, now, kept(truth), strict=True)):
            if not (k and b and not a):
                continue
            rules = current(t.rules, item_id)
            steps[fmt, lost_at(t.claim, rules, after)].append(f"{item_id}/{i}")
            if pieces_caught(t.claim, rules, after):
                loose[fmt].append(f"{item_id}/{i}")
    for fmt in sorted({f for f, _ in steps}):
        print(f"{args.stress} {fmt}: {sum(len(v) for (f, _), v in steps.items() if f == fmt)} lost")
        for step in STEPS:
            if ids := steps.get((fmt, step)):
                print(f"  {step}: {len(ids)}  {' '.join(ids)}")
        print(f"  every piece flagged with a matching rule: {len(loose[fmt])}  {' '.join(loose[fmt])}")


if __name__ == "__main__":
    main()
