"""Private per-upload storage. The retention journal never contains ad content."""

import json
import math
import re
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

IDENTIFIER = re.compile(r"^[0-9a-f]{32}$")
TERMINAL = {"completed", "incomplete", "failed"}


class APIError(Exception):
    def __init__(self, status: int, code: str):
        self.status, self.code = status, code


@dataclass(frozen=True)
class Settings:
    root: Path = Path("data/raw/uploads")
    retention_seconds: float = 86400
    # a job still running this long after its input expired is taken as hung; a screening takes minutes
    job_grace_seconds: float = 3600
    max_upload_bytes: int = 100 * 1024 * 1024
    max_json_bytes: int = 256 * 1024
    sweep_seconds: float = 30
    workers: int = 2
    max_pending: int = 16

    def __post_init__(self):
        for value in (self.retention_seconds, self.job_grace_seconds, self.sweep_seconds):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("retention and sweep periods must be positive and finite")
        if min(self.max_upload_bytes, self.max_json_bytes, self.workers, self.max_pending) < 1:
            raise ValueError("storage and concurrency limits must be positive")


def write_json(path: Path, fields: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


class Retention:
    def __init__(self, settings: Settings, clock=time.time):
        self.settings, self.clock = settings, clock
        self.root = settings.root.resolve()
        self.lock = threading.RLock()
        self.active: dict[str, int] = {}
        self.jobs: dict[str, dict] = {}

    def upload_dir(self, upload_id: str) -> Path:
        if not IDENTIFIER.fullmatch(upload_id):
            raise APIError(404, "upload_not_found")
        path = self.root / upload_id
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise APIError(404, "upload_not_found")
        return path

    def journal(self, event: str, upload_id: str) -> None:
        record = {"event": event, "upload_id": upload_id, "at": self.clock()}
        with (self.root / "retention.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")

    def start(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock:
            for path in self.root.glob("*/jobs/*/job.json"):
                if not path.resolve().is_relative_to(self.root):
                    continue
                fields = json.loads(path.read_text(encoding="utf-8"))
                self.jobs[fields["job_id"]] = fields
                if fields["status"] not in TERMINAL:
                    self.event(fields["job_id"], "failed", error="worker_interrupted")
            self.sweep()

    def begin(self, media_type: str, suffix: str) -> dict:
        with self.lock:
            upload_id = uuid4().hex
            directory = self.upload_dir(upload_id)
            directory.mkdir()
            fields = {
                "upload_id": upload_id, "media_type": media_type, "suffix": suffix,
                "bytes": 0, "created_at": self.clock(),
                "expires_at": self.clock() + self.settings.retention_seconds, "stored": False,
            }
            write_json(directory / "upload.json", fields)
            self.active[upload_id] = 1
            self.journal("storage_started", upload_id)
            return fields

    def finish(self, fields: dict, size: int) -> dict:
        with self.lock:
            fields = fields | {"bytes": size, "stored": True}
            write_json(self.upload_dir(fields["upload_id"]) / "upload.json", fields)
            self.release((fields["upload_id"],))
            self.journal("stored", fields["upload_id"])
            return fields

    def upload(self, upload_id: str) -> dict:
        path = self.upload_dir(upload_id) / "upload.json"
        if not path.is_file():
            raise APIError(404, "upload_not_found")
        fields = json.loads(path.read_text(encoding="utf-8"))
        if fields["expires_at"] <= self.clock():
            raise APIError(410, "upload_expired")
        if not fields["stored"]:
            raise APIError(409, "upload_not_ready")
        return fields

    def media(self, upload_id: str) -> Path:
        fields = self.upload(upload_id)
        return self.upload_dir(upload_id) / ("media" + fields["suffix"])

    def release(self, upload_ids) -> None:
        for upload_id in upload_ids:
            self.active[upload_id] = max(0, self.active.get(upload_id, 0) - 1)

    def unpin(self, fields: dict) -> None:
        # both the worker and the sweep may unpin a job, and each pin is released once
        with self.lock:
            if fields.pop("pinned", False):
                self.release(fields["upload_ids"])

    def discard(self, upload_id: str) -> None:
        with self.lock:
            self.release((upload_id,))
            self._delete(upload_id)

    def _delete(self, upload_id: str) -> None:
        directory = self.upload_dir(upload_id)
        try:
            shutil.rmtree(directory)
        except OSError:
            self.journal("delete_failed", upload_id)
            raise
        self.journal("deleted", upload_id)
        self.active.pop(upload_id, None)

    def job_dir(self, fields: dict) -> Path:
        return self.upload_dir(fields["upload_ids"][0]) / "jobs" / fields["job_id"]

    def job(self, job_id: str) -> dict:
        if not IDENTIFIER.fullmatch(job_id) or job_id not in self.jobs:
            raise APIError(404, "job_not_found")
        fields = self.jobs[job_id]
        for upload_id in fields["upload_ids"]:
            self.upload(upload_id)
        return fields

    def create_job(self, kind: str, upload_ids: list[str]) -> dict:
        with self.lock:
            if sum(j["status"] not in TERMINAL for j in self.jobs.values()) >= self.settings.max_pending:
                raise APIError(429, "job_queue_full")
            upload_ids = list(dict.fromkeys(upload_ids))
            deadline = min(self.upload(upload_id)["expires_at"] for upload_id in upload_ids)
            fields = {
                "job_id": uuid4().hex, "kind": kind, "upload_ids": upload_ids,
                "expires_at": deadline, "status": "queued", "events": [], "pinned": True,
            }
            self.job_dir(fields).mkdir(parents=True)
            self.jobs[fields["job_id"]] = fields
            for upload_id in upload_ids:
                self.active[upload_id] = self.active.get(upload_id, 0) + 1
            self.event(fields["job_id"], "queued")
            return fields

    def event(self, job_id: str, status: str | None = None, **data) -> None:
        with self.lock:
            fields = self.jobs.get(job_id)
            # a worker outlived by the sweep reports into a job that has already failed or been deleted
            if fields is None or (status and fields["status"] in TERMINAL):
                return
            if status:
                fields["status"] = status
            fields["events"].append({"id": len(fields["events"]) + 1, "status": fields["status"], **data})
            write_json(self.job_dir(fields) / "job.json", fields)

    def sweep(self) -> None:
        with self.lock:
            expired = set()
            for directory in self.root.iterdir():
                if not directory.is_dir() or directory.is_symlink() or not IDENTIFIER.fullmatch(directory.name):
                    continue
                meta = directory / "upload.json"
                deadline = json.loads(meta.read_text(encoding="utf-8"))["expires_at"] if meta.exists() else (
                    directory.stat().st_mtime + self.settings.retention_seconds
                )
                if deadline <= self.clock():
                    expired.add(directory.name)
            for job_id, fields in list(self.jobs.items()):
                expires_at = fields.get("expires_at", 0)
                if expires_at > self.clock():
                    continue
                if fields["status"] not in TERMINAL:
                    if expires_at + self.settings.job_grace_seconds > self.clock():
                        continue
                    # rule 6: a hung job must not keep its input past expiry and grace
                    self.event(job_id, "failed", error="expired_while_running")
                    self.unpin(fields)
                if any(self.active.get(i, 0) for i in fields["upload_ids"]):
                    continue
                try:
                    shutil.rmtree(self.job_dir(fields))
                except FileNotFoundError:
                    pass
                except OSError:
                    self.journal("delete_failed", fields["upload_ids"][0])
                    continue
                del self.jobs[job_id]
            for upload_id in expired:
                if not self.active.get(upload_id, 0):
                    try:
                        self._delete(upload_id)
                    except OSError:
                        # One locked file must not prevent other expired data being removed.
                        continue
