import argparse
import hashlib
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEAM_ID = re.compile(r"[TN]\d{2,}")
FOUNDERS = {"NEESAY", "neesay", "adi-0519"}
# an item written by an assistant may be checked by any founder
AUTHORS = FOUNDERS | {"assistant"}
# a check may also be signed by an independent checker, one that wrote none of the items (P60 decision, 2 Nov)
CHECKERS = FOUNDERS | {"checker"}


def sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def handle(value) -> str:
    # ground truth writes "<handle>: <note>", as N01's "Neesay: breach line in compliant team ad T16"
    return value.split(":", 1)[0].strip().casefold() if isinstance(value, str) else ""


def problems(root: Path, item_id: str, negatives: set[str]) -> list[str]:
    found = []
    try:
        truth = json.loads((root / "eval" / "ground_truth" / "v2" / f"{item_id}.json").read_text(encoding="utf-8"))
        ad = yaml.safe_load((root / "eval" / "items" / "team" / f"{item_id}.yaml").read_text(encoding="utf-8"))
        truth, ad = dict(truth), dict(ad)
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        return ["unreadable_source_or_ground_truth"]
    if truth.get("item_id") != item_id or ad.get("item_id") != item_id or truth.get("kind") != "team":
        found.append("item_id_or_kind_mismatch")
    claims = truth.get("claims")
    if item_id.startswith("T") and (truth.get("label") != "negative" or claims != [] or ad.get("inserted")):
        found.append("not_an_empty_claim_negative")
    if item_id.startswith("N"):
        one = claims[0] if isinstance(claims, list) and len(claims) == 1 and isinstance(claims[0], dict) else {}
        if truth.get("label") != "positive" or not one.get("rules") or one.get("claim") != ad.get("inserted"):
            found.append("not_one_inserted_breach_with_rules")
        if ad.get("base") not in negatives:
            found.append("base_is_not_a_new_test_negative")
    author, reviewer = handle(truth.get("written_by")), handle(truth.get("checked_by"))
    if author not in AUTHORS:
        found.append("unknown_author")
    if reviewer not in CHECKERS or reviewer == author:
        found.append("needs_a_check_by_someone_other_than_the_author")
    media = root / "data" / "raw" / "team" / item_id
    if sum((media / n).is_file() for n in ("ad.png", "ad.mp4")) != 1 or not (media / "meta.json").is_file():
        found.append("needs_one_render_and_its_metadata")
    return found


def inventory(root: Path) -> dict:
    splits = root / "eval" / "splits"
    v1, v2 = (yaml.safe_load((splits / f"{v}.yaml").read_text(encoding="utf-8")) for v in ("v1", "v2"))
    inherited = {*v1["dev"], *v1["test"]}
    new = [i for i in v2["test"] if TEAM_ID.fullmatch(i) and i not in inherited]
    negatives = {i for i in new if i.startswith("T")}
    on_disk = {p.stem for p in (root / "eval" / "items" / "team").glob("*.yaml") if TEAM_ID.fullmatch(p.stem)}
    split_problems = []
    if len({*v2["dev"], *v2["test"]}) != len(v2["dev"]) + len(v2["test"]):
        split_problems.append("an_item_is_listed_twice")
    if not set(v1["dev"]) <= set(v2["dev"]) or v2["test"][: len(v1["test"])] != v1["test"]:
        split_problems.append("v1_items_not_kept")
    return {
        "frozen": v2["frozen"],
        "new_test_items": len(new),
        "not_in_split": sorted(on_disk - inherited - {*v2["dev"], *v2["test"]}),
        "split_problems": split_problems,
        "items": [
            {
                "item_id": i,
                "problems": problems(root, i, negatives),
                "source_sha256": sha256(root / "eval" / "items" / "team" / f"{i}.yaml"),
                "ground_truth_sha256": sha256(root / "eval" / "ground_truth" / "v2" / f"{i}.json"),
                "media_sha256": next(
                    (h for n in ("ad.png", "ad.mp4") if (h := sha256(root / "data" / "raw" / "team" / i / n))), None
                ),
            }
            for i in new
        ],
    }


def main() -> int:
    # rule 5: whoever runs this may also work on the judge, so it prints hashes and problem names, never copy
    parser = argparse.ArgumentParser(description="Check the metadata of v2's new test items without printing copy.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = inventory(args.root)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
        # a parser error can quote the file it failed on, which may be test copy
        print(json.dumps({"error": "split manifests unreadable"}))
        return 1
    print(json.dumps(result, indent=2))
    return 0 if not result["split_problems"] and not any(r["problems"] for r in result["items"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
