"""Check built reconstructions against their ruling's ad description and ground truth, with no model calls.

For each ruling item: how many ground-truth claims the reconstruction carries (exactly, or with a brand
genericised or a "[sic]" dropped), and which on-screen or spoken lines do not come from the ad description.
This is a screen for the founders' spot-check (product rule 8), not a replacement for it.

    uv run python -m preflight.eval.check_reconstructions
"""

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from preflight.eval.reconstruct import OUT_DIR, ShotList
from preflight.eval.split import load_ground_truth, load_split
from preflight.sources.rulings import load_rulings

NEAR = 0.8  # share of a claim's words found in order in the reconstruction


def words(text: str) -> list[str]:
    text = text.replace("’", "'").replace("‘", "'").lower()
    text = re.sub(r"\[(?:sic|brand)\]", " ", text)
    return re.findall(r"[a-z0-9']+", text)


def carried(claim: str, text: list[str]) -> str:
    """'exact', 'near' or 'missing' for one claim against the reconstruction's words."""
    target = words(claim)
    if not target:
        return "exact"
    if " ".join(target) in " ".join(text):
        return "exact"
    blocks = SequenceMatcher(None, target, text, autojunk=False).get_matching_blocks()
    return "near" if sum(b.size for b in blocks) / len(target) >= NEAR else "missing"


def lines(shots: ShotList) -> list[str]:
    return [line for s in shots.scenes for line in [*s.on_screen_text, s.voiceover] if line.strip()]


def added(line: str, description: list[str]) -> bool:
    """True if under NEAR of the line's words appear, in order, in the ad description."""
    target = words(line)
    if not target:
        return False
    blocks = SequenceMatcher(None, target, description, autojunk=False).get_matching_blocks()
    return sum(b.size for b in blocks) / len(target) < NEAR


def check_item(ruling_id: str, description: str, claims: list[str], shots: ShotList) -> dict:
    text = [w for line in lines(shots) for w in words(line)]
    verdicts = [carried(c, text) for c in claims]
    desc = words(description)
    return {
        "ruling_id": ruling_id,
        "claims": len(claims),
        "exact": verdicts.count("exact"),
        "near": verdicts.count("near"),
        "missing": [c for c, v in zip(claims, verdicts, strict=True) if v == "missing"],
        "lines": len(lines(shots)),
        "added": [line for line in lines(shots) if added(line, desc)],
    }


def main(out_dir: Path = OUT_DIR) -> None:
    rulings = {r.ruling_id: r for r in load_rulings(scope_only=False)}
    results = []
    for rid in sorted(load_split("v1").excluded_ruling_ids()):
        shots = ShotList.model_validate_json((out_dir / rid / "shotlist.json").read_text(encoding="utf-8"))
        claims = [c.claim for c in load_ground_truth("v1", rid).claims]
        results.append(check_item(rid, rulings[rid].ad_description, claims, shots))
    (out_dir / "_check.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(r["claims"] for r in results)
    exact, near = sum(r["exact"] for r in results), sum(r["near"] for r in results)
    print(
        f"{len(results)} items; claims carried exactly {exact}, near {near}, missing {total - exact - near} of {total}"
    )
    print(f"items missing a claim: {sum(1 for r in results if r['missing'])}")
    print(f"lines not from the ad description: {sum(len(r['added']) for r in results)} of "
          f"{sum(r['lines'] for r in results)}, in {sum(1 for r in results if r['added'])} items")  # fmt: skip


if __name__ == "__main__":
    main()
