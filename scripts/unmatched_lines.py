"""Count a dev run's flagged lines by review tier, matched against the ASA's claims or not, with no model calls.

Lines that match no ruled claim are not all false alarms: a ruling only covers what was complained about. The
--sample option writes some unmatched lines for a blind grade (breach, arguable or wrong) from the CAP rule pack,
without the ruling, so a grader cannot be steered by what the ASA said.
"""

import argparse
import csv
import random
from collections import Counter
from pathlib import Path

# run as a script, so its own folder is on the path
from claim_losses import saved_screenings

from preflight.eval.score import matched_lines
from preflight.eval.split import load_ground_truth
from preflight.view import TIERS, build_view

FIELDS = ("item_id", "screening_id", "claim_id", "tier", "text", "rules", "reasons", "grade")


def tally(run_id: str) -> tuple[Counter, list[dict]]:
    counts: Counter = Counter()
    unmatched = []
    for item_id, screenings in sorted(saved_screenings(run_id).items()):
        # rule 5: split v2 dev only
        truth = load_ground_truth("v2", item_id)
        for s in screenings:
            # every line on a clean ad is a false alarm; on a ruled ad, one that matches no objected claim is unmatched
            matched = matched_lines(truth.claims, s, item_id)
            for line in build_view(s)["lines"]:
                state = "matched" if matched[line["claim_id"]] else "unmatched"
                counts[truth.label, line["tier"], state] += 1
                if state == "unmatched":
                    unmatched.append({
                        "item_id": item_id, "screening_id": s.screening_id, "claim_id": line["claim_id"],
                        "tier": line["tier"], "text": line["text"],
                        "rules": " ".join(line["primary_rules"] + line["other_rules"]),
                        "reasons": " | ".join(line["flags"]["reasons"]), "grade": "",
                    })  # fmt: skip
    return counts, unmatched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_id")
    parser.add_argument("--sample", type=int, help="write this many unmatched lines, drawn at random, for grading")
    parser.add_argument("--out", type=Path, help="where the sample goes (default: data/work/grading/<run>.csv)")
    args = parser.parse_args()
    counts, unmatched = tally(args.run_id)
    print(f"{args.run_id}: flagged lines by tier")
    print(f"{'':10}" + "".join(f"{t:>12}" for t in TIERS[:3]))
    for label, state in (("positive", "matched"), ("positive", "unmatched"), ("negative", "unmatched")):
        print(f"{label[:3]} {state:9}" + "".join(f"{counts[label, t, state]:>12}" for t in TIERS[:3]))
    if args.sample:
        out = args.out or Path("data/work/grading") / f"{args.run_id}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        # seeded on the run, so the same run always gives the same sample
        drawn = random.Random(args.run_id).sample(unmatched, min(args.sample, len(unmatched)))
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, FIELDS)
            w.writeheader()
            w.writerows(drawn)
        print(f"wrote {len(drawn)} of {len(unmatched)} unmatched lines to {out}")


if __name__ == "__main__":
    main()
