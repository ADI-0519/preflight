from contextlib import nullcontext

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from test_api import start, wait_for
from test_script import NoMedia, NoPrecedents, ScriptSpark

from preflight.api import Settings, create_app
from preflight.models import Models

COPY = "VO: Treats anxiety\n\nSUPER: <script>alert(1)</script>\n"


def application(root, *, clock=None, spark=None):
    models = Models(spark or ScriptSpark(), NoMedia(), NoMedia(), NoMedia(), None)
    return create_app(Settings(root=root, retention_seconds=10), clock=clock,
                      models_factory=lambda _: nullcontext(models), precedents_factory=NoPrecedents)


def test_script_upload_screening_evidence_report_progress_and_expiry(tmp_path, caplog, monkeypatch):
    import importlib

    api_module = importlib.import_module("preflight.api.app")
    monkeypatch.setattr(api_module, "validate_media", lambda *args: pytest.fail("script invoked FFmpeg validation"))
    clock = [100.0]
    app = application(tmp_path / "private", clock=lambda: clock[0])
    with TestClient(app) as client:
        uploaded = client.post("/uploads", content=COPY.encode(), headers={"Content-Type": "text/markdown"})
        assert uploaded.status_code == 201, uploaded.text
        upload_id = uploaded.json()["upload_id"]
        job_id = start(client, upload_id)
        assert wait_for(client, job_id) == "completed"
        saved = client.get(f"/screenings/{job_id}").json()
        assert saved["schema_version"] == "4" and saved["ad"]["media"] == "script"
        assert saved["claims"][0]["evidence"] == [{"kind": "script", "line_number": 1, "text": "VO: Treats anxiety"}]
        assert saved["flags"][0]["sources"] and "Script only" in saved["headline"]
        report = client.get(f"/screenings/{job_id}/report")
        assert report.status_code == 200 and "Script line 1" in report.text
        view = client.get(f"/ui/jobs/{job_id}").json()
        assert view["claims"][0]["evidence"][0]["line_number"] == 1
        media = client.get(f"/uploads/{upload_id}/media")
        assert media.headers["content-type"].startswith("text/plain")
        assert media.headers["x-content-type-options"] == "nosniff" and media.text == COPY
        progress = client.get(f"/jobs/{job_id}/events").text
        assert "Treats anxiety" not in progress and "alert(1)" not in progress
        fix = client.post("/fixes", json={
            "screening_id": job_id, "format": "image", "scenes": [{"upload_id": upload_id}],
        })
        assert fix.status_code == 409 and fix.json()["error"] == "script_fix_not_supported"
        assert client.get(f"/ui/jobs/{job_id}").json() == view
        storage = app.state.service.storage
        journal = (storage.root / "retention.jsonl").read_text()
        assert "Treats anxiety" not in journal + caplog.text
        clock[0] = 111
        storage.sweep()
        assert not (storage.root / upload_id).exists()
        assert client.get(f"/ui/jobs/{job_id}").status_code in {404, 410}


@pytest.mark.parametrize(("raw", "status"), [(b"\xff", 415), (b"text\x00", 415),
                                             (b" \n\t", 422), (b"x" * 65537, 413)])
def test_invalid_script_never_calls_model_or_retains_source(tmp_path, raw, status):
    spark = ScriptSpark()
    app = application(tmp_path / "private", spark=spark)
    with TestClient(app) as client:
        result = client.post("/uploads", content=raw, headers={"Content-Type": "text/plain"})
        assert result.status_code == status
        assert not spark.calls
        assert not list(app.state.service.storage.root.glob("*/media*"))


@pytest.mark.parametrize(("empty", "broken", "status"), [(True, False, "completed"), (False, True, "incomplete")])
def test_script_clean_and_incomplete_states(tmp_path, empty, broken, status):
    with TestClient(application(tmp_path / "private", spark=ScriptSpark(empty=empty, broken=broken))) as client:
        response = client.post("/uploads", content=COPY.encode(), headers={"Content-Type": "text/plain"})
        upload_id = response.json()["upload_id"]
        job = start(client, upload_id)
        assert wait_for(client, job) == status
        result = client.get(f"/screenings/{job}").json()
        assert "Script only" in result["headline"]
        assert ("No issues found" in result["headline"]) == empty
        assert ("Incomplete" in result["headline"]) == broken


def test_script_result_survives_a_service_restart(tmp_path):
    root = tmp_path / "private"
    with TestClient(application(root, clock=lambda: 100)) as client:
        upload_id = client.post("/uploads", content=COPY.encode(),
                                headers={"Content-Type": "text/plain"}).json()["upload_id"]
        job = start(client, upload_id)
        assert wait_for(client, job) == "completed"
    with TestClient(application(root, clock=lambda: 101)) as restarted:
        result = restarted.get(f"/ui/jobs/{job}")
        assert result.status_code == 200
        assert result.json()["screening"]["script_lines"][0]["line_number"] == 1


def test_public_upload_quota_applies_to_scripts(tmp_path):
    app = create_app(Settings(root=tmp_path / "private", public=True, public_uploads_per_hour=1))
    with TestClient(app) as client:
        assert client.post("/uploads", content=COPY.encode(), headers={"Content-Type": "text/plain"}).status_code == 201
        blocked = client.post("/uploads", content=COPY.encode(), headers={"Content-Type": "text/plain"})
        assert blocked.status_code == 429 and "Treats anxiety" not in blocked.text
