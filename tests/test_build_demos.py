import csv
import importlib.util
import json
from pathlib import Path

import pytest

from preflight.api.web import Demos
from preflight.eval.registry import FIELDS
from preflight.models.store import digest

spec = importlib.util.spec_from_file_location("build_demos", Path(__file__).parents[1] / "scripts" / "build_demos.py")
demos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demos)

FIXTURE = Path(__file__).parent / "fixtures/agent/magnesium/round0.json"
RUN = "screen-20261104T000000"
RULING = "A24-1228813"


@pytest.fixture
def world(tmp_path, monkeypatch):
    runs = tmp_path / "runs.csv"
    with runs.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, restval="")
        writer.writeheader()
        writer.writerow({"run_id": RUN, "git_sha": "abc1234", "split": "v2", "part": "test", "stage": "screen",
                         "metric": "ad_recall", "hits": 1, "total": 1})
    monkeypatch.setattr(demos, "void_runs", lambda: {})
    monkeypatch.setattr(demos, "load_split", lambda version: type("S", (), {"test": [RULING, "T26"]}))
    monkeypatch.setattr(demos, "RECONSTRUCTIONS", tmp_path / "reconstructions")
    monkeypatch.setattr(demos, "TEAM_DIR", tmp_path / "team")
    work = tmp_path / "work"
    for item, path in ((RULING, tmp_path / "reconstructions" / RULING / "reconstruction.mp4"),
                       ("T26", tmp_path / "team" / "T26" / "ad.mp4")):
        path.parent.mkdir(parents=True)
        path.write_bytes(f"media of {item}".encode())
        screening = json.loads(FIXTURE.read_text(encoding="utf-8"))
        screening["ad"]["content_hash"] = digest(path)
        saved = work / "runs" / RUN / f"{RUN}-{item}-ad.json"
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text(json.dumps(screening), encoding="utf-8")
        for name in {r["crop"] for t in screening["tracks"] for r in t["regions"] if r["crop"]}:
            crop = work / digest(path) / name
            crop.parent.mkdir(parents=True, exist_ok=True)
            crop.write_bytes(b"png")
    return {"runs": runs, "work": work, "out": tmp_path / "demo"}


def build(world, items):
    return demos.build(RUN, items, work=world["work"], out=world["out"], runs=world["runs"])


def test_demos_are_the_runs_own_screenings_labelled_and_readable_by_the_page(world):
    entries = build(world, [RULING, "T26"])
    assert [e["id"] for e in entries] == [RULING.lower(), "t26"]
    assert entries[0]["kind"] == "reconstruction" and entries[0]["ruling_id"] == RULING
    assert entries[0]["title"].startswith("AI reconstruction from ASA ruling text")
    assert entries[1]["kind"] == "synthetic" and "ruling_id" not in entries[1]
    assert all("v2 test split" in e["title"] for e in entries)
    page = Demos(world["out"])
    for entry in page.entries():
        assert page.result(entry).flags
        assert (world["out"] / entry["id"] / "crops" / "dark-rectangle-0.png").is_file()


def test_media_that_is_not_the_screened_file_is_refused(world):
    (demos.TEAM_DIR / "T26" / "ad.mp4").write_bytes(b"a different render")
    with pytest.raises(SystemExit, match="content hash differs"):
        build(world, ["T26"])
    assert not world["out"].exists()


@pytest.mark.parametrize("run_id, items, message", [
    (RUN, ["T99"], "not in split v2 test"),
    ("screen-unregistered", ["T26"], "not registered"),
])
def test_items_outside_the_run_and_unregistered_runs_are_refused(world, run_id, items, message):
    with pytest.raises(SystemExit, match=message):
        demos.build(run_id, items, work=world["work"], out=world["out"], runs=world["runs"])


@pytest.mark.parametrize("absolute", [False, True])
def test_crop_paths_cannot_escape_the_ingest_folder_or_replace_existing_demos(world, absolute):
    outside = world["work"] / "outside.png"
    outside.write_bytes(b"not a crop of the screened ad")
    saved = demos.screening_of(RUN, "T26", world["work"])
    screening = json.loads(saved.read_text(encoding="utf-8"))
    name = str(outside.resolve()) if absolute else "../outside.png"
    for track in screening["tracks"]:
        for region in track["regions"]:
            region["crop"] = name
    saved.write_text(json.dumps(screening), encoding="utf-8")
    world["out"].mkdir()
    previous = world["out"] / "items.json"
    previous.write_text("[]", encoding="utf-8")
    with pytest.raises(SystemExit, match="crop path"):
        build(world, ["T26"])
    assert previous.read_text(encoding="utf-8") == "[]"
    assert not (world["out"].with_name("demo.tmp") / "outside.png").exists()
