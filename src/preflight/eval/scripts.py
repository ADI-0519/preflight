"""Paired script/media evaluation on an original, retained v2 development cohort."""

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from preflight import check, claims
from preflight.check.precedents import load_precedents
from preflight.eval.check_reconstructions import carried, words
from preflight.eval.reconstruct import OUT_DIR, ShotList
from preflight.eval.registry import RESULTS, Metric, register, revision, snapshot_text, write_rows
from preflight.eval.run import joined, metered, vote_tag
from preflight.eval.score import caught, metrics, score_item
from preflight.eval.split import EVAL_DIR, ROOT, RULING_ID, GroundTruth, load_ground_truth, load_team_ad
from preflight.eval.triage import Inputs, load_inputs
from preflight.ingest import ingest
from preflight.ingest.script import PREFIX, parse_script
from preflight.models import Models, from_env
from preflight.pipeline import SNAPSHOTS, screen

OUTPUT = ROOT / "data" / "work" / "script-eval"


def script_copy(item_id: str) -> tuple[bytes, dict[str, str]]:
    """Call only after cohort validation. Export ad words, never label annotations or images."""
    if RULING_ID.fullmatch(item_id):
        path = OUT_DIR / item_id / "shotlist.json"
        shots = ShotList.model_validate_json(path.read_text(encoding="utf-8"))
        pairs = [(s.voiceover, s.on_screen_text) for s in shots.scenes]
    else:
        path = EVAL_DIR / "items" / "team" / f"{item_id}.yaml"
        ad = load_team_ad(item_id)
        pairs = [(ad.voiceover, ad.on_screen_text)]
    lines = []
    for voice, shown in pairs:
        lines.extend(f"VO: {line}" for line in voice.splitlines() if line.strip())
        lines.extend(f"SUPER: {part}" for line in shown for part in line.splitlines() if part.strip())
    raw = ("\n".join(lines) + "\n").encode("utf-8")
    parse_script(raw)
    return raw, {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()}


def prepare(run_id: str, directory: Path | None = None) -> tuple[Inputs, dict, dict, dict]:
    baseline = load_inputs(run_id, directory)
    if baseline.run["snapshots"] != snapshot_text(SNAPSHOTS):
        raise ValueError("script comparison requires the same source snapshots as the media baseline")
    configured = set(baseline.run["prompt"].split("+"))
    if not {claims.PROMPT_VERSION, check.PROMPT_VERSION} <= configured:
        raise ValueError("baseline must use the adopted claims and judge prompts")
    if check.SAMPLES > 1 and f"vote{check.SAMPLES}" not in configured:
        raise ValueError("baseline must use the adopted judge sample count")
    for ss in baseline.screenings.values():
        for s in ss:
            answered = next(r for r in s.stages if r.stage == "check").samples
            # A sample may abstain, and empty-claim checks make no judge calls.
            if s.claims and check.SAMPLES > 1 and answered not in range(2, check.SAMPLES + 1):
                raise ValueError("baseline must contain completed adopted judge votes")
    # All copy and labels are prepared before model construction, so a missing
    # shot list cannot consume credits on a partial cohort.
    copies, sources, truths = {}, {}, {}
    for item in baseline.screenings:
        copies[item], hashes = script_copy(item)
        sources.update(hashes)
    for item in baseline.screenings:
        truth = load_ground_truth("v2", item)
        if truth.item_id != item or truth.label != baseline.labels[item]:
            raise ValueError("ground truth disagrees with the original cohort")
        truths[item] = truth
    return baseline, copies, sources, truths


def textual_mask(truth: GroundTruth, raw: bytes) -> list[bool]:
    text = [w for line in parse_script(raw) for w in words(PREFIX.sub("", line.text))]
    return [carried(c.claim, text) != "missing" for c in truth.claims]


def evaluate(prepared: tuple, models: Models, out: Path) -> str:
    baseline, copies, sources, truths = prepared
    created = datetime.now(UTC)
    run_id = f"script-{created:%Y%m%dT%H%M%S}"
    sha = revision("dev")
    out.mkdir(parents=True, exist_ok=False)
    # Load every item-specific index before the first request, preserving the
    # same chronology and advertiser exclusions as media evaluation.
    precedents = {i: load_precedents(SNAPSHOTS.rulings, "v2", i) for i in copies}
    rows, before, after, saved = [], [], [], []
    gained = lost = 0
    for item, raw in copies.items():
        source = out / f"{item}.txt"
        source.write_bytes(raw)
        done = ingest(source, out / "ingest")
        item_models, bill = metered(models)
        result = screen(done, item_models, precedents[item], f"{run_id}-{item}-script", align=None)
        (out / f"{result.screening_id}.json").write_text(result.model_dump_json(), encoding="utf-8")
        mask = textual_mask(truths[item], raw)
        media_score = score_item(truths[item], baseline.screenings[item], mask)
        script_score = score_item(truths[item], [result], mask)
        b = caught(truths[item].claims, baseline.screenings[item], item).with_rule
        a = caught(truths[item].claims, [result], item).with_rule
        gained += sum(k and x and not y for k, x, y in zip(mask, a, b, strict=True))
        lost += sum(k and y and not x for k, x, y in zip(mask, a, b, strict=True))
        failed = any(r.status == "failed" for r in result.stages) or not any(
            r.stage == "check" and r.status == "done" for r in result.stages
        )
        rows.append(asdict(script_score) | {"media": 1, "incomplete_check": failed, "baseline": baseline.run["run_id"],
                    "media_caught_textual": media_score.caught_carried,
                    "script_sha256": hashlib.sha256(raw).hexdigest(), "cost_usd": round(bill(), 6)})
        before.append(media_score)
        after.append(script_score)
        saved.append(result)
    write_rows(out / "items.csv", rows)
    (out / "provenance.json").write_text(json.dumps({
        "run_id": run_id, "baseline": baseline.run, "baseline_hashes": baseline.hashes, "copy_sources": sources,
        "git_sha": sha, "items": list(copies), "split": "v2", "part": "dev",
        "notice": "Observed script-versus-media gap; modality, visual information and run variation also differ.",
    }, indent=2), encoding="utf-8")
    if any(r["incomplete_check"] for r in rows):
        raise ValueError(f"{run_id}: incomplete checks; saved locally without registering success")
    write_rows(RESULTS / "runs" / f"{run_id}.csv", rows)
    measured = [*metrics(after), *[Metric(f"media_{m.name}", m.hits, m.total, m.low, m.high) for m in metrics(before)],
                Metric("paired_claims_gained", gained, sum(s.carried for s in after)),
                Metric("paired_claims_lost", lost, sum(s.carried for s in after))]
    register({"run_id": run_id, "created_at": created.isoformat(), "git_sha": sha, "split": "v2", "part": "dev",
              "stage": "script", "model": joined(saved, lambda r: r.model),
              "prompt": joined(saved, lambda r: r.prompt) + vote_tag(check.SAMPLES, 0),
              "effort": joined(saved, lambda r: r.effort and f"{r.stage}={r.effort}"),
              "snapshots": snapshot_text(SNAPSHOTS)}, measured)
    return run_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", help="registered original v2 dev media run")
    parser.add_argument("--screenings", type=Path, help="restored baseline screening folder")
    parser.add_argument("--check-inputs", action="store_true", help="validate local inputs without model calls")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        prepared = prepare(args.baseline, args.screenings)
        if args.check_inputs:
            print(f"Ready: {len(prepared[1])} original development items; no model calls made.")
            return
        out = args.out or OUTPUT / datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        print(evaluate(prepared, from_env(), out))
    except (ValueError, OSError) as exc:
        # Evaluation inputs are synthetic/dev material; operational errors remain content-free.
        raise SystemExit(f"script evaluation inputs or run failed ({type(exc).__name__})") from None


if __name__ == "__main__":
    main()
