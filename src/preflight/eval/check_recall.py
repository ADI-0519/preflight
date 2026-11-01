import argparse
import csv
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from preflight.check import EFFORT, PROMPT_VERSION, check
from preflight.check.precedents import load_precedents
from preflight.eval.claim_recall import PART, WORK, Metered, cost
from preflight.eval.registry import RESULTS, register, revision, snapshot_text
from preflight.eval.score import caught
from preflight.eval.split import GroundTruth, load_ground_truth, load_split, load_team_ad
from preflight.models import from_env
from preflight.models.clients import SPARK
from preflight.models.store import Store
from preflight.pipeline import SNAPSHOTS
from preflight.schema import Ad, Claim, OnScreenEvidence, OnScreenText, Screening, StageRun

# the dev screenings whose claims the judge is run on (docs/notes/claim-extraction.md)
CLAIMS_RUN = "claims-20261101T023641"


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
        screening_id=f"team-{item_id}",
        ad=Ad(content_hash=digest, media="image", width=1080, height=1080),
        snapshots=SNAPSHOTS,
        stages=(StageRun(stage="claims", status="skipped"),),
        screened_at=datetime.now(UTC),
        on_screen=texts,
        claims=claims,
    )


def scored(judged: dict[str, list[Screening]], truths: dict[str, GroundTruth]) -> tuple[list[dict], list[tuple]]:
    rows = []
    for item_id, screenings in judged.items():
        truth = truths[item_id]
        c = caught(truth.claims, screenings, item_id)
        flags = [f for s in screenings for f in s.flags]
        rows.append(
            {
                "item_id": item_id,
                "label": truth.label,
                "claims": len(truth.claims),
                "caught": sum(c.any_rule),
                "caught_with_rule": sum(c.with_rule),
                "caught_exact_rules": sum(c.exact_rules),
                "rules_cited": c.rules_cited,
                "rules_related": c.rules_related,
                "judged": sum(len(s.claims) for s in screenings),
                "flags": len(flags),
                "on_hold": sum(f.kind == "on_hold" for f in flags),
                "suggested": sum(f.suggested_wording is not None for f in flags),
            }
        )
        print(f"{item_id} ({truth.label}): {sum(c.any_rule)} of {len(truth.claims)} caught, {len(flags)} flags",
              flush=True)  # fmt: skip
    positives = [r for r in rows if r["label"] == "positive"]
    negatives = [r for r in rows if r["label"] == "negative"]

    def total(group: list[dict], column: str) -> int:
        return sum(r[column] for r in group)

    return rows, [
        ("ad_recall", sum(r["caught_with_rule"] > 0 for r in positives), len(positives)),
        ("claim_recall", total(positives, "caught_with_rule"), total(positives, "claims")),
        ("claim_recall_any_rule", total(positives, "caught"), total(positives, "claims")),
        # a flag counts here only if every rule it cites belongs to the claim, so citing extra rules earns nothing
        ("claim_recall_exact_rules", total(positives, "caught_exact_rules"), total(positives, "claims")),
        ("rule_precision", total(positives, "rules_related"), total(positives, "rules_cited")),
        ("flags_per_positive_ad", total(positives, "flags"), len(positives)),
        ("negative_ads_flagged_judge_only", sum(r["flags"] > 0 for r in negatives), len(negatives)),
        ("flags_per_negative_ad_judge_only", total(negatives, "flags"), len(negatives)),
    ]


def write_rows(run_id: str, rows: list[dict]) -> None:
    (RESULTS / "runs").mkdir(parents=True, exist_ok=True)
    with (RESULTS / "runs" / f"{run_id}.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def rescore(run_id: str, claims_run: str, split: str) -> None:
    """Score a saved check run again under the current scoring, with no model calls, as run <run_id>-rescored."""
    items = {}
    for path in (WORK / claims_run).glob("*.json"):
        if path.name == "details.json":
            continue
        s = Screening.model_validate_json(path.read_text(encoding="utf-8"))
        items[s.screening_id] = path.stem.rsplit("-", 1)[0]
    judged: dict[str, list[Screening]] = {}
    for path in sorted((WORK / run_id).glob("*.json")):
        if path.name == "details.json":
            continue
        s = Screening.model_validate_json(path.read_text(encoding="utf-8"))
        item_id = s.screening_id.removeprefix("team-") if s.screening_id.startswith("team-") else items[s.screening_id]
        judged.setdefault(item_id, []).append(s)
    truths = {i: load_ground_truth(split, i) for i in judged}
    rows, metrics = scored(judged, truths)
    stage = next(st for s in next(iter(judged.values())) for st in s.stages if st.stage == "check")
    new_id = f"{run_id}-rescored"
    write_rows(new_id, rows)
    common = {
        "run_id": new_id,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": revision(PART),
        "split": split,
        "part": PART,
        "stage": "check",
        "model": stage.model,
        "prompt": stage.prompt,
        "effort": stage.effort,
        "snapshots": snapshot_text(next(iter(judged.values()))[0].snapshots),
    }
    register(common, metrics)
    for metric, hits, out_of in metrics:
        print(f"{new_id} {metric}: {hits} / {out_of}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge the dev screenings' claims and score breach recall.")
    parser.add_argument("--split", default="v1")
    parser.add_argument("--claims-run", default=CLAIMS_RUN)
    parser.add_argument("--rulings", default=SNAPSHOTS.rulings, help="rulings snapshot for the precedent index")
    parser.add_argument("--prompt", default=PROMPT_VERSION)
    parser.add_argument("--effort", default=EFFORT)
    parser.add_argument("--cap-rules", default=SNAPSHOTS.cap_rules, help="CAP rule pack snapshot")
    parser.add_argument("--per-ad-precedents", action="store_true", help="retrieve rulings per ad, as before v4")
    parser.add_argument("--only", nargs="*", help="dev item IDs to run (default: all of dev)")
    parser.add_argument("--cache-dir", help="a fresh model cache, so a repeat run calls the model again")
    parser.add_argument("--rescore", metavar="RUN_ID", help="score a saved check run again; no model calls")
    args = parser.parse_args()
    if args.rescore:
        return rescore(args.rescore, args.claims_run, args.split)
    # rule 5: dev only; the test part runs once, in P33
    items = [i for i in load_split(args.split).dev if not args.only or i in args.only]
    truths = {i: load_ground_truth(args.split, i) for i in items}
    precedents = load_precedents(args.rulings)
    sha = revision(PART)
    created = datetime.now(UTC)
    run_id = f"check-{created:%Y%m%dT%H%M%S}"
    work = WORK / run_id
    work.mkdir(parents=True)
    spark = Metered(from_env(Store(args.cache_dir) if args.cache_dir else None).spark)
    snapshots = SNAPSHOTS.model_copy(update={"rulings": args.rulings, "cap_rules": args.cap_rules})

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
            checked = check(
                s.model_copy(update={"snapshots": snapshots}),
                spark,
                precedents,
                prompt=args.prompt,
                effort=args.effort,
                per_claim=not args.per_ad_precedents,
            )
            (work / f"{checked.screening_id}.json").write_text(checked.model_dump_json(indent=1), encoding="utf-8")
            out.append(checked)
        return out

    with ThreadPoolExecutor(max_workers=4) as pool:
        judged = dict(zip(items, pool.map(judge, items), strict=True))
    rows, metrics = scored(judged, truths)
    write_rows(run_id, rows)
    (work / "details.json").write_text(
        json.dumps(
            [
                {"item_id": i, "flags": [f.model_dump(mode="json") for s in ss for f in s.flags]}
                for i, ss in judged.items()
            ],
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    timed = [r.seconds for r in spark.calls if r.seconds is not None]
    metrics += [
        ("check_cost_usd", round(sum(map(cost, spark.calls)), 4), len(rows)),
        ("check_seconds", round(sum(timed), 1), len(timed)),
    ]
    common = {
        "run_id": run_id,
        "created_at": created.isoformat(timespec="seconds"),
        "git_sha": sha,
        "split": args.split,
        "part": PART,
        "stage": "check",
        "model": SPARK,
        "prompt": args.prompt + ("+ad-precedents" if args.per_ad_precedents else ""),
        "effort": args.effort,
        "snapshots": snapshot_text(snapshots),
    }
    register(common, metrics)
    for metric, hits, out_of in metrics:
        print(f"{run_id} {metric}: {hits} / {out_of}")


if __name__ == "__main__":
    main()
