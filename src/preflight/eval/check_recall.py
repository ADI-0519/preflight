import argparse
import csv
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from preflight.check import EFFORT, PROMPT_VERSION, check
from preflight.check.precedents import load_precedents
from preflight.eval.check_reconstructions import words
from preflight.eval.claim_recall import FIELDS, PART, RESULTS, RUNS, WORK, Metered, cost, git, matches
from preflight.eval.split import BreachingClaim, load_ground_truth, load_split, load_team_ad
from preflight.models import from_env
from preflight.models.clients import SPARK
from preflight.pipeline import SNAPSHOTS
from preflight.schema import Ad, Claim, OnScreenEvidence, OnScreenText, Screening, StageRun

# the dev screenings whose claims the judge is run on (docs/notes/claim-extraction.md)
CLAIMS_RUN = "claims-20261101T023641"


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


def team_screening(item_id: str) -> Screening:
    ad = load_team_ad(item_id)
    lines = ad.on_screen_text + [s for s in re.split(r"(?<=[.!?])\s+", ad.voiceover.strip()) if s]
    texts = [OnScreenText(text_id=f"text-{n}", text=t, start=0, end=0) for n, t in enumerate(lines)]
    # judge-only: each line of the team ad is taken as a claim, with no extraction stage
    claims = [
        Claim(claim_id=f"claim-{n}", text=t.text, kind="explicit", evidence=(OnScreenEvidence(text_id=t.text_id),))
        for n, t in enumerate(texts)
    ]
    digest = hashlib.sha256(ad.model_dump_json().encode()).hexdigest()
    return Screening(
        screening_id=f"team-{item_id}", ad=Ad(content_hash=digest, media="image", width=1080, height=1080),
        snapshots=SNAPSHOTS, stages=(StageRun(stage="claims", status="skipped"),), screened_at=datetime.now(UTC),
        on_screen=texts, claims=claims,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge the dev screenings' claims and score breach recall.")
    parser.add_argument("--claims-run", default=CLAIMS_RUN)
    parser.add_argument("--rulings", required=True, help="rulings snapshot the precedent index is built from")
    parser.add_argument("--prompt", default=PROMPT_VERSION)
    parser.add_argument("--effort", default=EFFORT)
    parser.add_argument("--only", nargs="*", help="dev item IDs to run (default: all of dev)")
    args = parser.parse_args()
    # rule 5: dev only; the test part runs once, in P33
    items = [i for i in load_split("v1").dev if not args.only or i in args.only]
    truths = {i: load_ground_truth("v1", i) for i in items}
    precedents = load_precedents(args.rulings)
    sha = git("rev-parse", "--short", "HEAD").strip()
    if git("status", "--porcelain", "--untracked-files=no"):
        sha += "-dirty"
    created = datetime.now(UTC)
    run_id = f"check-{created:%Y%m%dT%H%M%S}"
    work = WORK / run_id
    work.mkdir(parents=True)
    spark = Metered(from_env().spark)
    snapshots = SNAPSHOTS.model_copy(update={"rulings": args.rulings})

    def judge(item_id: str) -> list[Screening]:
        if truths[item_id].kind == "team":
            saved = [team_screening(item_id)]
        else:
            paths = sorted((WORK / args.claims_run).glob(f"{item_id}-*.json"))
            if not paths:
                raise FileNotFoundError(f"no saved screening for {item_id} in {args.claims_run}")
            saved = [Screening.model_validate_json(p.read_text(encoding="utf-8")) for p in paths]
        out = []
        for s in saved:
            checked = check(s.model_copy(update={"snapshots": snapshots}), spark, precedents, prompt=args.prompt,
                            effort=args.effort)
            (work / f"{checked.screening_id}.json").write_text(checked.model_dump_json(indent=1), encoding="utf-8")
            out.append(checked)
        return out

    with ThreadPoolExecutor(max_workers=4) as pool:
        judged = dict(zip(items, pool.map(judge, items), strict=True))
    rows = []
    for item_id, screenings in judged.items():
        truth = truths[item_id]
        hits, with_rule = caught(truth.claims, screenings)
        flags = [f for s in screenings for f in s.flags]
        rows.append({
            "item_id": item_id, "label": truth.label, "claims": len(truth.claims), "caught": sum(hits),
            "caught_with_rule": sum(with_rule), "judged": sum(len(s.claims) for s in screenings), "flags": len(flags),
            "on_hold": sum(f.kind == "on_hold" for f in flags),
            "suggested": sum(f.suggested_wording is not None for f in flags),
        })
        print(f"{item_id} ({truth.label}): {sum(hits)} of {len(truth.claims)} caught, {len(flags)} flags", flush=True)
    (RESULTS / "runs").mkdir(parents=True, exist_ok=True)
    with (RESULTS / "runs" / f"{run_id}.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (work / "details.json").write_text(json.dumps(
        [{"item_id": i, "flags": [f.model_dump(mode="json") for s in ss for f in s.flags]} for i, ss in judged.items()],
        indent=1, ensure_ascii=False,
    ), encoding="utf-8")

    positives = [r for r in rows if r["label"] == "positive"]
    negatives = [r for r in rows if r["label"] == "negative"]

    def total(group: list[dict], column: str) -> int:
        return sum(r[column] for r in group)

    timed = [r.seconds for r in spark.calls if r.seconds is not None]
    metrics = [
        ("ad_recall", sum(r["caught_with_rule"] > 0 for r in positives), len(positives)),
        ("claim_recall", total(positives, "caught_with_rule"), total(positives, "claims")),
        ("claim_recall_any_rule", total(positives, "caught"), total(positives, "claims")),
        ("flags_per_positive_ad", total(positives, "flags"), len(positives)),
        ("negative_ads_flagged_judge_only", sum(r["flags"] > 0 for r in negatives), len(negatives)),
        ("flags_per_negative_ad_judge_only", total(negatives, "flags"), len(negatives)),
        ("check_cost_usd", round(sum(map(cost, spark.calls)), 4), len(rows)),
        ("check_seconds", round(sum(timed), 1), len(timed)),
    ]
    common = {
        "run_id": run_id, "created_at": created.isoformat(timespec="seconds"), "git_sha": sha, "split": "v1",
        "part": PART, "stage": "check", "model": SPARK, "prompt": args.prompt, "effort": args.effort,
    }
    with RUNS.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        for metric, hits, out_of in metrics:
            writer.writerow(common | {"metric": metric, "hits": hits, "total": out_of})
    for metric, hits, out_of in metrics:
        print(f"{run_id} {metric}: {hits} / {out_of}")


if __name__ == "__main__":
    main()
