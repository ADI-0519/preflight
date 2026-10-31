"""GB nutrition and health claims register: XLSX release -> dated JSONL snapshot -> RegisterEntry records.

Build a snapshot from a downloaded release:

    uv run python -m preflight.sources.register data/raw/register/<release>.xlsx --date 2026-05-19
"""

import argparse
import hashlib
import html
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

SNAPSHOT_DIR = Path(__file__).resolve().parents[3] / "data" / "snapshots"

HEALTH_SHEET = "Health_claims"
NUTRITION_SHEET = "Nutrition_claims"
HEALTH_HEADER_ROW = 3  # rows 1-2 are a title and an accessibility note
NUTRITION_HEADER_ROW = 3

_TAG = re.compile(r"<[^>]+>")
_HYPERLINK = re.compile(r'^=HYPERLINK\("([^"]*)"\s*,\s*"([^"]*)"\)$')


class RegisterEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    register_id: str
    claim_type: str
    substance: str | None
    wording: str
    wording_source: str
    conditions: str | None
    health_relationship: str | None
    status: Literal["authorised", "non_authorised"]
    proprietary: bool
    efsa_ids: list[str]
    references: list[str]
    regulation: str | None


def clean(text: str | None) -> str | None:
    """Remove the HTML tags some cells carry and decode entities; every other character is kept."""
    if text is None:
        return None
    return html.unescape(_TAG.sub("", text))


def _link(cell) -> str | None:
    """Text of a reference cell: the URL of a HYPERLINK formula, else the cell's text."""
    if cell is None:
        return None
    match = _HYPERLINK.match(str(cell))
    return html.unescape(match.group(1)) if match else str(cell)


def _efsa_ids(cell) -> list[str]:
    if cell is None:
        return []
    ids = [i.strip() for i in str(cell).split(",")]
    return [i for i in ids if i and i.lower() != "not applicable"]


def _make_id(prefix: str, *fields) -> str:
    key = "\x1f".join("" if f is None else str(f) for f in fields)
    return f"{prefix}-{hashlib.sha256(key.encode()).hexdigest()[:12]}"


def _status(raw: str) -> tuple[Literal["authorised", "non_authorised"], bool]:
    raw = raw.strip()
    if raw.startswith("Authorised"):
        return "authorised", raw.endswith("*")
    if raw == "Non-authorised":
        return "non_authorised", False
    raise ValueError(f"unknown register status: {raw!r}")


def read_health_claims(rows: list[tuple]) -> Iterator[RegisterEntry]:
    """Health claim rows after the header. A row with only column F filled continues the entry above it."""
    pending: dict | None = None
    for row in rows:
        row = tuple(row) + (None,) * (9 - len(row))
        claim_type, substance, claim, conditions, relationship, opinion, regulation, status, entry_id = row[:9]
        if claim_type is None and claim is None:
            if pending is not None and opinion is not None:
                pending["references"].append(_link(opinion))
            continue
        if pending is not None:
            yield RegisterEntry(**pending)
        status_value, proprietary = _status(status)
        pending = {
            "register_id": _make_id("gbhc", claim_type, substance, claim, conditions, relationship, entry_id),
            "claim_type": claim_type,
            "substance": clean(substance),
            "wording": clean(claim),
            "wording_source": claim,
            "conditions": clean(conditions),
            "health_relationship": clean(relationship),
            "status": status_value,
            "proprietary": proprietary,
            "efsa_ids": _efsa_ids(entry_id),
            "references": [_link(opinion)] if opinion is not None else [],
            "regulation": _link(regulation),
        }
    if pending is not None:
        yield RegisterEntry(**pending)


def read_nutrition_claims(rows: list[tuple]) -> Iterator[RegisterEntry]:
    for row in rows:
        claim, conditions = (tuple(row) + (None, None))[:2]
        if claim is None:
            continue
        yield RegisterEntry(
            register_id=_make_id("gbnc", claim),
            claim_type="Nutrition claim",
            substance=None,
            wording=clean(claim),
            wording_source=claim,
            conditions=clean(conditions),
            health_relationship=None,
            status="authorised",
            proprietary=False,
            efsa_ids=[],
            references=[],
            regulation=None,
        )


def read_xlsx(path: Path) -> list[RegisterEntry]:
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True)
    health = list(workbook[HEALTH_SHEET].iter_rows(min_row=HEALTH_HEADER_ROW + 1, values_only=True))
    nutrition = list(workbook[NUTRITION_SHEET].iter_rows(min_row=NUTRITION_HEADER_ROW + 1, values_only=True))
    entries = [*read_health_claims(health), *read_nutrition_claims(nutrition)]
    ids = [e.register_id for e in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("register IDs collide; the identifying fields are no longer unique")
    return entries


def snapshot_path(version: str) -> Path:
    return SNAPSHOT_DIR / f"register-{version}.jsonl"


def write_snapshot(entries: list[RegisterEntry], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for entry in entries:
            f.write(json.dumps(entry.model_dump(), ensure_ascii=False) + "\n")


def load_register(snapshot: str | Path) -> list[RegisterEntry]:
    """Load a snapshot by version (e.g. "2026-05-19") or by path."""
    path = Path(snapshot) if str(snapshot).endswith(".jsonl") else snapshot_path(str(snapshot))
    with path.open(encoding="utf-8") as f:
        return [RegisterEntry.model_validate_json(line) for line in f if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a register snapshot from a GOV.UK XLSX release.")
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("--date", required=True, help="release date of the spreadsheet, YYYY-MM-DD")
    args = parser.parse_args()
    entries = read_xlsx(args.xlsx)
    write_snapshot(entries, snapshot_path(args.date))
    authorised = sum(e.status == "authorised" for e in entries)
    print(f"{len(entries)} entries ({authorised} authorised) -> {snapshot_path(args.date)}")


if __name__ == "__main__":
    main()
