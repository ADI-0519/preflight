import argparse
import csv
import io
import time
import wave
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from preflight.check.precedents import PrecedentIndex, load_precedents
from preflight.eval.check_reconstructions import carried, lines, words
from preflight.eval.claim_recall import WORK, Metered, cost, media_of
from preflight.eval.reconstruct import OUT_DIR, ShotList
from preflight.eval.registry import RESULTS, RUNS, Metric, register, revision, snapshot_text, write_rows
from preflight.eval.score import ItemScore, metrics, score_item
from preflight.eval.split import RULING_ID, GroundTruth, load_ground_truth, load_split
from preflight.eval.team_media import TEAM_DIR
from preflight.ingest import ingest
from preflight.models import Models, from_env
from preflight.models.clients import Sam, SamResult, Turn, VoiceTranscribe
from preflight.pipeline import SNAPSHOTS, screen
from preflight.schema import Screening

# published prices (docs/plan.md); SAM bills every decoded frame, at least 50 per video
SAM_FRAME, SAM_MIN_FRAMES, SAM_IMAGE, TRANSCRIBE_HOUR = 0.20 / 1000, 50, 2.50 / 1000, 0.18
WORKERS = 3


@dataclass
class MeteredSam:
    client: Sam
    usd: list[float] = field(default_factory=list)

    def segment(self, prompt: str, **media) -> SamResult:
        r = self.client.segment(prompt, **media)
        frames = r.usage.get("video_frames_processed")
        self.usd.append(SAM_IMAGE if frames is None else max(frames, SAM_MIN_FRAMES) * SAM_FRAME)
        return r


@dataclass
class MeteredTranscribe:
    client: VoiceTranscribe
    usd: list[float] = field(default_factory=list)

    def transcribe(self, wav: bytes) -> list[Turn]:
        with wave.open(io.BytesIO(wav)) as f:
            self.usd.append(f.getnframes() / f.getframerate() / 3600 * TRANSCRIBE_HOUR)
        return self.client.transcribe(wav)


def metered(models: Models) -> tuple[Models, Callable[[], float]]:
    spark, sam, heard = Metered(models.spark), MeteredSam(models.sam), MeteredTranscribe(models.transcribe)
    # cached answers are priced as if called, so the figure is what screening the ad costs
    bill = lambda: sum(map(cost, spark.calls)) + sum(sam.usd) + sum(heard.usd)  # noqa: E731
    return Models(spark, heard, sam, models.image, models.glimmer), bill


def media(item_id: str) -> list[Path]:
    return media_of(item_id) if RULING_ID.match(item_id) else sorted((TEAM_DIR / item_id).glob("ad.*"))


def kept(truth: GroundTruth) -> list[bool] | None:
    if truth.kind == "team":
        return None
    shots = ShotList.model_validate_json((OUT_DIR / truth.item_id / "shotlist.json").read_text(encoding="utf-8"))
    shown = [w for line in lines(shots) for w in words(line)]
    # a claim the reconstruction lost (a genericised name) cannot be found in it
    return [carried(c.claim, shown) != "missing" for c in truth.claims]


def screen_item(
    truth: GroundTruth, models: Models, precedents: PrecedentIndex, run_id: str, align: Literal["mms"] | None,
) -> tuple[ItemScore, list[Screening], float]:
    item_models, bill = metered(models)
    screenings = []
    for path in media(truth.item_id):
        s = screen(ingest(path), item_models, precedents, f"{run_id}-{truth.item_id}-{path.stem}", align=align)
        (WORK / run_id / f"{s.screening_id}.json").write_text(s.model_dump_json(indent=1), encoding="utf-8")
        screenings.append(s)
    return score_item(truth, screenings, kept(truth)), screenings, bill()


def joined(screenings: list[Screening], value) -> str:
    return "+".join(dict.fromkeys(v for s in screenings for r in s.stages if (v := value(r))))


def citation_spread(screenings: list[Screening]) -> list[Metric]:
    cited = Counter(s.ruling_id for sc in screenings for f in sc.flags for s in f.sources if s.kind == "ruling")
    total = sum(cited.values())
    return [
        Metric("precedent_citations_top6", sum(n for _, n in cited.most_common(6)), total),
        Metric("precedent_rulings_cited", len(cited), total),
    ]


def rescore(run_id: str) -> None:
    with RUNS.open(newline="", encoding="utf-8") as f:
        row = next((r for r in csv.DictReader(f) if r["run_id"] == run_id), None)
    if row is None:
        raise SystemExit(f"{run_id} is not a registered run")
    if row["part"] == "test":
        # rule 5: the test part is scored once, by the run that screened it
        raise SystemExit("a test run is not rescored")
    if reason := void_runs().get(run_id):
        raise SystemExit(f"{run_id} is void ({reason}) and is not rescored")
    scored = RESULTS / "runs" / f"{run_id}.csv"
    if "-rescored-" in run_id or not scored.exists():
        raise SystemExit(f"{run_id} has no saved screenings; rescore the run that screened the ads")
    with scored.open(newline="", encoding="utf-8") as f:
        expected = {r["item_id"]: int(r["media"]) for r in csv.DictReader(f)}
    screenings: dict[str, list[Screening]] = {}
    for path in sorted((WORK / run_id).glob(f"{run_id}-*.json")):
        # files are named <run_id>-<item_id>-<media stem>; the media stem holds no hyphen, so the last one splits them
        item_id = path.stem.removeprefix(f"{run_id}-").rsplit("-", 1)[0]
        screenings.setdefault(item_id, []).append(Screening.model_validate_json(path.read_text(encoding="utf-8")))
    short = sorted(i for i, n in expected.items() if len(screenings.get(i, [])) != n)
    if short:
        # rule 11: a rescore on fewer ads would register under the same split and part as the whole run
        raise SystemExit(f"{run_id}: saved screenings missing for {', '.join(short)}")
    # in the split's order, as the run scored them, so the bootstrap draws the same resamples
    order = [i for i in getattr(load_split(row["split"]), row["part"]) if i in expected]
    truths = [load_ground_truth(row["split"], i) for i in order]
    scores = [score_item(t, screenings[t.item_id], kept(t)) for t in truths]
    created = datetime.now(UTC)
    # stamped, so a run rescored again after a later scoring change is registered apart from the first rescore
    new_id = f"{run_id}-rescored-{created:%Y%m%dT%H%M%S}"
    write_rows(RESULTS / "runs" / f"{new_id}.csv", [asdict(s) for s in scores])
    run_metrics = [*metrics(scores), *citation_spread([s for ss in screenings.values() for s in ss])]
    register(row | {"run_id": new_id, "created_at": created.isoformat(timespec="seconds"),
                    "git_sha": revision(row["part"])}, run_metrics)  # fmt: skip
    show(new_id, run_metrics)


def void_runs() -> dict[str, str]:
    # registered runs that must not be quoted, with the reason; rows in runs.csv are never edited
    path = RESULTS / "void.csv"
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {r["run_id"]: r["reason"] for r in csv.DictReader(f)}


def show(run_id: str, run_metrics: list[Metric]) -> None:
    for m in run_metrics:
        print(f"{run_id} {m.name}: {m.hits} / {m.total}" + (f" [{m.low}, {m.high}]" if m.low is not None else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="Screen every item of a split part end to end and register the run.")
    parser.add_argument("--split", help="split version (default: v1)")
    parser.add_argument("--part", choices=["dev", "test"], help="split part (default: dev)")
    parser.add_argument("--only", nargs="*", help="item IDs to run (default: the whole part)")
    parser.add_argument("--no-align", action="store_true", help="keep each transcription turn's timing")
    parser.add_argument("--rescore", metavar="RUN_ID", help="score a registered dev run again; no model calls")
    args = parser.parse_args()
    if args.rescore:
        if args.split or args.part or args.only:
            # a rescore takes its split, part and items from the registered run
            parser.error("--rescore takes no --split, --part or --only")
        return rescore(args.rescore)
    args.split, args.part = args.split or "v1", args.part or "dev"
    if args.part == "test" and args.only:
        raise SystemExit("the test part runs whole")
    sha = revision(args.part)
    items = [i for i in getattr(load_split(args.split), args.part) if not args.only or i in args.only]
    missing = [i for i in items if not media(i)]
    if missing:
        raise SystemExit(f"no rendered media for {', '.join(missing)}; build reconstructions and team ads first")
    truths = [load_ground_truth(args.split, i) for i in items]
    # each item gets its own index, so an item's ruling never stands as its own precedent
    precedents = {t.item_id: load_precedents(SNAPSHOTS.rulings, args.split, t.item_id) for t in truths}
    models = from_env()
    created = datetime.now(UTC)
    run_id = f"screen-{created:%Y%m%dT%H%M%S}"
    (WORK / run_id).mkdir(parents=True)
    began = time.monotonic()
    align = None if args.no_align else "mms"
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        done = list(pool.map(lambda t: screen_item(t, models, precedents[t.item_id], run_id, align), truths))
    seconds = time.monotonic() - began

    rows = []
    for score, screenings, usd in done:
        failed = sorted({r.stage for s in screenings for r in s.stages if r.status == "failed"})
        incomplete_check = not screenings or any(
            not any(r.stage == "check" and r.status == "done" for r in s.stages) for s in screenings
        )
        rows.append(asdict(score) | {
            "media": len(screenings), "failed": " ".join(failed), "incomplete_check": incomplete_check,
            "cost_usd": round(usd, 5),
        })
        print(f"{score.item_id} ({score.label}): {score.caught} of {score.claims} caught, {score.flags} flags"
              + (f", FAILED {' '.join(failed)}" if failed else ""), flush=True)  # fmt: skip
    write_rows(RESULTS / "runs" / f"{run_id}.csv", rows)
    if any(r["failed"] or r["incomplete_check"] for r in rows):
        # a failed stage would be scored as a miss or as a clean ad; rerun, and cached stages cost nothing
        raise SystemExit(f"{run_id}: stages failed or checks did not finish, so the run is not registered")

    screenings = [s for _, ss, _ in done for s in ss]
    run_metrics = [
        *metrics([score for score, _, _ in done]),
        Metric("screen_cost_usd", round(sum(r["cost_usd"] for r in rows), 4), len(rows)),
        Metric("screen_wall_seconds", round(seconds, 1), len(rows)),
        *citation_spread(screenings),
    ]
    register({
        "run_id": run_id, "created_at": created.isoformat(timespec="seconds"), "git_sha": sha, "split": args.split,
        "part": args.part, "stage": "screen", "model": joined(screenings, lambda r: r.model),
        "prompt": joined(screenings, lambda r: r.prompt),
        "effort": joined(screenings, lambda r: r.effort and f"{r.stage}={r.effort}"),
        "snapshots": snapshot_text(SNAPSHOTS),
    }, run_metrics)
    show(run_id, run_metrics)


if __name__ == "__main__":
    main()
