import json
import time
from contextlib import nullcontext
from pathlib import Path

import httpx
import pytest
import yaml
from openai import OpenAI

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from preflight.api import Settings, create_app
from preflight.api.storage import APIError
from preflight.ingest import ingest, run
from preflight.models import Image, Models, Sam, Spark, Store, VoiceTranscribe
from preflight.pipeline import SNAPSHOTS
from preflight.schema import NOTICE, Screening, StageRun

FIXTURES = Path(__file__).parent / "fixtures"
MEDIA = FIXTURES / "models" / "media"
AGENT = FIXTURES / "agent" / "magnesium"
SECRET = "private customer caption must not leak"


class NoPrecedents:
    version = SNAPSHOTS.rulings

    def top(self, query, k=3):
        return []


def wait_for(client, job_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200, response.text
        if response.json()["status"] in {"completed", "incomplete", "failed"}:
            return response.json()["status"]
        time.sleep(0.02)
    pytest.fail("API job did not finish")


def upload(client, data=None, media_type="image/png"):
    response = client.post("/uploads", content=data or (AGENT / "still.png").read_bytes(),
                           headers={"Content-Type": media_type, "X-Filename": SECRET})
    assert response.status_code == 201, response.text
    assert SECRET not in response.text
    return response.json()["upload_id"]


def start(client, upload_id):
    response = client.post("/screenings", json={"upload_id": upload_id})
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


@pytest.fixture
def replay_models():
    def refuse(request):
        raise AssertionError("network is disabled")

    with httpx.Client(transport=httpx.MockTransport(refuse)) as http:
        with OpenAI(api_key="replay-only", http_client=http, max_retries=0) as api:
            store = Store(FIXTURES / "models", "replay")
            yield Models(Spark(store, api), VoiceTranscribe(store, "replay-only", http=http),
                         Sam(store, api), Image(store, api), None)


def replay_ingest(path, out_root):
    # Existing synthetic recordings combine the clip and separate speech fixture.
    done = ingest(path, out_root)
    return done.model_copy(update={"video": MEDIA / "captions.mp4", "audio": MEDIA / "speech.wav"})


# the folders the service hands the draft screener, where its renders go
SCREENER_DIRS: list[Path] = []


def recorded_screener(models, precedents, directory, align=None):
    SCREENER_DIRS.append(directory)

    def replay(draft, screening_id, previous_id):
        number = 0 if previous_id is None else 1
        return Screening.model_validate_json((AGENT / f"round{number}.json").read_text(encoding="utf-8")).model_copy(
            update={"screening_id": screening_id, "previous_id": previous_id}
        )
    return replay


@pytest.fixture
def app(tmp_path_factory, replay_models):
    return create_app(
        Settings(root=tmp_path_factory.mktemp("api") / "uploads"),
        models_factory=lambda directory: nullcontext(replay_models),
        precedents_factory=NoPrecedents, ingester=replay_ingest, draft_screener=recorded_screener,
    )


def test_replayed_upload_screening_progress_and_reconnect(app):
    with TestClient(app) as client:
        upload_id = upload(client, (MEDIA / "captions.mp4").read_bytes(), "video/mp4")
        job_id = start(client, upload_id)
        assert wait_for(client, job_id) == "completed"
        response = client.get(f"/screenings/{job_id}")
        assert response.status_code == 200
        result = Screening.model_validate(response.json())
        assert len(result.claims) == 3
        # the judge reads "Supports your immune system" as a general claim beside the authorised one (CAP 15.2)
        assert {flag.claim_id for flag in result.flags} == {"claim-2"}
        assert all(flag.sources for flag in result.flags)
        assert result.notice == NOTICE
        report = client.get(f"/screenings/{job_id}/report")
        assert report.status_code == 200 and NOTICE in report.text
        assert "CAP Code rule" in report.text
        response = client.get(f"/jobs/{job_id}/events")
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-store"
        events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
        assert [event["id"] for event in events] == list(range(1, len(events) + 1))
        assert {event.get("stage") for event in events if "stage" in event} == {
            "transcribe", "on_screen", "regions", "claims", "check",
        }
        assert events[-1]["status"] == "completed"
        assert "Clinically" not in response.text
        resumed = client.get(f"/jobs/{job_id}/events", headers={"Last-Event-ID": str(events[-2]["id"])})
        assert resumed.text.count("data: ") == 1
        assert client.get(f"/jobs/{job_id}/events", headers={"Last-Event-ID": str(events[-1]["id"])}).text == ""
        assert client.get(f"/jobs/{job_id}/events", headers={"Last-Event-ID": "invalid"}).status_code == 400


def test_fix_and_explicit_human_approval_use_the_existing_loop(app):
    with TestClient(app) as client:
        still = upload(client)
        source = start(client, upload(client, (MEDIA / "captions.mp4").read_bytes(), "video/mp4"))
        assert wait_for(client, source) == "completed"
        draft = yaml.safe_load((AGENT / "draft.yaml").read_text(encoding="utf-8"))
        draft["scenes"][0].pop("still")
        draft["scenes"][0]["upload_id"] = still
        response = client.post("/fixes", json={"screening_id": source, **draft})
        assert response.status_code == 202, response.text
        job_id = response.json()["job_id"]
        assert wait_for(client, job_id) == "completed"
        result = client.get(f"/fixes/{job_id}")
        assert result.status_code == 200, result.text
        assert result.json()["state"] == "awaiting_approval"
        assert result.json()["decision"] is None
        assert not result.json()["screening"]["flags"]
        assert "still" not in result.json()["draft"]["scenes"][0]
        still_url = result.json()["draft"]["scenes"][0]["still_url"]
        assert client.get(still_url).content == (AGENT / "still.png").read_bytes()
        directory = app.state.service.storage.job_dir(app.state.service.storage.jobs[job_id])
        # rule 6: renders go in the job's folder, so they expire with it
        assert SCREENER_DIRS[-1] == directory
        log = directory / "audit.jsonl"
        before = log.read_text(encoding="utf-8")
        assert '"event": "approved"' not in before
        assert client.post(f"/fixes/{job_id}/approve", json={"by": " "}).status_code == 422
        response = client.post(f"/fixes/{job_id}/approve", json={"by": "Ana", "note": "reviewed"})
        assert response.status_code == 200, response.text
        assert response.json()["decision"]["by"] == "Ana"
        assert client.get(f"/fixes/{job_id}").json()["decision"]["by"] == "Ana"
        assert log.read_text(encoding="utf-8").startswith(before)
        assert client.post(f"/fixes/{job_id}/approve", json={"by": "Ben"}).status_code == 409
        storage = app.state.service.storage
        upload_ids = storage.jobs[job_id]["upload_ids"]
        storage.clock = lambda: time.time() + 86401
        storage.sweep()
        assert all(not (storage.root / upload_id).exists() for upload_id in upload_ids)
        assert not directory.exists() and not log.exists()
        assert "Ana" not in (storage.root / "retention.jsonl").read_text()


def test_validation_errors_do_not_echo_private_text_or_paths(app):
    with TestClient(app) as client:
        response = client.post("/fixes", json={"screening_id": SECRET, "unexpected": SECRET})
        assert response.status_code == 422
        assert SECRET not in response.text
        assert client.get("/jobs/../../private").status_code == 404
        assert client.post("/uploads", content=b"invalid", headers={"Content-Type": "image/png"}).status_code == 415
        assert list(app.state.service.storage.root.glob("*/media*")) == []


def test_upload_limit_removes_partial_files_and_logs_no_content(tmp_path):
    root = tmp_path / "uploads"
    app = create_app(Settings(root=root, max_upload_bytes=3))
    with TestClient(app) as client:
        response = client.post("/uploads", content=SECRET.encode(), headers={"Content-Type": "image/png"})
        assert response.status_code == 413
        assert list(root.glob("*/media*")) == []
        assert SECRET not in (root / "retention.jsonl").read_text()
        assert {row["event"] for row in map(json.loads, (root / "retention.jsonl").read_text().splitlines())} == {
            "storage_started", "deleted",
        }


def test_expiry_deletes_uploads_and_all_private_derivatives(tmp_path):
    clock = [100.0]
    root = tmp_path / "uploads"
    app = create_app(Settings(root=root, retention_seconds=10), clock=lambda: clock[0])
    with TestClient(app) as client:
        upload_id = upload(client)
        folder = root / upload_id
        (folder / "cache").mkdir()
        (folder / "cache" / "private.json").write_text(SECRET)
        clock[0] = 111
        with pytest.raises(APIError) as error:
            app.state.service.storage.upload(upload_id)
        assert error.value.status == 410
        app.state.service.storage.sweep()
        assert not folder.exists()
        journal = (root / "retention.jsonl").read_text()
        assert SECRET not in journal
        assert json.loads(journal.splitlines()[-1])["event"] == "deleted"


def test_active_upload_is_not_deleted_until_released(tmp_path):
    clock = [100.0]
    root = tmp_path / "uploads"
    app = create_app(Settings(root=root, retention_seconds=10), clock=lambda: clock[0])
    with TestClient(app) as client:
        upload_id = upload(client)
        storage = app.state.service.storage
        job = storage.create_job("screening", [upload_id])
        clock[0] = 111
        storage.sweep()
        assert (root / upload_id).exists()
        storage.event(job["job_id"], "failed")
        storage.unpin(job)
        storage.sweep()
        assert not (root / upload_id).exists()


def test_hung_job_is_failed_and_its_upload_deleted_after_the_grace_period(tmp_path):
    clock = [100.0]
    root = tmp_path / "uploads"
    app = create_app(Settings(root=root, retention_seconds=10, job_grace_seconds=5), clock=lambda: clock[0])
    with TestClient(app) as client:
        upload_id = upload(client)
        storage = app.state.service.storage
        job = storage.create_job("screening", [upload_id])
        storage.event(job["job_id"], "running")
        clock[0] = 116
        storage.sweep()
        assert not (root / upload_id).exists() and job["job_id"] not in storage.jobs
        assert job["status"] == "failed" and job["events"][-1]["error"] == "expired_while_running"
        # the worker reporting late neither revives the job nor releases another job's pin
        storage.event(job["job_id"], "completed")
        storage.unpin(job)
        assert job["status"] == "failed"


def test_periodic_sweep_survives_a_failed_sweep(tmp_path):
    clock = [100.0]
    root = tmp_path / "uploads"
    app = create_app(Settings(root=root, retention_seconds=10, sweep_seconds=0.02), clock=lambda: clock[0])
    storage = app.state.service.storage
    sweep, calls = storage.sweep, []

    def flaky():
        calls.append(1)
        if len(calls) == 2:
            raise ValueError("bad upload.json")
        sweep()

    storage.sweep = flaky
    with TestClient(app) as client:
        upload_id = upload(client)
        deadline = time.monotonic() + 2
        while len(calls) < 3 and time.monotonic() < deadline:
            time.sleep(0.02)
        clock[0] = 111
        while (root / upload_id).exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not (root / upload_id).exists()


def test_sweep_deletes_a_folder_a_late_worker_recreated(tmp_path):
    root = tmp_path / "uploads"
    app = create_app(Settings(root=root))
    with TestClient(app):
        orphan = root / ("f" * 32) / "jobs" / ("e" * 32) / "ingest"
        orphan.mkdir(parents=True)
        app.state.service.storage.sweep()
        assert not (root / ("f" * 32)).exists()


def test_periodic_retention_sweep_runs_without_an_http_cleanup_call(tmp_path):
    clock = [100.0]
    root = tmp_path / "uploads"
    app = create_app(Settings(root=root, retention_seconds=10, sweep_seconds=0.02), clock=lambda: clock[0])
    with TestClient(app) as client:
        upload_id = upload(client)
        clock[0] = 111
        deadline = time.monotonic() + 2
        while (root / upload_id).exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not (root / upload_id).exists()


def test_restart_marks_unfinished_jobs_failed_and_expires_storage(tmp_path):
    clock = [100.0]
    settings = Settings(root=tmp_path / "uploads", retention_seconds=10)
    first = create_app(settings, clock=lambda: clock[0])
    with TestClient(first) as client:
        upload_id = upload(client)
        job = first.state.service.storage.create_job("screening", [upload_id])
    second = create_app(settings, clock=lambda: clock[0])
    with TestClient(second) as client:
        response = client.get(f'/jobs/{job["job_id"]}')
        assert response.json()["status"] == "failed"
        assert "worker_interrupted" in client.get(f'/jobs/{job["job_id"]}/events').text
    clock[0] = 111
    third = create_app(settings, clock=lambda: clock[0])
    with TestClient(third):
        assert not (settings.root / upload_id).exists()


def test_errors_and_sse_do_not_expose_provider_exceptions(app, caplog):
    def broken(*args):
        raise RuntimeError(SECRET)

    app.state.service.ingester = broken
    with TestClient(app) as client:
        job_id = start(client, upload(client))
        assert wait_for(client, job_id) == "failed"
        events = client.get(f"/jobs/{job_id}/events")
        assert "processing_failed" in events.text
        assert SECRET not in events.text and SECRET not in caplog.text
        assert client.get(f"/screenings/{job_id}").status_code == 409
        assert client.post(f"/fixes/{job_id}/approve", json={"by": "Ana"}).status_code == 409


def test_fixes_reject_forged_register_wording_before_running(app):
    with TestClient(app) as client:
        source = start(client, upload(client, (MEDIA / "captions.mp4").read_bytes(), "video/mp4"))
        assert wait_for(client, source) == "completed"
        storage = app.state.service.storage
        saved = storage.job_dir(storage.jobs[source]) / "screening.json"
        fields = json.loads(saved.read_text(encoding="utf-8"))
        fields["flags"][0]["suggested_wording"] = {"register_id": "gbhc-e1f78000ec6b", "wording": SECRET}
        saved.write_text(json.dumps(fields), encoding="utf-8")
        still = upload(client)
        response = client.post("/fixes", json={
            "screening_id": source, "format": "image", "scenes": [{"upload_id": still}],
        })
        assert response.status_code == 409
        assert SECRET not in response.text
        assert len(storage.jobs) == 1


@pytest.mark.parametrize("status", ["skipped", "failed", None])
def test_incomplete_results_are_visible_without_becoming_successful_jobs(app, monkeypatch, status):
    from preflight.api import service

    def unfinished(done, models, precedents, screening_id, **kwargs):
        stages = (StageRun(stage="claims", status="done"),)
        if status is not None:
            stages += (StageRun(stage="check", status=status),)
        return Screening(screening_id=screening_id, ad=done.ad, snapshots=SNAPSHOTS,
                         stages=stages, screened_at="2026-11-01T00:00:00Z")

    monkeypatch.setattr(service, "screen", unfinished)
    with TestClient(app) as client:
        job_id = start(client, upload(client, (MEDIA / "captions.mp4").read_bytes(), "video/mp4"))
        assert wait_for(client, job_id) == "incomplete"
        response = client.get(f"/screenings/{job_id}")
        assert response.status_code == 200 and response.json()["headline"].startswith("Incomplete")


def test_pending_job_limit_is_enforced_before_more_processing(tmp_path):
    app = create_app(Settings(root=tmp_path / "uploads", max_pending=1))
    with TestClient(app) as client:
        upload_id = upload(client)
        app.state.service.storage.create_job("screening", [upload_id])
        assert client.post("/screenings", json={"upload_id": upload_id}).status_code == 429


def test_json_body_limit_and_unknown_paths_do_not_echo_content(tmp_path):
    app = create_app(Settings(root=tmp_path / "uploads", max_json_bytes=5))
    with TestClient(app) as client:
        response = client.post("/screenings", json={"upload_id": SECRET})
        assert response.status_code == 413 and SECRET not in response.text
        assert client.get("/jobs/" + "f" * 32).status_code == 404


def test_uploaded_playlist_is_not_treated_as_a_video(app):
    playlist = b"#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXTINF:4,\nhttp://127.0.0.1:9/private.ts\n#EXT-X-ENDLIST\n"
    with TestClient(app) as client:
        response = client.post("/uploads", content=playlist, headers={"Content-Type": "video/mp4"})
        assert response.status_code == 415
        assert list(app.state.service.storage.root.glob("*/media*")) == []


@pytest.mark.parametrize("suffix,media_type,source", [
    (".jpg", "image/jpeg", AGENT / "still.png"),
    (".webp", "image/webp", AGENT / "still.png"),
    (".webm", "video/webm", MEDIA / "captions.mp4"),
    (".mov", "video/quicktime", MEDIA / "captions.mp4"),
])
def test_supported_media_formats_decode_before_storage(app, tmp_path, suffix, media_type, source):
    converted = tmp_path / ("synthetic" + suffix)
    run("ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(source), str(converted))
    with TestClient(app) as client:
        upload_id = upload(client, converted.read_bytes(), media_type)
        assert app.state.service.storage.media(upload_id).read_bytes() == converted.read_bytes()


def test_openapi_exposes_binary_upload_and_screening_contracts(app):
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
        binary = schema["paths"]["/uploads"]["post"]["requestBody"]["content"]["image/png"]["schema"]
        assert binary["format"] == "binary"
        assert "Screening" in schema["components"]["schemas"]
        assert "JobView" in schema["components"]["schemas"]
        assert client.get("/health", headers={"Host": "untrusted.example"}).status_code == 400


def test_failed_deletion_is_logged_without_private_details_and_retried(tmp_path, monkeypatch):
    from preflight.api import storage as module

    clock = [100.0]
    root = tmp_path / "uploads"
    app = create_app(Settings(root=root, retention_seconds=10), clock=lambda: clock[0])
    with TestClient(app) as client:
        upload_id = upload(client)
        other_id = upload(client)
        clock[0] = 111
        remove = module.shutil.rmtree

        def fail(path, *args, **kwargs):
            if path == root / upload_id:
                raise OSError(SECRET)
            return remove(path, *args, **kwargs)

        monkeypatch.setattr(module.shutil, "rmtree", fail)
        app.state.service.storage.sweep()
        assert not (root / other_id).exists()
        journal = (root / "retention.jsonl").read_text()
        assert SECRET not in journal and '"delete_failed"' in journal
        monkeypatch.setattr(module.shutil, "rmtree", remove)
        app.state.service.storage.sweep()
        assert not (root / upload_id).exists()


def test_derived_job_deletion_retries_after_its_expired_input_is_gone(tmp_path, monkeypatch):
    from preflight.api import storage as module

    clock = [100.0]
    app = create_app(Settings(root=tmp_path / "uploads", retention_seconds=10), clock=lambda: clock[0])
    with TestClient(app) as client:
        older = upload(client)
        clock[0] = 105
        newer = upload(client)
        storage = app.state.service.storage
        job = storage.create_job("fix", [newer, older])
        storage.event(job["job_id"], "completed")
        storage.release(job["upload_ids"])
        directory = storage.job_dir(job)
        (directory / "private.txt").write_text(SECRET)
        remove = module.shutil.rmtree
        blocked = [True]

        def remove_once(path, *args, **kwargs):
            if path == directory and blocked[0]:
                blocked[0] = False
                raise OSError(SECRET)
            return remove(path, *args, **kwargs)

        monkeypatch.setattr(module.shutil, "rmtree", remove_once)
        clock[0] = 111
        storage.sweep()
        assert not (storage.root / older).exists() and directory.exists()
        storage.sweep()
        assert not directory.exists()
        assert SECRET not in (storage.root / "retention.jsonl").read_text()


def public_app(tmp_path, replay_models, monkeypatch, clock=None, **limits):
    monkeypatch.delenv("PREFLIGHT_PUBLIC_MODE", raising=False)
    return create_app(
        Settings(root=tmp_path / "uploads", public=True, **limits),
        models_factory=lambda directory: nullcontext(replay_models), precedents_factory=NoPrecedents,
        ingester=replay_ingest, draft_screener=recorded_screener, **({"clock": clock} if clock else {}),
    )


def test_public_mode_allows_three_screenings_per_client_an_hour(tmp_path, replay_models, monkeypatch):
    clock = [1_800_000_000.0]
    app = public_app(tmp_path, replay_models, monkeypatch, clock=lambda: clock[0])
    with TestClient(app) as client:
        upload_id = upload(client, (MEDIA / "captions.mp4").read_bytes(), "video/mp4")
        jobs = [start(client, upload_id) for _ in range(3)]
        response = client.post("/screenings", json={"upload_id": upload_id})
        assert response.status_code == 429 and response.json()["error"] == "rate_limited"
        for job_id in jobs:
            wait_for(client, job_id)
        # each job's model usage is counted towards the day's spend, priced from its recorded usage
        assert app.state.service.public.spent() > 0
        clock[0] += 3601
        assert client.post("/screenings", json={"upload_id": upload_id}).status_code == 202


def test_public_mode_allows_one_fix_per_client_an_hour_and_one_round():
    from preflight.api.public import Public

    public = Public(Settings(public=True))
    public.admit("203.0.113.1", "fix")
    with pytest.raises(APIError) as error:
        public.admit("203.0.113.1", "fix")
    assert (error.value.status, error.value.code) == (429, "rate_limited")
    # another client has its own allowance
    public.admit("203.0.113.2", "fix")


def test_public_mode_limits_upload_size_and_video_length(tmp_path, replay_models, monkeypatch):
    small = public_app(tmp_path / "a", replay_models, monkeypatch, public_max_upload_bytes=3)
    with TestClient(small) as client:
        response = client.post("/uploads", content=SECRET.encode(), headers={"Content-Type": "image/png"})
        assert response.status_code == 413
        assert client.get("/ui/config").json()["max_upload_bytes"] == 3
    short = public_app(tmp_path / "b", replay_models, monkeypatch, public_max_seconds=0.5)
    with TestClient(short) as client:
        response = client.post("/uploads", content=(MEDIA / "captions.mp4").read_bytes(),
                               headers={"Content-Type": "video/mp4"})
        assert response.status_code == 422 and response.json()["error"] == "media_too_long"
        assert list((tmp_path / "b" / "uploads").glob("*/media*")) == []


def test_daily_spend_cap_refuses_uploads_until_the_next_day(tmp_path, replay_models, monkeypatch):
    clock = [1_800_000_000.0]
    app = public_app(tmp_path, replay_models, monkeypatch, clock=lambda: clock[0], daily_cap_usd=1.0)
    with TestClient(app) as client:
        upload_id = upload(client)
        app.state.service.public.spend(1.0)
        response = client.post("/uploads", content=(AGENT / "still.png").read_bytes(),
                               headers={"Content-Type": "image/png"})
        assert response.status_code == 503 and response.json()["error"] == "daily_cap_reached"
        assert client.post("/screenings", json={"upload_id": upload_id}).status_code == 503
        assert client.get("/ui/config").json()["uploads_closed"] == "daily_cap_reached"
        # the preloaded demos still run, from replay
        assert client.get("/ui/demos").status_code == 200
        clock[0] += 86400
        assert client.get("/ui/config").json()["uploads_closed"] is None
        upload(client)


def test_replay_switch_turns_uploads_off_without_public_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("PREFLIGHT_PUBLIC_MODE", "replay")
    app = create_app(Settings(root=tmp_path / "uploads"))
    with TestClient(app) as client:
        response = client.post("/uploads", content=(AGENT / "still.png").read_bytes(),
                               headers={"Content-Type": "image/png"})
        assert response.status_code == 503 and response.json()["error"] == "uploads_paused"
        config = client.get("/ui/config").json()
        assert (config["public_mode"], config["uploads_closed"]) == ("replay", "uploads_paused")
        assert "Do not upload confidential ads" in config["upload_notice"]
        assert client.get("/ui/demos").status_code == 200
    monkeypatch.setenv("PREFLIGHT_PUBLIC_MODE", "off")
    with TestClient(app) as client:
        assert client.get("/ui/config").json()["uploads_closed"] is None


def test_public_approval_is_recorded_as_a_demo_approval(tmp_path, replay_models, monkeypatch):
    app = public_app(tmp_path, replay_models, monkeypatch)
    with TestClient(app) as client:
        still = upload(client)
        source = start(client, upload(client, (MEDIA / "captions.mp4").read_bytes(), "video/mp4"))
        assert wait_for(client, source) == "completed"
        draft = yaml.safe_load((AGENT / "draft.yaml").read_text(encoding="utf-8"))
        draft["scenes"][0].pop("still")
        draft["scenes"][0]["upload_id"] = still
        response = client.post("/fixes", json={"screening_id": source, **draft, "rounds": 3})
        assert response.status_code == 202, response.text
        job_id = response.json()["job_id"]
        assert wait_for(client, job_id) == "completed"
        directory = app.state.service.storage.job_dir(app.state.service.storage.jobs[job_id])
        records = map(json.loads, (directory / "audit.jsonl").read_text().splitlines())
        rounds = [r for r in records if r["event"] == "round"]
        # three rounds were asked for; public mode allows one fix round after the first screening
        assert max(r["round"] for r in rounds) <= 1
        response = client.post(f"/fixes/{job_id}/approve", json={"by": "Visitor"})
        assert response.status_code == 200, response.text
        assert response.json()["decision"]["public_demo"] is True
        log = (directory / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        assert json.loads(log[-1]) | {"at": None} == json.loads(log[-1]) | {"at": None, "public_demo": True}
