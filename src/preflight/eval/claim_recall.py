import argparse
import csv
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from preflight.claims import EFFORT, PROMPT_VERSION
from preflight.eval.check_reconstructions import carried, lines, words
from preflight.eval.reconstruct import OUT_DIR, SPARK_IN, SPARK_OUT, ShotList
from preflight.eval.registry import RESULTS, register, revision, snapshot_text
from preflight.eval.score import matches
from preflight.eval.split import ROOT, load_ground_truth, load_split
from preflight.ingest import ingest
from preflight.models import Models, Spark, SparkResult, from_env
from preflight.models.clients import SPARK
from preflight.pipeline import SNAPSHOTS, gather
from preflight.schema import Claim, Screening

# rule 5: prompts are tuned on dev; the test part runs once, in P33
PART = "dev"
WORK = ROOT / "data" / "work" / "runs"


@dataclass
class Metered:
    spark: Spark
    calls: list[SparkResult] = field(default_factory=list)

    def ask(self, text: str, **kwargs) -> SparkResult:
        r = self.spark.ask(text, **kwargs)
        self.calls.append(r)
        return r


def media_of(item_id: str) -> list[Path]:
    folder = OUT_DIR / item_id
    video = folder / "reconstruction.mp4"
    return [video] if video.exists() else sorted(folder.glob("reconstruction*.png"))


def screen(path: Path, models: Models, run_id: str, spark: Spark | Metered, **config) -> Screening:
    done = ingest(path)
    screening = gather(done, models, f"{run_id}-{done.ad.content_hash[:12]}", spark=spark, **config)
    # a failed stage would be scored as a miss
    failed = [r.stage for r in screening.stages if r.status == "failed"]
    if failed:
        raise RuntimeError(f"{path.name}: {', '.join(failed)} failed")
    return screening


def score(truth: list[str], claims: list[Claim], tight: bool = True) -> list[bool]:
    said = [words(c.text) for c in claims]
    return [any(matches(t, s, tight) for s in said) for t in truth]


def cost(r: SparkResult) -> float:
    return (r.usage.get("input_tokens", 0) * SPARK_IN + r.usage.get("output_tokens", 0) * SPARK_OUT) / 1e6


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract claims from dev reconstructions and score claim recall.")
    parser.add_argument("--only", nargs="*", help="dev item IDs to run (default: every dev positive)")
    parser.add_argument("--prompt", default=PROMPT_VERSION)
    parser.add_argument("--effort", default=EFFORT)
    parser.add_argument("--second-pass", action="store_true")
    args = parser.parse_args()
    config = {"prompt": args.prompt, "effort": args.effort, "second_pass": args.second_pass}
    dev = [i for i in load_split("v1").dev if not args.only or i in args.only]
    items = [i for i in dev if load_ground_truth("v1", i).label == "positive"]
    sha = revision(PART)
    created = datetime.now(UTC)
    run_id = f"claims-{created:%Y%m%dT%H%M%S}"
    work = WORK / run_id
    work.mkdir(parents=True)
    models = from_env()
    rows, details, version = [], [], args.prompt
    for item_id in items:
        truth = [c.claim for c in load_ground_truth("v1", item_id).claims]
        shots = ShotList.model_validate_json((OUT_DIR / item_id / "shotlist.json").read_text(encoding="utf-8"))
        shown = [w for line in lines(shots) for w in words(line)]
        # a claim the reconstruction lost (a genericised name) cannot be found in it
        kept = [carried(t, shown) != "missing" for t in truth]
        claims, heard, spark = [], [], Metered(models.spark)
        for path in media_of(item_id):
            screening = screen(path, models, run_id, spark, **config)
            (work / f"{item_id}-{path.stem}.json").write_text(screening.model_dump_json(indent=1), encoding="utf-8")
            claims += screening.claims
            heard += [w for e in screening.segments + screening.on_screen for w in words(e.text)]
            version = next(r.prompt for r in screening.stages if r.stage == "claims") or version
        hits, loose = score(truth, claims), score(truth, claims, tight=False)
        # carried by the reconstruction but never transcribed or read, so lost before extraction
        upstream = [k and carried(t, heard) == "missing" for t, k in zip(truth, kept, strict=True)]
        timed = [r.seconds for r in spark.calls if r.seconds is not None]
        rows.append({
            "item_id": item_id, "claims": len(truth), "found": sum(hits), "found_loose": sum(loose),
            "carried": sum(kept), "found_carried": sum(h and k for h, k in zip(hits, kept, strict=True)),
            "upstream": sum(upstream), "extracted": len(claims), "cost_usd": round(sum(map(cost, spark.calls)), 5),
            "seconds": round(sum(timed), 1), "timed": len(timed),
        })
        details.append({
            "item_id": item_id, "missed": [t for t, h in zip(truth, hits, strict=True) if not h],
            "extracted": [c.model_dump(include={"text", "kind", "substance"}) for c in claims],
        })
        print(f"{item_id}: {sum(hits)} of {len(truth)} ground-truth claims, {len(claims)} extracted", flush=True)
    (work / "details.json").write_text(json.dumps(details, indent=1, ensure_ascii=False), encoding="utf-8")
    (RESULTS / "runs").mkdir(parents=True, exist_ok=True)
    with (RESULTS / "runs" / f"{run_id}.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def total(column: str) -> float:
        return sum(r[column] for r in rows)

    common = {
        "run_id": run_id, "created_at": created.isoformat(timespec="seconds"), "git_sha": sha, "split": "v1",
        "part": PART, "stage": "claims", "model": SPARK, "prompt": version, "effort": args.effort,
        "snapshots": snapshot_text(SNAPSHOTS),
    }
    metrics = [
        ("ad_recall", sum(r["found"] > 0 for r in rows), len(rows)),
        ("claim_recall", total("found"), total("claims")),
        ("claim_recall_carried", total("found_carried"), total("carried")),
        ("claim_recall_loose", total("found_loose"), total("claims")),
        ("lost_upstream", total("upstream"), total("claims")),
        ("claims_extracted", total("extracted"), len(rows)),
        ("claims_cost_usd", round(total("cost_usd"), 4), len(rows)),
        # only calls made in this run are timed; cached answers carry the time of their original call or none
        ("claims_seconds", round(total("seconds"), 1), total("timed")),
    ]
    register(common, metrics)
    for metric, hits, out_of in metrics:
        print(f"{run_id} {metric}: {hits} / {out_of}")


if __name__ == "__main__":
    main()
