"""Job orchestration only; policy decisions remain in screen() and fix()."""

import json
import mimetypes
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

from preflight.agent import Draft, DraftScene, DraftScreener, approve, fix, is_clean
from preflight.agent.fix import read_log
from preflight.api.storage import APIError, Retention, Settings, write_json
from preflight.check.precedents import load_precedents
from preflight.ingest import ingest
from preflight.models import Store, from_env
from preflight.pipeline import SNAPSHOTS, screen
from preflight.report import render_html
from preflight.schema import Screening, StageRun, verify_sources


def completed(screening: Screening) -> bool:
    return any(r.stage == "check" and r.status == "done" for r in screening.stages) and all(
        r.status != "failed" for r in screening.stages
    )


@contextmanager
def private_models(directory: Path):
    models = from_env(Store(directory / "cache"))
    try:
        yield models
    finally:
        clients = {id(c.api): c.api for c in (models.spark, models.sam, models.image, models.glimmer) if c is not None}
        for client in clients.values():
            client.close()


class Service:
    def __init__(
        self, settings: Settings, *, clock=None, models_factory=private_models, precedents_factory=None,
        ingester=ingest, draft_screener=DraftScreener,
    ):
        self.storage = Retention(settings, **({"clock": clock} if clock else {}))
        self.models_factory, self.ingester, self.draft_screener = models_factory, ingester, draft_screener
        self.precedents_factory = precedents_factory or (lambda: load_precedents(SNAPSHOTS.rulings))
        self.executor = ThreadPoolExecutor(max_workers=settings.workers, thread_name_prefix="preflight-api")

    def stage(self, job_id: str, stage: StageRun) -> None:
        if stage.stage in {"transcribe", "on_screen", "regions", "claims", "check"}:
            self.storage.event(job_id, stage=stage.stage, stage_status=stage.status)

    def submit(self, kind: str, upload_ids: list[str], call: Callable) -> dict:
        job = self.storage.create_job(kind, upload_ids)

        def work():
            directory = self.storage.job_dir(job)
            try:
                self.storage.event(job["job_id"], "running")
                result = call(job, directory)
                verify_sources(result)
                (directory / "screening.json").write_text(result.model_dump_json(), encoding="utf-8")
                self.storage.event(job["job_id"], "completed" if completed(result) else "incomplete")
            except Exception:
                # Provider/validation exceptions can contain captions, keys or paths.
                self.storage.event(job["job_id"], "failed", error="processing_failed")
            finally:
                self.storage.unpin(job)

        try:
            self.executor.submit(work)
        except RuntimeError:
            with self.storage.lock:
                self.storage.event(job["job_id"], "failed", error="worker_unavailable")
                self.storage.unpin(job)
            raise APIError(503, "worker_unavailable") from None
        return job

    def start_screening(self, upload_id: str, align: bool) -> dict:
        path = self.storage.media(upload_id)

        def call(job, directory):
            done = self.ingester(path, directory / "ingest")
            with self.models_factory(directory) as models:
                return screen(
                    done, models, self.precedents_factory(), job["job_id"], align="mms" if align else None,
                    on_stage=lambda stage: self.stage(job["job_id"], stage),
                )

        return self.submit("screening", [upload_id], call)

    def result(self, job_id: str) -> Screening:
        with self.storage.lock:
            job = self.storage.job(job_id)
            path = self.storage.job_dir(job) / "screening.json"
            if not path.is_file():
                raise APIError(409, "result_not_available")
            try:
                result = Screening.model_validate_json(path.read_text(encoding="utf-8"))
                verify_sources(result)
            except (ValueError, KeyError, FileNotFoundError):
                raise APIError(409, "invalid_screening_sources") from None
            return result

    def start_fix(self, source_id: str, fields: dict) -> dict:
        with self.storage.lock:
            source = self.storage.job(source_id)
            if source["kind"] != "screening":
                raise APIError(409, "screening_required")
            self.result(source_id)
            upload_ids = [source["upload_ids"][0], *(s["upload_id"] for s in fields["scenes"])]
            scenes = []
            for scene in fields["scenes"]:
                meta = self.storage.upload(scene["upload_id"])
                if not meta["media_type"].startswith("image/"):
                    raise APIError(422, "draft_still_required")
                scenes.append(DraftScene(still=self.storage.media(scene["upload_id"]), **{
                    key: scene[key] for key in ("on_screen_text", "voiceover", "duration_seconds")
                }))
            draft = Draft(format=fields["format"], scenes=tuple(scenes))

            def call(job, directory):
                with self.models_factory(directory) as models:
                    screener = self.draft_screener(
                        models, self.precedents_factory(), directory, align="mms" if fields["align"] else None,
                    )
                    result = fix(
                        draft, screen_draft=screener, image=models.image, rounds=fields["rounds"],
                        log=directory / "audit.jsonl", work_dir=directory,
                    )
                    verify_sources(result.screening)
                    write_json(directory / "fix.json", {
                        "state": result.state, "draft": result.draft.model_dump(mode="json"), "open": result.open,
                    })
                    return result.screening

            return self.submit("fix", upload_ids, call)

    def report(self, job_id: str) -> str:
        with self.storage.lock:
            job = self.storage.job(job_id)
            result = self.result(job_id)
            crops = self.storage.job_dir(job) / "ingest" / result.ad.content_hash
            return render_html(result, crops)

    def fix_result(self, job_id: str) -> dict:
        with self.storage.lock:
            job = self.storage.job(job_id)
            if job["kind"] != "fix":
                raise APIError(409, "fix_required")
            result = self.result(job_id)
            fields = json.loads((self.storage.job_dir(job) / "fix.json").read_text(encoding="utf-8"))
            # Paths stay in private storage, never in HTTP responses.
            for index, scene in enumerate(fields["draft"]["scenes"]):
                scene.pop("still")
                scene["still_url"] = f"/fixes/{job_id}/stills/{index}"
            records = read_log(self.storage.job_dir(job) / "audit.jsonl")
            decision = records[-1] if records and records[-1]["event"] == "approved" else None
            return fields | {"screening": result.model_dump(mode="json"), "decision": decision}

    def still(self, job_id: str, index: int) -> tuple[bytes, str]:
        with self.storage.lock:
            job = self.storage.job(job_id)
            self.fix_result(job_id)
            fields = json.loads((self.storage.job_dir(job) / "fix.json").read_text(encoding="utf-8"))
            if not 0 <= index < len(fields["draft"]["scenes"]):
                raise APIError(404, "still_not_found")
            path = Path(fields["draft"]["scenes"][index]["still"]).resolve()
            if not path.is_relative_to(self.storage.root) or not path.is_file():
                raise APIError(409, "still_not_available")
            return path.read_bytes(), mimetypes.guess_type(path)[0] or "application/octet-stream"

    def approve(self, job_id: str, by: str, note: str) -> dict:
        with self.storage.lock:
            job = self.storage.job(job_id)
            if job["kind"] != "fix" or job["status"] != "completed":
                raise APIError(409, "completed_fix_required")
            result = self.result(job_id)
            if not completed(result) or not is_clean(result):
                raise APIError(409, "human_review_required")
            try:
                record = approve(self.storage.job_dir(job) / "audit.jsonl", by, note)
            except ValueError:
                raise APIError(409, "approval_not_available") from None
            self.storage.event(job_id, human_approval_recorded=True)
            return record
