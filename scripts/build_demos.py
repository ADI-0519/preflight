"""Build the web page's demo list (data/raw/demo/items.json) from a registered run's screenings.

    uv run python scripts/build_demos.py <run_id> <item_id> [<item_id> ...]

Each demo is the screening the run made of that item, so the page shows the run's own blind result,
not one made for the demo. The screening must name the item's media by its content hash, and pass
source verification against the repository's snapshots (rule 3), or the item is refused. A
reconstruction is titled as one (rule 8) and its ASA outcome stays behind the page's reveal.
"""

import argparse
import csv
import json
import shutil
from pathlib import Path

from preflight.eval.reconstruct import OUT_DIR as RECONSTRUCTIONS
from preflight.eval.registry import RUNS
from preflight.eval.run import void_runs
from preflight.eval.split import RULING_ID, load_split
from preflight.eval.team_media import TEAM_DIR
from preflight.models.store import digest
from preflight.schema import Screening, verify_sources
from preflight.sources.rulings import load_ruling_index

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "work"
DEMO = ROOT / "data" / "raw" / "demo"


def run_record(run_id: str, runs: Path = RUNS) -> dict:
    with runs.open(newline="", encoding="utf-8") as f:
        row = next((r for r in csv.DictReader(f) if r["run_id"] == run_id), None)
    if row is None:
        raise SystemExit(f"{run_id} is not registered in {runs.name}; only a registered run's screenings are shown")
    if reason := void_runs().get(run_id):
        raise SystemExit(f"{run_id} is void ({reason})")
    return row


def media(item_id: str) -> Path:
    if RULING_ID.match(item_id):
        found = [RECONSTRUCTIONS / item_id / "reconstruction.mp4"]
        found = [p for p in found if p.exists()] or sorted((RECONSTRUCTIONS / item_id).glob("reconstruction*.png"))
    else:
        found = sorted((TEAM_DIR / item_id).glob("ad.*"))
    if len(found) != 1:
        raise SystemExit(f"{item_id}: expected one media file, found {len(found)}")
    return found[0]


def screening_of(run_id: str, item_id: str, work: Path) -> Path:
    found = sorted((work / "runs" / run_id).glob(f"{run_id}-{item_id}-*.json"))
    if len(found) != 1:
        raise SystemExit(f"{item_id}: expected one screening in {work / 'runs' / run_id}, found {len(found)}")
    return found[0]


def title(item_id: str, run: dict) -> str:
    part = "test split" if run["part"] == "test" else "dev split, prompts tuned on it"
    kind = "AI reconstruction from ASA ruling text" if RULING_ID.match(item_id) else "Team-written test ad"
    return f"{kind} · {item_id} · {run['split']} {part}"


def build(run_id: str, items: list[str], *, work: Path = WORK, out: Path = DEMO, runs: Path = RUNS) -> list[dict]:
    run = run_record(run_id, runs)
    part = set(getattr(load_split(run["split"]), run["part"]))
    entries = []
    staged = out.with_name(out.name + ".tmp")
    shutil.rmtree(staged, ignore_errors=True)
    staged.mkdir(parents=True)
    for item_id in items:
        if item_id not in part:
            raise SystemExit(f"{item_id} is not in split {run['split']} {run['part']}, the part {run_id} screened")
        source = screening_of(run_id, item_id, work)
        screening = Screening.model_validate_json(source.read_text(encoding="utf-8"))
        verify_sources(screening)
        if RULING_ID.match(item_id) and not screening.flags:
            print(f"note: {item_id} has no flags in {run_id}")
        ad = media(item_id)
        if digest(ad) != screening.ad.content_hash:
            raise SystemExit(f"{item_id}: {ad.name} is not the file {run_id} screened (content hash differs)")
        if RULING_ID.match(item_id) and item_id not in {r.ruling_id for r in load_ruling_index(
                screening.snapshots.rulings)}:
            raise SystemExit(f"{item_id} is not in rulings snapshot {screening.snapshots.rulings}")
        folder = staged / item_id.lower()
        folder.mkdir()
        shutil.copyfile(source, folder / "screening.json")
        shutil.copyfile(ad, folder / f"media{ad.suffix}")
        crops = [r.crop for t in screening.tracks for r in t.regions if r.crop]
        for name in crops:
            # crops sit in the ingest folder of the screened file, named relative to it
            ingest = (work / screening.ad.content_hash).resolve()
            src, dst = (ingest / name).resolve(), (folder / name).resolve()
            if (Path(name).is_absolute() or not src.is_relative_to(ingest)
                    or not dst.is_relative_to(folder.resolve())):
                raise SystemExit(f"{item_id}: crop path must stay inside the screened ad's folder")
            if not src.is_file():
                raise SystemExit(f"{item_id}: crop {name} missing under {work / screening.ad.content_hash}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        entry = {"id": item_id.lower(), "title": title(item_id, run),
                 "kind": "reconstruction" if RULING_ID.match(item_id) else "synthetic",
                 "screening": f"{item_id.lower()}/screening.json", "media": f"{item_id.lower()}/media{ad.suffix}",
                 "crops": "."}
        if RULING_ID.match(item_id):
            entry["ruling_id"] = item_id
        entries.append(entry)
    (staged / "items.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(out, ignore_errors=True)
    staged.rename(out)
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Write data/raw/demo/ from a registered run's screenings.")
    parser.add_argument("run_id")
    parser.add_argument("items", nargs="+", help="item IDs from the part the run screened, in page order")
    parser.add_argument("--work", type=Path, default=WORK, help="folder holding runs/<run_id>/ and ingest folders")
    args = parser.parse_args()
    for entry in build(args.run_id, args.items, work=args.work):
        print(f"{entry['id']}: {entry['title']}")
    print(f"wrote {DEMO / 'items.json'}")


if __name__ == "__main__":
    main()
