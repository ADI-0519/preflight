import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from preflight import check as judge
from preflight import claims as extraction
from preflight.check import check
from preflight.check.precedents import PrecedentIndex
from preflight.claims import extract_claims
from preflight.evidence import on_screen, regions
from preflight.evidence.on_screen import read_on_screen, snap
from preflight.evidence.regions import find_regions
from preflight.evidence.transcribe import transcribe
from preflight.ingest import Ingested, capture, ingest
from preflight.models import Models, Spark
from preflight.models.clients import SAM, SPARK, TRANSCRIBE
from preflight.report import render_html
from preflight.schema import Screening, Snapshots, StageRun

log = logging.getLogger(__name__)

SNAPSHOTS = Snapshots(gb_register="2026-05-19", on_hold="2021-01-12", cap_rules="2026-10-31", rulings="2026-11-01")


def default_id(done: Ingested) -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{done.ad.content_hash[:12]}"


def attempt[T](stage: str, model: str, prompt: str | None, empty: T, call: Callable[[], tuple[T, StageRun]]):
    try:
        return call()
    except Exception as e:
        # rule 6: exception messages can hold ad text, so only the class is logged
        log.warning("stage %s failed: %s", stage, type(e).__name__)
        return empty, StageRun(stage=stage, status="failed", model=model, prompt=prompt)


def gather(
    done: Ingested, models: Models, screening_id: str, *, spark: Spark | None = None,
    align: Literal["mms"] | None = "mms", prompt: str = extraction.PROMPT_VERSION, effort: str = extraction.EFFORT,
    second_pass: bool = False,
) -> Screening:
    with ThreadPoolExecutor(max_workers=3) as pool:
        heard = pool.submit(
            attempt, "transcribe", TRANSCRIBE, None, [], lambda: transcribe(done, models.transcribe, align)
        )
        read = pool.submit(
            attempt, "on_screen", SPARK, on_screen.PROMPT_VERSION, [], lambda: read_on_screen(done, models.spark)
        )
        found = pool.submit(attempt, "regions", SAM, regions.PROMPT_VERSION, [], lambda: find_regions(done, models.sam))
        (segments, heard_run), (texts, read_run), (tracks, found_run) = heard.result(), read.result(), found.result()
    texts = snap(texts, tracks)
    claims, claims_run = attempt(
        "claims", SPARK, prompt, [],
        lambda: extract_claims(
            done, spark or models.spark, segments, texts, tracks, prompt=prompt, effort=effort, second_pass=second_pass
        ),
    )
    # the schema checks every claim's evidence against the screening's segments, texts and tracks
    return Screening(
        screening_id=screening_id, ad=done.ad, snapshots=SNAPSHOTS,
        stages=(heard_run, read_run, found_run, claims_run), screened_at=datetime.now(UTC),
        segments=segments, on_screen=texts, tracks=tracks, claims=claims,
    )


def screen(
    done: Ingested, models: Models, precedents: PrecedentIndex, screening_id: str | None = None, *,
    judge_prompt: str = judge.PROMPT_VERSION, judge_effort: str = judge.EFFORT, **config,
) -> Screening:
    gathered = gather(done, models, screening_id or default_id(done), **config)
    try:
        return check(gathered, models.spark, precedents, prompt=judge_prompt, effort=judge_effort)
    except Exception as e:
        log.warning("stage check failed: %s", type(e).__name__)
        failed = StageRun(stage="check", status="failed", model=SPARK, prompt=judge_prompt, effort=judge_effort)
        return gathered.model_copy(update={"stages": (*gathered.stages, failed)})


def screen_target(
    target: str, models: Models, precedents: PrecedentIndex, out: Path, *, align: Literal["mms"] | None = "mms"
) -> tuple[Screening, Path, Path]:
    done = capture(target) if target.startswith(("http://", "https://")) else ingest(Path(target))
    screening = screen(done, models, precedents, default_id(done), align=align)
    out.mkdir(parents=True, exist_ok=True)
    stem = out / screening.screening_id
    stem.with_suffix(".json").write_text(screening.model_dump_json(indent=1), encoding="utf-8")
    crops = done.frames[0].path.parent.parent
    stem.with_suffix(".html").write_text(render_html(screening, crops), encoding="utf-8")
    return screening, stem.with_suffix(".json"), stem.with_suffix(".html")
