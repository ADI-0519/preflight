import csv
import json
from contextlib import nullcontext
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from test_api import (  # noqa: F401
    AGENT,
    MEDIA,
    NoPrecedents,
    recorded_screener,
    replay_ingest,
    replay_models,
    start,
    upload,
    wait_for,
)

from preflight.api import Settings, create_app
from preflight.api.web import presentation, scoreboard
from preflight.schema import NOTICE, Screening
from preflight.sources.rulings import load_ruling_index


@pytest.fixture
def replay_app(request, tmp_path_factory):
    models = request.getfixturevalue("replay_models")
    return create_app(Settings(root=tmp_path_factory.mktemp("web") / "uploads"),
                      models_factory=lambda directory: nullcontext(models), precedents_factory=NoPrecedents,
                      ingester=replay_ingest, draft_screener=recorded_screener)


def test_web_build_is_served_without_exposing_workspace(tmp_path):
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<title>PreFlight</title>")
    (web / "assets/app.js").write_text("/* public bundle */")
    with TestClient(create_app(Settings(root=tmp_path / "uploads"), web_root=web)) as client:
        response = client.get("/")
        assert response.status_code == 200 and "PreFlight" in response.text
        assert "default-src 'self'" in response.headers["content-security-policy"]
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/.env").status_code == 404
        assert client.get("/web/schema.json").status_code == 404
        config = client.get("/ui/config").json()
        assert config["notice"] == NOTICE
        assert config["verification_label"] is None


def test_missing_build_has_a_clear_status(tmp_path):
    with TestClient(create_app(Settings(root=tmp_path / "uploads"), web_root=tmp_path / "absent")) as client:
        assert client.get("/").status_code == 503


def test_private_media_ranges_and_expiry(tmp_path):
    clock = [100.0]
    settings = Settings(root=tmp_path / "uploads", retention_seconds=10)
    with TestClient(create_app(settings, clock=lambda: clock[0])) as client:
        content = (MEDIA / "captions.mp4").read_bytes()
        identifier = upload(client, content, "video/mp4")
        url = f"/uploads/{identifier}/media"
        for value, expected in [("bytes=0-15", content[:16]), ("bytes=-12", content[-12:]),
                                ("bytes=12-", content[12:])]:
            response = client.get(url, headers={"Range": value})
            assert response.status_code == 206 and response.content == expected
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["accept-ranges"] == "bytes"
        for value in ("bytes=999999999-", "bytes=8-2", "bytes=0-1,4-5", "bytes=-0"):
            assert client.get(url, headers={"Range": value}).status_code == 416
        clock[0] = 111
        assert client.get(url).status_code == 410


def test_presentation_preserves_evidence_and_sources_and_confines_crops(replay_app):
    app = replay_app
    with TestClient(app) as client:
        identifier = start(client, upload(client, (MEDIA / "captions.mp4").read_bytes(), "video/mp4"))
        assert wait_for(client, identifier) == "completed"
        response = client.get(f"/ui/jobs/{identifier}")
        assert response.status_code == 200
        result = response.json()
        flagged = next(c for c in result["claims"] if c["flags"])
        assert flagged["evidence"] and flagged["flags"][0]["source_details"]
        assert result["screening"]["notice"] == NOTICE
        assert result["media_url"].startswith("/uploads/")
        for evidence in flagged["evidence"]:
            assert evidence["start"] >= 0 and evidence["text"]
        assert client.get(f"/ui/jobs/{identifier}/crops/-1/0").status_code == 404
        storage = app.state.service.storage
        saved = storage.job_dir(storage.jobs[identifier]) / "screening.json"
        fields = json.loads(saved.read_text(encoding="utf-8"))
        region = fields["tracks"][0]["regions"][0]
        region["crop"] = "../../../../../../../.env"
        saved.write_text(json.dumps(fields), encoding="utf-8")
        assert client.get(f"/ui/jobs/{identifier}/crops/0/0").status_code == 404


def test_round_history_is_source_checked_and_does_not_return_paths(replay_app):
    app = replay_app
    with TestClient(app) as client:
        source = start(client, upload(client, (MEDIA / "captions.mp4").read_bytes(), "video/mp4"))
        assert wait_for(client, source) == "completed"
        response = client.post("/fixes", json={"screening_id": source, "format": "image", "scenes": [{
            "upload_id": upload(client), "on_screen_text": ["Beats fatigue in seven days"],
        }]})
        identifier = response.json()["job_id"]
        assert wait_for(client, identifier) == "completed"
        response = client.get(f"/ui/fixes/{identifier}/rounds")
        assert response.status_code == 200
        rows = response.json()
        assert [r["round"] for r in rows] == [0, 1]
        assert rows[0]["screening"]["flags"] and not rows[1]["screening"]["flags"]
        assert '"still"' not in response.text and str(AGENT) not in response.text
        assert client.get(f"/ui/fixes/{identifier}/rounds/99/media").status_code == 404
        directory = app.state.service.storage.job_dir(app.state.service.storage.jobs[identifier])
        log = [json.loads(line) for line in (directory / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
        digests = {r["round"]: r["digest"] for r in log if r["event"] == "round"}
        for row in rows:
            # where render_draft puts a draft: named by its digest, inside the job folder
            render = directory / "renders" / digests[row["round"]][:16] / "draft.png"
            render.parent.mkdir(parents=True)
            render.write_bytes(b"render-%d" % row["round"])
        for row in rows:
            assert client.get(row["media_url"]).content == b"render-%d" % row["round"]
        saved = directory / (rows[0]["screening"]["screening_id"] + ".json")
        fields = json.loads(saved.read_text(encoding="utf-8"))
        fields["flags"][0]["suggested_wording"]["wording"] = "forged wording"
        saved.write_text(json.dumps(fields), encoding="utf-8")
        assert client.get(f"/ui/fixes/{identifier}/rounds").status_code != 200


def test_demo_reveal_uses_snapshot_metadata_and_asset_paths_are_confined(tmp_path):
    root = tmp_path / "demos"
    root.mkdir()
    (root / "screening.json").write_bytes((AGENT / "round0.json").read_bytes())
    (root / "ad.png").write_bytes((AGENT / "still.png").read_bytes())
    entries = [{"id": "synthetic", "title": "Synthetic fixture", "kind": "synthetic", "media": "ad.png",
                "screening": "screening.json"}]
    (root / "items.json").write_text(json.dumps(entries))
    with TestClient(create_app(Settings(root=tmp_path / "uploads"), demo_root=root)) as client:
        assert client.get("/ui/demos").json()[0]["kind"] == "synthetic"
        assert client.get("/ui/demos/synthetic").status_code == 200
        assert "No ASA outcome" in client.get("/ui/demos/synthetic/reveal").json()["message"]
        entries[0]["media"] = "../outside.png"
        (root / "items.json").write_text(json.dumps(entries))
        (tmp_path / "outside.png").write_bytes(b"private")
        assert client.get("/ui/demos/synthetic/media").status_code == 404


def test_reconstruction_outcome_comes_from_committed_metadata(tmp_path):
    root = tmp_path / "demos"
    root.mkdir()
    (root / "screening.json").write_bytes((AGENT / "round0.json").read_bytes())
    ruling = load_ruling_index("2026-11-01")[0]
    entries = [{"id": "reconstruction", "title": "Explicit test manifest", "kind": "reconstruction",
                "ruling_id": ruling.ruling_id, "screening": "screening.json", "media": "missing.mp4",
                "outcome": "forged manifest outcome"}]
    (root / "items.json").write_text(json.dumps(entries))
    with TestClient(create_app(Settings(root=tmp_path / "uploads"), demo_root=root)) as client:
        listing = client.get("/ui/demos").json()
        assert "outcome" not in listing[0]
        result = client.get("/ui/demos/reconstruction/reveal").json()
        assert result["outcome"] == ruling.outcome and result["rules"] == ruling.cap_rules
        assert result["url"] == ruling.url and "forged" not in json.dumps(result)


def write_registry(root: Path, part="test", stage="screen", total="10"):
    fields = ["run_id", "part", "stage", "created_at", "git_sha", "split", "model", "prompt", "effort",
              "snapshots", "metric", "hits", "total", "low", "high"]
    with (root / "runs.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(dict.fromkeys(fields, "") | {"run_id": "synthetic-test-run", "part": part, "stage": stage,
                        "metric": "claim_recall_carried", "hits": "7", "total": total, "git_sha": "abc1234"})


def test_scoreboard_requires_final_selector_and_registered_test_denominators(tmp_path):
    assert not scoreboard(tmp_path)["available"]
    write_registry(tmp_path)
    (tmp_path / "final.md").write_text("A historical run synthetic-test-run is mentioned here.")
    assert not scoreboard(tmp_path)["available"]
    (tmp_path / "final.md").write_text("run_id: synthetic-test-run\n")
    board = scoreboard(tmp_path)
    assert board["available"] and board["metrics"][0]["hits"] == 7
    assert board["metrics"][0]["total"] == 10 and board["git_sha"] == "abc1234"
    (tmp_path / "final.md").write_text("run_id: synthetic-test-run\nrun_id: another-run\n")
    assert not scoreboard(tmp_path)["available"]
    (tmp_path / "final.md").write_text("run_id: synthetic-test-run\n")
    write_registry(tmp_path, part="dev")
    assert not scoreboard(tmp_path)["available"]
    write_registry(tmp_path, total="nan")
    assert not scoreboard(tmp_path)["available"]


def test_scoreboard_ignores_costs_and_rejects_dirty_or_duplicated_metrics(tmp_path):
    (tmp_path / "final.md").write_text("run_id: synthetic-test-run\n")
    write_registry(tmp_path)
    path = tmp_path / "runs.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    cost = rows[0] | {"metric": "screen_wall_seconds", "hits": "900", "total": "10"}
    with path.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writerow(cost)
    assert scoreboard(tmp_path)["available"]
    assert len(scoreboard(tmp_path)["metrics"]) == 1
    with path.open("a", newline="", encoding="utf-8") as stream:
        csv.DictWriter(stream, fieldnames=fields).writerow(rows[0])
    assert not scoreboard(tmp_path)["available"]
    write_registry(tmp_path)
    path.write_text(path.read_text().replace("abc1234", "abc1234-dirty"))
    assert not scoreboard(tmp_path)["available"]


def test_bad_scoreboard_file_does_not_disable_the_upload_workspace(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    (results / "final.md").write_text("run_id: synthetic-test-run\n")
    (results / "runs.csv").write_text("wrong_header\nnot-a-registry\n")
    with TestClient(create_app(Settings(root=tmp_path / "uploads"), results_root=results)) as client:
        response = client.get("/ui/config")
        assert response.status_code == 200
        assert not response.json()["scoreboard"]["available"]


@pytest.mark.parametrize("manifest", ["[{}]", '["invalid"]', "{broken json"])
def test_invalid_demo_configuration_returns_a_controlled_error(tmp_path, manifest):
    demos = tmp_path / "demos"
    demos.mkdir()
    (demos / "items.json").write_text(manifest)
    with TestClient(create_app(Settings(root=tmp_path / "uploads"), demo_root=demos)) as client:
        response = client.get("/ui/demos")
        assert response.status_code == 409
        assert response.json()["error"] == "invalid_demo_manifest"


def test_presentation_folds_nested_flags_and_shows_each_flag_once():
    screening = Screening.model_validate_json((AGENT / "round0.json").read_text(encoding="utf-8"))
    result = presentation(screening, "/crops")
    rows = result["claims"]
    # rule 3: every flag appears once, on its line or on a phrase folded under it, with its sources
    shown = [f for r in rows for f in (*r["flags"], *(f for n in r["folded"] for f in n["flags"]))]
    assert sorted(f["flag_id"] for f in shown) == sorted(f.flag_id for f in screening.flags)
    assert all(f["source_details"] for f in shown)
    assert len(rows) < len(screening.claims) and any(r["folded"] for r in rows)
    order = ("high", "medium", "low", "unchecked")
    keys = [(order.index(r["tier"]) if r["tier"] else len(order), r["start"] is None, r["start"] or 0) for r in rows]
    assert keys == sorted(keys)
    assert all(r["start"] is None for r in rows if not any(e["timed"] for e in r["evidence"]))
    assert result["may_say"] and result["incomplete_stages"] == []
    ranks = [("high", "medium", "low").index(r["tier"]) for r in rows if r["flags"]]
    assert ranks == sorted(ranks) and all(r["tier"] is None for r in rows if not r["flags"])
    assert sum(result["tiers"].values()) == sum(r["tier"] is not None for r in rows)
