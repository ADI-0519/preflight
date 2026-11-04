import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from preflight.eval.check_reconstructions import NEAR, carried, words
from preflight.eval.run import kept, saved
from preflight.eval.score import caught, current, fits, holds, matches
from preflight.schema import Screening
from preflight.view import TIERS, build_view

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


def piece(claim: str, said: list[str]) -> bool:
    return len(said) >= 2 and carried(" ".join(said), words(claim)) != "missing"


def covered(claim: str, pieces: list[list[str]]) -> bool:
    target = words(claim)
    if not target:
        return False
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


def diagnose(run_id: str, directory: Path | None = None, baseline: str | None = None) -> dict:
    row, screenings, truths = saved(run_id, directory)
    if row["split"] != "v2" or row["part"] != "dev" or row["stage"] not in {"screen", "stress"}:
        raise SystemExit("diagnostics require a registered v2 development screen or stress run")
    plain = None
    if baseline:
        base_row, plain, _ = saved(baseline)
        if base_row["split"] != row["split"] or base_row["part"] != "dev" or base_row["stage"] != "screen":
            raise SystemExit("the baseline must be a screening run on the same development split")
        if not set(screenings) <= set(plain):
            raise SystemExit("the baseline is missing items screened by the compared run")
    misses, unmatched = [], []
    total = hits = 0
    for truth in truths:
        item_id = truth.item_id
        after = screenings[item_id]
        original = plain[item_id] if plain is not None else after
        fmt = "video" if original[0].ad.media == "video" else "stills"
        now = caught(truth.claims, after, item_id).with_rule
        carried_claims = kept(truth)
        carried_claims = carried_claims if carried_claims is not None else [True] * len(truth.claims)
        before = caught(truth.claims, plain[item_id], item_id).with_rule if plain is not None else None
        for i, (t, a, k) in enumerate(zip(truth.claims, now, carried_claims, strict=True)):
            total += bool(k)
            hits += bool(k and a)
            if not k or a or (before is not None and not before[i]):
                continue
            rules = current(t.rules, item_id)
            misses.append({"id": f"{item_id}/{i}", "format": fmt, "claim": t.claim, "rules": rules,
                           "step": lost_at(t.claim, rules, after),
                           "flagged_pieces_cover": pieces_caught(t.claim, rules, after)})
        # Match the scorer's folded review lines, not raw flags. A line is
        # unmatched only when none of its phrases holds a claim with a related rule.
        if truth.label != "positive":
            continue
        for s in after:
            rules = flagged_rules(s)
            for line in build_view(s)["lines"]:
                ids = {part["claim_id"] for part in [line, *line["folded"]]}
                matched = any(
                    holds(t.claim, words(c.text)) and any(fits(r, current(t.rules, item_id)) for r in rules[c.claim_id])
                    for c in s.claims if c.claim_id in ids for t in truth.claims
                )
                if not matched:
                    unmatched.append({"item_id": item_id, "screening_id": s.screening_id, **line})
    return {
        "run": row, "baseline": baseline, "dev_only": True, "registered_metrics_changed": False,
        "items": len(truths), "carried": total, "caught": hits,
        "miss_scope": "lost against baseline" if baseline else "all carried misses",
        "misses_by_step": {step: sum(m["step"] == step for m in misses) for step in STEPS},
        "misses": misses, "unmatched_lines": unmatched,
        "unmatched_by_tier": {tier: sum(line["tier"] == tier for line in unmatched) for tier in TIERS},
        "notice": "Unmatched means absent from the ruling labels, not an incorrect flag. Piece coverage is diagnostic.",
    }


GRADE_FIELDS = ("item_id", "screening_id", "claim_id", "tier", "text", "rules", "reasons", "grade")


def grading_sheet(report: dict, n: int, out: Path) -> int:
    """Write n unmatched lines, drawn with the run ID as seed, for a blind grade: breach, arguable or wrong.

    The sheet holds each line's tier, rules and the judge's reasons but not the ruling, so a grader working from
    the CAP rule pack is not steered by what the ASA said.
    """
    lines = report["unmatched_lines"]
    drawn = random.Random(report["run"]["run_id"]).sample(lines, min(n, len(lines)))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, GRADE_FIELDS)
        w.writeheader()
        w.writerows({
            "item_id": x["item_id"], "screening_id": x["screening_id"], "claim_id": x["claim_id"],
            "tier": x["tier"], "text": x["text"], "rules": " ".join(x["primary_rules"] + x["other_rules"]),
            "reasons": " | ".join(x["flags"]["reasons"]), "grade": "",
        } for x in drawn)  # fmt: skip
    return len(drawn)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose saved dev misses and unmatched lines without model calls.")
    parser.add_argument("plain", metavar="PLAIN_RUN")
    parser.add_argument("stress", nargs="?", metavar="STRESS_RUN", help="compare losses against PLAIN_RUN")
    parser.add_argument("--screenings", type=Path, help="saved folder for the diagnosed run (not its baseline)")
    parser.add_argument("--json", action="store_true", help="include claim evidence and tiers as JSON on stdout")
    parser.add_argument("--grade", type=int, metavar="N", help="write N unmatched lines for a blind grade")
    parser.add_argument("--grade-out", type=Path, help="the grading sheet (default: data/work/grading/<run>.csv)")
    args = parser.parse_args()
    report = diagnose(args.stress or args.plain, args.screenings, args.plain if args.stress else None)
    if args.grade:
        out = args.grade_out or Path("data/work/grading") / f"{report['run']['run_id']}.csv"
        n = grading_sheet(report, args.grade, out)
        print(f"wrote {n} of {len(report['unmatched_lines'])} unmatched lines to {out}", file=sys.stderr)
    if args.json:
        print(json.dumps(report, indent=2))
        return
    print(f"{report['run']['run_id']}: {report['caught']}/{report['carried']} carried claims caught")
    print(f"{len(report['misses'])} {report['miss_scope']}")
    for step, count in report["misses_by_step"].items():
        ids = " ".join(m["id"] for m in report["misses"] if m["step"] == step)
        print(f"  {step}: {count}  {ids}")
    for fmt in sorted({m["format"] for m in report["misses"]}):
        print(f"  {fmt}: {sum(m['format'] == fmt for m in report['misses'])} misses")
    print(f"Unmatched positive-ad review lines by tier: {report['unmatched_by_tier']}")
    print(report["notice"])


if __name__ == "__main__":
    main()
