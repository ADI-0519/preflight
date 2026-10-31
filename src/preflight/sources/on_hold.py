import argparse
import json
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict

SNAPSHOT_DIR = Path(__file__).resolve().parents[3] / "data" / "snapshots"

SHEETS = {
    "Article_13_1_botanicals_on_hold": "botanical",
    "Other_Article_13_1_on_hold_": "other",
}
HEADER_LAST_CELL = "Claim ID"

_NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
_TABLE = f"{{{_NS['table']}}}"
_TEXT = f"{{{_NS['text']}}}"


class OnHoldClaim(BaseModel):
    model_config = ConfigDict(frozen=True)

    on_hold_id: str
    kind: Literal["botanical", "other"]
    substance: str
    health_relationship: str | None
    # wording proposed by applicants in 2008; rule 2: never offered as suggested wording
    proposed_wording: str | None


def _paragraph_text(p: ElementTree.Element) -> str:
    parts = [p.text or ""]
    for child in p:
        if child.tag == _TEXT + "s":
            parts.append(" " * int(child.get(_TEXT + "c", "1")))
        else:
            parts.append(_paragraph_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _cells(row: ElementTree.Element) -> list[str | None]:
    values = []
    for cell in row:
        paragraphs = cell.findall("text:p", _NS)
        value = "\n".join(_paragraph_text(p) for p in paragraphs) or None
        # trailing blank cells are written as one cell repeated thousands of times
        repeat = int(cell.get(_TABLE + "number-columns-repeated", "1"))
        values.extend([value] * (repeat if value is not None else min(repeat, 1)))
    return values


def read_rows(rows: list[list[str | None]], list_name: Literal["botanical", "other"]) -> Iterator[OnHoldClaim]:
    header_seen = False
    for row in rows:
        row = (row + [None] * 4)[:4]
        if not header_seen:
            header_seen = row[3] == HEADER_LAST_CELL
            continue
        substance, relationship, wording, claim_id = row
        if claim_id is None:
            if any(row):
                raise ValueError(f"on-hold row without a Claim ID: {row!r}")
            continue
        yield OnHoldClaim(
            on_hold_id=claim_id.strip(),
            kind=list_name,
            substance=substance,
            health_relationship=relationship,
            proposed_wording=wording,
        )
    if not header_seen:
        raise ValueError(f"no '{HEADER_LAST_CELL}' header row in the {list_name} sheet")


def read_ods(path: Path) -> list[OnHoldClaim]:
    root = ElementTree.fromstring(zipfile.ZipFile(path).read("content.xml"))
    claims = []
    for table in root.iter(_TABLE + "table"):
        name = table.get(_TABLE + "name")
        if name not in SHEETS:
            raise ValueError(f"unexpected sheet in on-hold list: {name!r}")
        rows = [_cells(row) for row in table.iter(_TABLE + "table-row")]
        claims.extend(read_rows(rows, SHEETS[name]))
    ids = [c.on_hold_id for c in claims]
    if len(ids) != len(set(ids)):
        raise ValueError("on-hold Claim IDs collide")
    return claims


def snapshot_path(version: str) -> Path:
    return SNAPSHOT_DIR / f"on-hold-{version}.jsonl"


def write_snapshot(claims: list[OnHoldClaim], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for claim in claims:
            f.write(json.dumps(claim.model_dump(), ensure_ascii=False) + "\n")


def load_on_hold(snapshot: str | Path) -> list[OnHoldClaim]:
    path = Path(snapshot) if str(snapshot).endswith(".jsonl") else snapshot_path(str(snapshot))
    with path.open(encoding="utf-8") as f:
        return [OnHoldClaim.model_validate_json(line) for line in f if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an on-hold claims snapshot from the DHSC ODS release.")
    parser.add_argument("ods", type=Path)
    parser.add_argument("--date", required=True, help="release date of the spreadsheet, YYYY-MM-DD")
    args = parser.parse_args()
    claims = read_ods(args.ods)
    write_snapshot(claims, snapshot_path(args.date))
    botanical = sum(c.kind == "botanical" for c in claims)
    print(f"{len(claims)} on-hold claims ({botanical} botanical) -> {snapshot_path(args.date)}")


if __name__ == "__main__":
    main()
