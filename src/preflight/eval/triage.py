"""Measure P43 on saved development screenings, without rerunning any stage."""

import argparse
import csv
import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from preflight.eval.check_reconstructions import words
from preflight.eval.registry import RESULTS, RUNS, git, snapshot_text, write_rows
from preflight.eval.score import holds
from preflight.eval.split import ROOT, GroundTruth, load_ground_truth, load_split
from preflight.models import Glimmer, Store
from preflight.schema import Screening
from preflight.triage import MODELS, PROMPT_VERSION, PROMPTS, Result, Unit, baseten_client, classify, units

WORK = ROOT / "data" / "work" / "runs"
OUTPUT = ROOT / "data" / "work" / "triage"


def fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass
class Inputs:
    run: dict
    screenings: dict[str, list[Screening]]
    hashes: dict[str, str]
    labels: dict[str, str]


def load_inputs(run_id: str, directory: Path | None = None) -> Inputs:
    """Validate the saved cohort before opening labels or constructing a client."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]*", run_id):
        raise ValueError("run ID must be a filename component")
    raw = RUNS.read_bytes()
    rows = [r for r in csv.DictReader(raw.decode("utf-8").splitlines()) if r["run_id"] == run_id]
    if not rows or any(r["split"] != "v2" or r["part"] != "dev" or r["stage"] != "screen" for r in rows):
        raise ValueError("triage requires a registered v2 development screening run")
    keys = ("split", "part", "stage", "model", "prompt", "snapshots", "git_sha", "effort")
    if any(any(r[k] != rows[0][k] for k in keys) for r in rows):
        raise ValueError("source run has conflicting provenance")
    void = RESULTS / "void.csv"
    if void.exists():
        with void.open(newline="", encoding="utf-8") as source:
            if any(r["run_id"] == run_id for r in csv.DictReader(source)):
                raise ValueError("void runs cannot supply triage measurements")
    raw_scores = (RESULTS / "runs" / f"{run_id}.csv").read_bytes()
    scores = list(csv.DictReader(raw_scores.decode("utf-8").splitlines()))
    split = load_split("v2")
    expected = {r["item_id"]: int(r["media"]) for r in scores}
    if not expected or len(expected) != len(scores) or not set(expected) <= set(split.dev) or any(
        n < 1 for n in expected.values()
    ) or len(set(split.items)) != len(split.items):
        raise ValueError("source rows must identify a unique development cohort with positive media counts")
    if any(r["label"] not in {"positive", "negative"} for r in scores):
        raise ValueError("invalid source item labels")
    # Earlier runs can predate additions to an open dev split. Their registered
    # population counts, rather than today's manifest size, establish the cohort.
    populations = {"ad_recall": "positive", "negative_ads_flagged": "negative"}
    for metric, label in populations.items():
        population = sum(r["label"] == label for r in scores)
        registered = [r for r in rows if r["metric"] == metric]
        if population and (len(registered) != 1 or float(registered[0]["total"]) != population):
            raise ValueError("source cohort disagrees with registered ad denominators")
    saved = {item: [] for item in expected}
    hashes = {"registry": fingerprint(raw), "item_scores": fingerprint(raw_scores),
              "split": fingerprint(split.model_dump_json().encode())}
    directory = directory if directory is not None else WORK / run_id
    for path in sorted(directory.glob(f"{run_id}-*.json")):
        suffix = path.stem.removeprefix(run_id + "-")
        matching = [item for item in expected if suffix.startswith(item + "-")]
        if len(matching) != 1:
            raise ValueError("unexpected screening outside the original development cohort")
        payload = path.read_bytes()
        s = Screening.model_validate_json(payload)
        if s.screening_id != path.stem or snapshot_text(s.snapshots) != rows[0]["snapshots"]:
            raise ValueError("screening identity or snapshots disagree with the registered run")
        if any(stage.status == "failed" for stage in s.stages) or not any(
            stage.stage == "check" and stage.status == "done" for stage in s.stages
        ):
            raise ValueError("triage measurement requires completed source screenings")
        saved[matching[0]].append(s)
        hashes[path.name] = fingerprint(payload)
    if any(len(saved[item]) != count for item, count in expected.items()):
        raise ValueError("missing saved media screenings; restore the complete original dev bundle")
    return Inputs(rows[0], saved, hashes, {r["item_id"]: r["label"] for r in scores})


def measure(item: str, ad_units: list[Unit], result: Result, truth: GroundTruth) -> tuple[dict, list[dict]]:
    if truth.item_id != item:
        raise ValueError("ground truth identity mismatch")
    by_id = {d.id: d.needs_review for d in result.decisions}
    if len(by_id) != len(result.decisions) or set(by_id) != {u.id for u in ad_units}:
        raise ValueError("measurement needs exactly one decision per unit")
    bearing = {u.id: [i for i, c in enumerate(truth.claims) if holds(c.claim, words(u.text))] for u in ad_units}
    skips = [{"item_id": item, "unit_id": u.id, "screening_id": u.screening_id,
              "kind": u.kind, "source_id": u.source_id, "claim_indices": bearing[u.id]}
             for u in ad_units if bearing[u.id] and not by_id[u.id]]
    covered = {i for indices in bearing.values() for i in indices}
    kept = {i for uid, indices in bearing.items() if by_id[uid] for i in indices}
    return {
        "item_id": item, "units": len(ad_units), "skipped": sum(not v for v in by_id.values()),
        "claim_units": sum(bool(v) for v in bearing.values()),
        "claim_units_kept": sum(bool(v) and by_id[uid] for uid, v in bearing.items()),
        "claims": len(truth.claims), "claims_in_units": len(covered), "claims_kept": len(kept),
        # characters stand in for the input tokens a skipped unit would save in the stages after triage
        "chars": sum(len(u.text) for u in ad_units),
        "skipped_chars": sum(len(u.text) for u in ad_units if not by_id[u.id]),
        "triage_input_tokens": result.usage.get("prompt_tokens", 0),
        "triage_output_tokens": result.usage.get("completion_tokens", 0),
        "fallback": result.fallback,
    }, skips


def evaluate(inputs: Inputs, client: Glimmer, out: Path) -> dict:
    # Validate all evidence and labels before the first paid request.
    batch = {item: units(saved) for item, saved in inputs.screenings.items()}
    truths = {item: load_ground_truth("v2", item) for item in batch}
    if any(t.item_id != item or t.label != inputs.labels[item] for item, t in truths.items()):
        raise ValueError("ground truth identity or label disagrees with source rows")
    out.mkdir(parents=True, exist_ok=False)
    rows, skips, responses = [], [], {}
    for item, ad_units in batch.items():
        start = time.perf_counter()
        response = classify(client, ad_units)
        row, missed = measure(item, ad_units, response, truths[item])
        row["seconds"] = round(time.perf_counter() - start, 3)
        rows.append(row)
        skips.extend(missed)
        responses[item] = asdict(response)
        (out / "responses.json").write_text(json.dumps(responses, indent=2), encoding="utf-8")
    totals = {key: sum(r[key] for r in rows) for key in (
        "units", "skipped", "claim_units", "claim_units_kept", "claims", "claims_in_units", "claims_kept", "chars",
        "skipped_chars", "triage_input_tokens", "triage_output_tokens", "fallback",
    )}
    def ratio(numerator: str, denominator: str) -> float | None:
        return totals[numerator] / totals[denominator] if totals[denominator] else None
    report = {
        "source_run": inputs.run["run_id"], "split": "v2", "part": "dev", "items": list(batch),
        "model_requested": client.model, "models_returned": sorted({r["model"] for r in responses.values()}),
        "host": "Baseten", "prompt": PROMPT_VERSION, "totals": totals,
        "cache_mode": client.store.mode,
        "claim_unit_recall": ratio("claim_units_kept", "claim_units"),
        "skip_share": ratio("skipped", "units"), "units_skipped_per_ad": totals["skipped"] / len(rows),
        "skipped_char_share": ratio("skipped_chars", "chars"),
        "skipped_chars_per_ad": totals["skipped_chars"] / len(rows),
        "triage_tokens_per_ad": (totals["triage_input_tokens"] + totals["triage_output_tokens"]) / len(rows),
        # the full pipeline judges every unit, so a single false skip leaves triage below it (the issue's watch-out)
        "matches_full_pipeline_recall": not skips,
        "gates_screening": False,
        "limitations": ["Dev experiment; not final test results.",
                        "Labels identify breaching claims, not every possible health or nutrition claim.",
                        "Text-only; visual and cross-unit claims can lack a matching text unit.",
                        "Skipped units are potential downstream input savings, not measured API cost savings.",
                        "Wall time includes cache lookups; cache mode does not certify fresh inference.",
                        "No OCR, transcription, extraction or checking stage was rerun."],
        "hashes": inputs.hashes | {
            "prompt": fingerprint((PROMPTS / f"{PROMPT_VERSION}.txt").read_bytes()),
            "evaluation_code": fingerprint(Path(__file__).read_bytes()),
            "triage_code": fingerprint((Path(__file__).parents[1] / "triage.py").read_bytes()),
            **{f"truth:{i}": fingerprint(t.model_dump_json().encode()) for i, t in truths.items()},
        },
        "git_sha": git("rev-parse", "HEAD").strip(), "dirty": bool(git("status", "--porcelain")),
        "created_at": datetime.now(UTC).isoformat(),
    }
    write_rows(out / "items.csv", rows)
    (out / "false-skips.json").write_text(json.dumps(skips, indent=2), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--screenings", type=Path, help="retained screening folder for this registered dev run")
    parser.add_argument("--check-inputs", action="store_true", help="validate the cohort without labels or credentials")
    parser.add_argument("--model", choices=MODELS, help="defaults to GLIMMER_MODEL or Muse Spark Open")
    parser.add_argument("--replay", action="store_true", help="cache only; never contact Baseten")
    parser.add_argument("--cache", type=Path, default=OUTPUT / "cache")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        inputs = load_inputs(args.run_id, args.screenings)
    except (OSError, ValueError, KeyError):
        parser.error("need a registered, non-void v2 dev run and every original saved screening")
    if args.check_inputs:
        print(f"Validated {len(inputs.screenings)} development items; no labels or credentials opened.")
        return
    load_dotenv()
    model = args.model or os.environ.get("GLIMMER_MODEL") or MODELS[0]
    if model not in MODELS:
        parser.error("GLIMMER_MODEL must identify a supported Meta open-weights model")
    key = "replay-only" if args.replay else os.environ.get("BASETEN_API_KEY")
    if not key:
        parser.error("set BASETEN_API_KEY locally, or use --replay with recorded responses")
    out = args.out or OUTPUT / f"triage-{datetime.now(UTC):%Y%m%dT%H%M%S}"
    with baseten_client(key) as api:
        client = Glimmer(Store(args.cache, "replay" if args.replay else "cache"), model, api)
        report = evaluate(inputs, client, out)
    print(json.dumps({"output": str(out), "claim_unit_recall": report["claim_unit_recall"],
                      "skip_share": report["skip_share"], "skipped_char_share": report["skipped_char_share"],
                      "matches_full_pipeline_recall": report["matches_full_pipeline_recall"],
                      "gates_screening": False}))


if __name__ == "__main__":
    main()
