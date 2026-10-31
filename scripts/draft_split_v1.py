"""Draft split v1 and its ground truth from the rulings corpus and the team-written ads.

Reproducible and model-free: run it on the same corpus and it writes the same files. The ground truth it
writes is a draft for a founder to check (checked_by stays null until then).

    uv run python scripts/draft_split_v1.py
"""

import re
from collections import Counter

import yaml

from preflight.eval.split import (
    EVAL_DIR,
    BreachingClaim,
    GroundTruth,
    advertiser_key,
    load_team_ad,
    write_ground_truth,
)
from preflight.sources.rulings import Ruling, load_rulings

VERSION = "v1"
CREATED = "2026-10-31"
MAX_PER_ADVERTISER = 2
TEST_SHARE = 2 / 3
TEAM_DEV = ["T01", "T05", "T09", "T12", "T15"]  # every third team ad, so dev and test both mix formats
TEAM_ITEMS = [f"T{i:02d}" for i in range(1, 16)]

QUOTE = re.compile(r"[“\"]([^”\"]{4,2000})[”\"]")
ELISION = re.compile(r"\[(?:…|\.\.\.)\]")
RULE = re.compile(r"\b(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)\b")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("‘", "'")).strip().lower()


def eligible(ruling: Ruling) -> bool:
    """In-scope corpus ruling, minus alcohol nutrition-claim cases (section 18), which P02 also left out."""
    return not any(r.startswith("18.") for r in ruling.cap_rules)


def points(assessment: str) -> list[tuple[list[int], str, str]]:
    """(numbers, outcome, text) for each numbered point; a ruling with one issue has no numbers."""
    # the ASA sometimes judges points together under one heading, e.g. "1. & 3. Upheld"
    parts = re.split(r"^\s*(\d+\.(?:\s*&\s*\d+\.)*)\s*(Upheld|Not upheld)\s*$", assessment, flags=re.M | re.I)
    if len(parts) < 4:
        return [([1], "upheld", assessment)]
    return [
        ([int(n) for n in re.findall(r"\d+", parts[i])], parts[i + 1].lower(), parts[i + 2])
        for i in range(1, len(parts) - 2, 3)
    ]


def draft_claims(ruling: Ruling) -> list[BreachingClaim]:
    """Quoted text in each upheld point that also appears verbatim in the ad description, with that point's rules."""
    description = norm(ruling.ad_description)
    claims: dict[str, BreachingClaim] = {}
    for numbers, outcome, body in points(ruling.assessment):
        if outcome != "upheld":
            continue
        breach_sentences = " ".join(s for s in re.split(r"(?<=[.;])\s", body) if "breach" in s.lower())
        cited = list(dict.fromkeys(RULE.findall(breach_sentences)))
        # seven pages have no CAP Code section; their rules are read from the assessment text alone
        rules = [r for r in cited if r in ruling.cap_rules] if ruling.cap_rules else cited
        rules = rules or list(ruling.cap_rules)
        for quote in dict.fromkeys(QUOTE.findall(body)):
            # a quote the ASA elided with […] is kept whole if it matches, else as its matching fragments
            parts = [quote] if norm(quote) in description else ELISION.split(quote)
            for part in parts:
                part = part.strip(" .,;:")
                key = norm(part)
                # single words count ("nootropic", "cured"); under 3 characters is a stray fragment
                if len(part) < 3 or key not in description:
                    continue
                # a claim upheld under several points is listed once, with every point and rule
                seen = claims.get(key, BreachingClaim(claim=part, rules=[], points=[]))
                claims[key] = BreachingClaim(
                    claim=seen.claim,
                    rules=list(dict.fromkeys([*seen.rules, *rules])),
                    points=list(dict.fromkeys([*seen.points, *numbers])),
                )
    return list(claims.values())


def main() -> None:
    positives, per_advertiser = [], Counter()
    for ruling in load_rulings():  # most recent first
        if eligible(ruling) and per_advertiser[advertiser_key(ruling.advertiser)] < MAX_PER_ADVERTISER:
            positives.append(ruling)
            per_advertiser[advertiser_key(ruling.advertiser)] += 1
    n_test = round(len(positives) * TEST_SHARE)
    test_pos, dev_pos = positives[:n_test], positives[n_test:]
    team_test = [t for t in TEAM_ITEMS if t not in TEAM_DEV]

    drafted = {p.stem for p in (EVAL_DIR / "ground_truth" / VERSION).glob("*.json")}
    # founders correct the drafts by hand, so an existing file is kept; delete it to redraft
    for ruling in (r for r in positives if r.ruling_id not in drafted):
        write_ground_truth(VERSION, GroundTruth(
            item_id=ruling.ruling_id, kind="ruling", label="positive", outcome=ruling.outcome,
            claims=draft_claims(ruling), written_by="draft: scripts/draft_split_v1.py", checked_by=None,
        ))  # fmt: skip
    for item in TEAM_ITEMS:
        load_team_ad(item)  # validates the item file
        if item in drafted:
            continue
        write_ground_truth(VERSION, GroundTruth(
            item_id=item, kind="team", label="negative", outcome=None, claims=[],
            written_by="team: authorised register wording only", checked_by=None,
        ))  # fmt: skip

    manifest = {
        "version": VERSION,
        "frozen": False,
        "created": CREATED,
        "status": "draft: ground truth awaits a second founder's check; not frozen",
        "sources": {"rulings": "2026-10-31", "register": "2026-05-19"},
        "topics": "all in-scope supplement and health-claim rulings (see docs/notes/rulings-corpus.md)",
        "counts": {
            "dev": {"positive": len(dev_pos), "negative": len(TEAM_DEV)},
            "test": {"positive": len(test_pos), "negative": len(team_test)},
        },
        "shortfall": "test negatives 10 of 20: no in-scope ruling in the window was not upheld, so negatives are "
        "team-written only until partner ads arrive (P06)",
        "dev": [r.ruling_id for r in dev_pos] + TEAM_DEV,
        "test": [r.ruling_id for r in test_pos] + team_test,
    }
    path = EVAL_DIR / "splits" / f"{VERSION}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "# Split v1. Item IDs are ASA ruling IDs (positives) or T-numbers (team-written negatives).\n"
    path.write_text(header + yaml.safe_dump(manifest, sort_keys=False, width=120), encoding="utf-8", newline="\n")
    empty = sum(1 for r in positives if not draft_claims(r))
    print(f"dev {len(dev_pos)}+{len(TEAM_DEV)}, test {len(test_pos)}+{len(team_test)}; {empty} with no draft claims")


if __name__ == "__main__":
    main()
