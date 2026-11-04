"""Read-only presentation of verified screenings; no model or policy decisions."""

import csv
import json
import math
import mimetypes
import re
from functools import cache
from pathlib import Path
from typing import Literal

from fastapi import Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from preflight.agent.fix import read_log
from preflight.api.public import UPLOAD_NOTICE
from preflight.api.storage import APIError
from preflight.ingest import MAX_SECONDS
from preflight.ingest.script import SCRIPT_SUFFIXES
from preflight.schema import NOTICE, Screening, register_entries, verify_sources
from preflight.sources.cap import CapRule, load_cap_rules
from preflight.sources.on_hold import OnHoldClaim, load_on_hold
from preflight.sources.rulings import RulingMeta, load_ruling_index
from preflight.view import TIERS, build_view, first_time

ROOT = Path(__file__).resolve().parents[3]


def inside(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root.resolve()) or not path.is_file():
        raise APIError(404, "asset_not_available")
    return path


MEDIA_SLICE = 8 * 1024 * 1024


def media_response(path: Path, request: Request) -> Response:
    size = path.stat().st_size
    headers = {"Accept-Ranges": "bytes", "X-Content-Type-Options": "nosniff"}
    media_type = "text/plain" if path.suffix.lower() in SCRIPT_SUFFIXES else (
        mimetypes.guess_type(path)[0] or "application/octet-stream"
    )
    value = request.headers.get("range")
    start, end, status = 0, size - 1, 200
    if value:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
        if len(value) > 200 or not match or not any(match.groups()):
            return Response(status_code=416, headers=headers | {"Content-Range": f"bytes */{size}"})
        first, last = match.groups()
        start = int(first) if first else max(0, size - int(last))
        end = min(int(last), size - 1) if first and last else size - 1
        # Cloud Run refuses a response over 32 MiB; a shorter range reply is valid and the player asks for the rest
        end = min(end, start + MEDIA_SLICE - 1)
        if start >= size or end < start:
            return Response(status_code=416, headers=headers | {"Content-Range": f"bytes */{size}"})
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
        status = 206
    # read the slice while the caller holds the retention lock: no open file survives local expiry
    with path.open("rb") as f:
        f.seek(start)
        body = f.read(end - start + 1)
    return Response(body, status_code=status, headers=headers, media_type=media_type)


@cache
def ruling_lookup(version: str) -> dict[str, RulingMeta]:
    return {e.ruling_id: e for e in load_ruling_index(version)}


@cache
def cap_rule_lookup(version: str) -> dict[str, CapRule]:
    return load_cap_rules(version).rules


@cache
def on_hold_lookup(version: str) -> dict[str, OnHoldClaim]:
    return {e.on_hold_id: e for e in load_on_hold(version)}


def presentation(screening: Screening, crop_base: str) -> dict:
    verify_sources(screening)
    snapshots = screening.snapshots
    caps = cap_rule_lookup(snapshots.cap_rules)
    register = register_entries(snapshots.gb_register)
    held = on_hold_lookup(snapshots.on_hold)
    rulings = ruling_lookup(snapshots.rulings)

    def source(ref):
        if ref.kind == "cap_rule":
            rule = caps[ref.rule]
            return {"label": f"CAP {rule.rule}", "text": rule.summary, "url": rule.url}
        if ref.kind == "register":
            entry = register[ref.register_id]
            return {"label": f"GB register {ref.register_id}", "text": entry.wording, "url": None}
        if ref.kind == "on_hold":
            entry = held[ref.on_hold_id]
            return {"label": f"On-hold list {ref.on_hold_id}", "text": entry.substance, "url": None}
        ruling = rulings[ref.ruling_id]
        return {"label": f"ASA {ref.ruling_id} · {ruling.date}", "text": ruling.advertiser, "url": ruling.url}

    kinds = {"transcript": "Spoken", "on_screen": "On screen", "region": "Image region", "script": "Script line"}

    def evidence(item: dict) -> dict:
        crop_url = None
        if item["kind"] == "region" and item["crop"]:
            ti, track = next((i, t) for i, t in enumerate(screening.tracks) if t.track_id == item["track_id"])
            ri = next(i for i, r in enumerate(track.regions) if r.frame_time == item["frame_time"])
            crop_url = f"{crop_base}/{ti}/{ri}"
        start = item["start"] if item["frame_time"] is None else item["frame_time"]
        end = item["end"] if item["frame_time"] is None else item["frame_time"]
        return {"kind": kinds[item["kind"]], "start": start, "end": end, "text": item["text"],
                "line_number": item.get("line_number"),
                "timing": item["timing"], "timed": item["timed"], "crop_url": crop_url}

    flags = {f.flag_id: f for f in screening.flags}

    def flag(flag_id: str) -> dict:
        f = flags[flag_id]
        return f.model_dump(mode="json") | {"source_details": [source(s) for s in f.sources]}

    def row(claim_id: str, text: str, shown: list[dict], line: dict | None, tier: str | None) -> dict:
        return {
            "claim_id": claim_id, "text": text, "start": first_time(shown), "tier": tier,
            "substance": line["substance"] if line else None,
            "evidence": [evidence(e) for e in shown],
            "flags": [flag(i) for i in line["flags"]["flag_ids"]] if line else [],
            "rules": {"primary": line["primary_rules"], "other": line["other_rules"]} if line else None,
            "folded": [{"claim_id": n["claim_id"], "text": n["text"], "flags": [flag(i) for i in n["flag_ids"]]}
                       for n in line["folded"]] if line else [],
        }

    view = build_view(screening)
    # one row per flagged line, with its nested phrases folded in, and one per unflagged claim
    rows = [row(line["claim_id"], line["text"], line["evidence"], line, line["tier"]) for line in view["lines"]]
    rows += [row(c["claim_id"], c["text"], c["evidence"], None, c["tier"]) for c in view["quiet_claims"]]
    rows.sort(key=lambda r: (TIERS.index(r["tier"]) if r["tier"] else len(TIERS), r["start"] is None, r["start"] or 0))
    return {"screening": screening.model_dump(mode="json"), "claims": rows, "may_say": view["may_say"],
            "incomplete_stages": view["incomplete_stages"], "tiers": view["tiers"]}


def crop_path(screening: Screening, root: Path, track: int, region: int) -> Path:
    if track < 0 or region < 0:
        raise APIError(404, "crop_not_available")
    try:
        name = screening.tracks[track].regions[region].crop
    except IndexError:
        raise APIError(404, "crop_not_available") from None
    if not name:
        raise APIError(404, "crop_not_available")
    return inside(root, name)


def scoreboard(root: Path) -> dict:
    unavailable = {"available": False, "reason": "No registered final test run is selected.", "metrics": []}
    final, registry = root / "final.md", root / "runs.csv"
    if not final.is_file() or not registry.is_file():
        return unavailable
    # Explicit selector avoids guessing which of several historical run IDs is final.
    try:
        text = final.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return unavailable
    selected = re.findall(r"^run_id:[ \t]*([A-Za-z0-9_-]+)[ \t]*$", text, re.MULTILINE)
    if len(selected) != 1:
        return unavailable
    run_id = selected[0]
    metadata = ("created_at", "git_sha", "split", "part", "stage", "model", "prompt", "effort", "snapshots")
    required = {*metadata, "run_id", "metric", "hits", "total", "low", "high"}
    try:
        with registry.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if not required.issubset(reader.fieldnames or []):
                return unavailable
            rows = [r for r in reader if r["run_id"] == run_id]
    except (OSError, UnicodeError, csv.Error):
        return unavailable
    if any(any(not isinstance(row.get(k), str) for k in required) for row in rows):
        return unavailable
    if not rows or any(r["part"] != "test" or r["stage"] != "screen" for r in rows):
        return unavailable
    if not re.fullmatch(r"[0-9a-f]{7,40}", rows[0]["git_sha"]):
        return unavailable
    if any(any(row[k] != rows[0][k] for k in metadata) for row in rows):
        return unavailable
    metrics = []
    try:
        for row in rows:
            if row["metric"] not in {"ad_recall", "claim_recall", "claim_recall_carried",
                                     "claim_recall_any_rule", "negative_ads_flagged"}:
                continue
            hits, total = float(row["hits"]), float(row["total"])
            low = float(row["low"]) if row["low"] else None
            high = float(row["high"]) if row["high"] else None
            if not all(math.isfinite(n) for n in (hits, total, low or 0, high or 0)) or not 0 <= hits <= total:
                return unavailable
            if (low is None) != (high is None) or (low is not None and not 0 <= low <= high <= 1):
                return unavailable
            metrics.append({"name": row["metric"], "hits": hits, "total": total, "low": low, "high": high})
    except (ValueError, KeyError):
        return unavailable
    if not metrics or len({m["name"] for m in metrics}) != len(metrics):
        return unavailable
    return {"available": True, "run_id": run_id, **{k: rows[0][k] for k in metadata}, "metrics": metrics}


class DemoEntry(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]{1,60}$")
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["synthetic", "reconstruction"]
    media: str = Field(min_length=1)
    screening: str = Field(min_length=1)
    crops: str = "crops"
    ruling_id: str | None = None

    @model_validator(mode="after")
    def ruling_matches_kind(self):
        if (self.kind == "reconstruction") != bool(self.ruling_id):
            raise ValueError("only reconstructions name a ruling")
        return self


class Demos:
    """Operator-supplied, labelled assets; never discovers uploads or evaluation labels."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def entries(self) -> list[dict]:
        manifest = self.root / "items.json"
        if not manifest.is_file():
            return []
        try:
            fields = json.loads(manifest.read_text(encoding="utf-8"))
            if not isinstance(fields, list):
                raise ValueError("demo manifest must be a list")
            entries = [DemoEntry.model_validate(e).model_dump() for e in fields]
            if len({e["id"] for e in entries}) != len(entries):
                raise ValueError("demo IDs must be unique")
        except (ValueError, OSError):
            raise APIError(409, "invalid_demo_manifest") from None
        return entries

    def entry(self, identifier: str) -> dict:
        found = next((e for e in self.entries() if e["id"] == identifier), None)
        if found is None:
            raise APIError(404, "demo_not_available")
        return found

    def result(self, entry: dict) -> Screening:
        screening = Screening.model_validate_json(inside(self.root, entry["screening"]).read_text(encoding="utf-8"))
        verify_sources(screening)
        return screening


def install_web(app, service, *, web_root: Path, demo_root: Path, results_root: Path) -> None:
    storage = service.storage
    demos = Demos(demo_root)

    @app.get("/ui/config")
    def configuration():
        public, retention = service.public, storage.settings.retention_seconds
        return {"notice": NOTICE, "max_upload_bytes": public.max_upload_bytes(),
                "max_seconds": public.max_seconds(MAX_SECONDS), "public_mode": public.mode,
                "upload_notice": UPLOAD_NOTICE.format(hours=retention / 3600), "uploads_closed": public.closed(),
                "retention_seconds": retention, "scoreboard": scoreboard(results_root),
                "verification_label": getattr(app.state, "verification_label", None),
                "auth": app.state.auth.client_config()}

    @app.get("/uploads/{upload_id}/media")
    def media(upload_id: str, request: Request):
        with storage.lock:
            return media_response(storage.media(upload_id), request)

    @app.get("/ui/jobs/{job_id}")
    def details(job_id: str):
        with storage.lock:
            job = storage.job(job_id)
            view = presentation(service.result(job_id), f"/ui/jobs/{job_id}/crops")
            if job["kind"] == "screening":
                view["media_url"] = f'/uploads/{job["upload_ids"][0]}/media'
            return view

    @app.get("/ui/jobs/{job_id}/crops/{track}/{region}")
    def crop(job_id: str, track: int, region: int, request: Request):
        with storage.lock:
            result = service.result(job_id)
            root = storage.job_dir(storage.job(job_id)) / "ingest" / result.ad.content_hash
            return media_response(crop_path(result, root, track, region), request)

    def rounds(job_id: str) -> list[dict]:
        service.fix_result(job_id)
        job = storage.job(job_id)
        directory = storage.job_dir(job)
        views = []
        for record in read_log(directory / "audit.jsonl"):
            if record["event"] != "round":
                continue
            result = Screening.model_validate_json(inside(directory, record["screening_id"] + ".json").read_text(
                encoding="utf-8"))
            verify_sources(result)
            draft = record["draft"]
            views.append({"round": record["round"], "screening": result.model_dump(mode="json"),
                          "format": draft["format"], "scenes": [{k: v for k, v in s.items() if k != "still"}
                                                                   for s in draft["scenes"]],
                          "substitutions": record["substitutions"],
                          "media_url": f'/ui/fixes/{job_id}/rounds/{record["round"]}/media'})
        return views

    @app.get("/ui/fixes/{job_id}/rounds")
    def fix_rounds(job_id: str):
        with storage.lock:
            return rounds(job_id)

    @app.get("/ui/fixes/{job_id}/rounds/{number}/media")
    def round_media(job_id: str, number: int, request: Request):
        with storage.lock:
            service.fix_result(job_id)
            directory = storage.job_dir(storage.job(job_id))
            record = next((r for r in read_log(directory / "audit.jsonl")
                           if r["event"] == "round" and r["round"] == number), None)
            if record is None:
                raise APIError(404, "round_not_available")
            suffix = "mp4" if record["draft"]["format"] == "video" else "png"
            return media_response(inside(directory, f'renders/{record["digest"][:16]}/draft.{suffix}'), request)

    @app.get("/ui/demos")
    def demo_items():
        return [{"id": e["id"], "title": e["title"], "kind": e["kind"], "ruling_id": e.get("ruling_id")}
                for e in demos.entries()]

    @app.get("/ui/demos/{identifier}")
    def demo(identifier: str):
        entry = demos.entry(identifier)
        result = demos.result(entry)
        return presentation(result, f"/ui/demos/{identifier}/crops") | {
            "media_url": f"/ui/demos/{identifier}/media", "kind": entry["kind"], "title": entry["title"],
        }

    @app.get("/ui/demos/{identifier}/media")
    def demo_media(identifier: str, request: Request):
        return media_response(inside(demos.root, demos.entry(identifier)["media"]), request)

    @app.get("/ui/demos/{identifier}/crops/{track}/{region}")
    def demo_crop(identifier: str, track: int, region: int, request: Request):
        entry = demos.entry(identifier)
        result = demos.result(entry)
        root = inside(demos.root, entry["screening"]).parent / entry.get("crops", "crops")
        if not root.resolve().is_relative_to(demos.root):
            raise APIError(404, "asset_not_available")
        return media_response(crop_path(result, root, track, region), request)

    @app.get("/ui/demos/{identifier}/reveal")
    def reveal(identifier: str):
        entry = demos.entry(identifier)
        if entry["kind"] == "synthetic":
            return {"kind": "synthetic", "message": "Team-made synthetic fixture. No ASA outcome exists."}
        result = demos.result(entry)
        ruling = ruling_lookup(result.snapshots.rulings).get(entry.get("ruling_id"))
        if ruling is None:
            raise APIError(409, "ruling_not_available")
        return {"kind": "reconstruction", "ruling_id": ruling.ruling_id, "date": str(ruling.date),
                "outcome": ruling.outcome, "rules": ruling.cap_rules, "url": ruling.url}

    @app.get("/login", include_in_schema=False)
    @app.get("/signup", include_in_schema=False)
    @app.get("/", include_in_schema=False)
    def index():
        if not (web_root / "index.html").is_file():
            raise APIError(503, "web_build_missing")
        return FileResponse(web_root / "index.html", headers={"Content-Security-Policy": app.state.auth.page_policy()})

    if (web_root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=web_root / "assets"), name="web-assets")
