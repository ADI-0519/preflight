import yaml
from draft_split_v1 import draft_claims

from preflight.eval.split import EVAL_DIR, GroundTruth, load_split, write_ground_truth
from preflight.sources.rulings import load_rulings

VERSION = "v3"
CREATED = "2026-11-04"
# upheld rulings in neither v1 nor v2 that cite section 12, or 3.1 and 3.7 without section 15
DEV = ["A26-1333913", "G22-1172031", "A22-1154125", "A21-1136893", "A26-1325741", "A20-1083951"]


def main() -> None:
    if (EVAL_DIR / "splits" / f"{VERSION}.yaml").exists() and load_split(VERSION).frozen:
        raise SystemExit(f"split {VERSION} is frozen; a change needs a new version")
    v2 = load_split("v2")
    rulings = {r.ruling_id: r for r in load_rulings()}
    drafted = {p.stem for p in (EVAL_DIR / "ground_truth" / VERSION).glob("*.json")}
    # checkers correct the drafts by hand, so an existing file is kept; delete it to redraft
    for ruling in (rulings[i] for i in DEV if i not in drafted):
        write_ground_truth(VERSION, GroundTruth(
            item_id=ruling.ruling_id, kind="ruling", label="positive", outcome=ruling.outcome,
            claims=draft_claims(ruling), written_by="draft: scripts/draft_split_v3.py", checked_by=None,
        ))  # fmt: skip
    manifest = {
        "version": VERSION,
        "frozen": False,
        "created": CREATED,
        "status": "draft: ground truth awaits two independent checks; not frozen",
        "sources": {"rulings": "2026-11-02", "register": "2026-05-19"},
        "topics": "supplement and health-product rulings citing CAP section 12, or 3.1 and 3.7 without section 15",
        "counts": {"dev": {"positive": len(DEV), "negative": 0}},
        "dev": DEV,
        # never run: it keeps v2's test rulings and their advertisers out of every v3 precedent pool
        "test": v2.test,
    }
    header = (
        "# Split v3: a rule-selection check set of rulings in neither v1 nor v2. The test list repeats v2's so its\n"
        "# rulings stay out of the precedent pools (rule 5); only the dev part is run.\n"
    )
    path = EVAL_DIR / "splits" / f"{VERSION}.yaml"
    path.write_text(header + yaml.safe_dump(manifest, sort_keys=False, width=120), encoding="utf-8", newline="\n")
    for i in DEV:
        print(i, len(draft_claims(rulings[i])), "draft claims")


if __name__ == "__main__":
    main()
