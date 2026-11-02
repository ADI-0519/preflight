import csv
import subprocess
from pathlib import Path
from typing import NamedTuple

from preflight.eval.split import ROOT
from preflight.schema import Snapshots

RESULTS = ROOT / "results"
RUNS = RESULTS / "runs.csv"
FIELDS = [
    "run_id", "created_at", "git_sha", "split", "part", "stage", "model", "prompt", "effort", "metric", "hits", "total",
    "low", "high", "snapshots",
]


class Metric(NamedTuple):
    name: str
    hits: float
    total: float
    # 95% interval of hits / total: exact for a count of ads, else a bootstrap over ads
    low: float | None = None
    high: float | None = None


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def revision(part: str) -> str:
    sha = git("rev-parse", "--short", "HEAD").strip()
    if part == "test":
        # rule 5: the test part runs once per final configuration, which must be traceable to a commit;
        # untracked files count, since an untracked prompt file changes what runs
        if git("status", "--porcelain"):
            raise SystemExit("refusing to run on the test part from a dirty tree; commit or stash first")
        return sha
    # a run on uncommitted code is not reproducible from its SHA alone
    return sha + "-dirty" if git("status", "--porcelain") else sha


def snapshot_text(s: Snapshots) -> str:
    return " ".join(f"{k}={v}" for k, v in s.model_dump(mode="json").items())


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def register(common: dict, metrics: list[Metric | tuple]) -> None:
    rows, fields = [], None
    if RUNS.exists():
        with RUNS.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows, fields = list(reader), reader.fieldnames
    with RUNS.open("w" if fields != FIELDS else "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, restval="")
        if fields != FIELDS:
            # columns added since a row was written stay empty in it
            writer.writeheader()
            writer.writerows(rows)
        for m in (Metric(*m) for m in metrics):
            writer.writerow(common | {
                "metric": m.name, "hits": m.hits, "total": m.total,
                "low": "" if m.low is None else m.low, "high": "" if m.high is None else m.high,
            })
