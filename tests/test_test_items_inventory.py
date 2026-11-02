import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "inventory_test_items.py"
SECRET = "TEST COPY MUST NOT BE PRINTED"


def write(root: Path, written_by="assistant: independent author", checked_by="Neesay: checked 3 Nov"):
    splits = root / "eval" / "splits"
    splits.mkdir(parents=True)
    (splits / "v1.yaml").write_text(yaml.safe_dump({"dev": ["T01"], "test": ["T02"], "frozen": True}))
    v2 = {"dev": ["T01", "T16"], "test": ["T02", "T26", "N11"], "frozen": False}
    (splits / "v2.yaml").write_text(yaml.safe_dump(v2))
    items, truths = root / "eval" / "items" / "team", root / "eval" / "ground_truth" / "v2"
    items.mkdir(parents=True)
    truths.mkdir(parents=True)
    (items / "T26.yaml").write_text(yaml.safe_dump({"item_id": "T26", "on_screen_text": [SECRET]}))
    (items / "N11.yaml").write_text(yaml.safe_dump({"item_id": "N11", "base": "T26", "inserted": SECRET}))
    signed = {"kind": "team", "outcome": None, "written_by": written_by, "checked_by": checked_by}
    (truths / "T26.json").write_text(json.dumps({"item_id": "T26", "label": "negative", "claims": [], **signed}))
    breach = [{"claim": SECRET, "rules": ["15.1"], "points": []}]
    (truths / "N11.json").write_text(json.dumps({"item_id": "N11", "label": "positive", "claims": breach, **signed}))
    for item_id in ("T26", "N11"):
        media = root / "data" / "raw" / "team" / item_id
        media.mkdir(parents=True)
        (media / "ad.png").write_bytes(b"png")
        (media / "meta.json").write_text("{}")


def inventory(root: Path) -> tuple[int, dict]:
    done = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], capture_output=True, text=True)
    assert SECRET not in done.stdout + done.stderr
    return done.returncode, json.loads(done.stdout)


def problems(result: dict) -> dict[str, list[str]]:
    return {r["item_id"]: r["problems"] for r in result["items"]}


@pytest.mark.parametrize("checked_by", ["Neesay: checked 3 Nov", "checker: checked 2026-11-02, media 0123456789ab"])
def test_signed_items_pass_with_their_hashes_and_nothing_changes(tmp_path, checked_by):
    write(tmp_path, checked_by=checked_by)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    code, result = inventory(tmp_path)
    assert code == 0 and result["new_test_items"] == 2
    assert problems(result) == {"T26": [], "N11": []}
    assert all(len(r["media_sha256"]) == 64 for r in result["items"])
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    ("written_by", "checked_by"),
    [
        ("assistant: drafted", None),
        ("Neesay: breach line", "neesay: checked"),
        ("assistant: drafted", "assistant: self-check"),
        ("team: generic", "Neesay"),
        ("checker: drafted", "checker: checked 2026-11-02"),
        ("assistant: drafted", "someone: checked"),
    ],
)
def test_each_item_needs_a_check_by_someone_other_than_its_author(tmp_path, written_by, checked_by):
    write(tmp_path, written_by, checked_by)
    code, result = inventory(tmp_path)
    assert code == 1
    assert all(
        {"unknown_author", "needs_a_check_by_someone_other_than_the_author"} & set(p)
        for p in problems(result).values()
    )


def test_a_near_miss_item_must_carry_its_inserted_line_on_a_new_negative(tmp_path):
    write(tmp_path)
    truth = tmp_path / "eval" / "ground_truth" / "v2" / "N11.json"
    truth.write_text(truth.read_text().replace(json.dumps(SECRET), json.dumps(SECRET + " changed")))
    item = tmp_path / "eval" / "items" / "team" / "N11.yaml"
    item.write_text(item.read_text().replace("T26", "T02"))
    _, result = inventory(tmp_path)
    assert set(problems(result)["N11"]) == {"not_one_inserted_breach_with_rules", "base_is_not_a_new_test_negative"}


def test_a_negative_with_claims_or_no_render_is_reported(tmp_path):
    write(tmp_path)
    truth = tmp_path / "eval" / "ground_truth" / "v2" / "T26.json"
    truth.write_text(truth.read_text().replace('"claims": []', f'"claims": [{{"claim": "{SECRET}"}}]'))
    (tmp_path / "data" / "raw" / "team" / "T26" / "ad.png").unlink()
    _, result = inventory(tmp_path)
    assert set(problems(result)["T26"]) == {"not_an_empty_claim_negative", "needs_one_render_and_its_metadata"}


def test_unreadable_files_are_reported_without_quoting_them(tmp_path):
    write(tmp_path)
    (tmp_path / "eval" / "ground_truth" / "v2" / "T26.json").write_text("{" + SECRET)
    _, result = inventory(tmp_path)
    assert problems(result)["T26"] == ["unreadable_source_or_ground_truth"]
    (tmp_path / "eval" / "splits" / "v2.yaml").write_text("[" + SECRET)
    assert inventory(tmp_path) == (1, {"error": "split manifests unreadable"})


def test_unlisted_items_and_split_changes_are_reported(tmp_path):
    write(tmp_path)
    (tmp_path / "eval" / "items" / "team" / "T27.yaml").write_text(SECRET)
    split = tmp_path / "eval" / "splits" / "v2.yaml"
    split.write_text(yaml.safe_dump({"dev": ["T01", "T26"], "test": ["T26", "N11"], "frozen": False}))
    _, result = inventory(tmp_path)
    assert result["not_in_split"] == ["T27"]
    assert result["split_problems"] == ["an_item_is_listed_twice", "v1_items_not_kept"]
