"""Build near-miss items (P65): a compliant team ad with one breaching line put in.

uv run python scripts/near_miss.py eval/near_miss/dev.yaml --split v2

Each entry names the item to write, the compliant team ad it is built on, the breaching line, the line's substance
and CAP rules, and its author. An image ad gets the line on screen, before the closing line (the food supplement
statement); a video ad gets it at the end of the voiceover. The script writes eval/items/team/<item_id>.yaml and the
item's ground truth, with checked_by empty for a founder other than the author to fill in. It does not add the items
to the split.
"""

import argparse
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from preflight.eval.split import EVAL_DIR, BreachingClaim, GroundTruth, TeamAd, load_team_ad, write_ground_truth


class Breach(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: str
    base: str
    line: str
    substance: str
    rules: list[str]
    written_by: str


def build(breach: Breach) -> tuple[TeamAd, GroundTruth]:
    ad = load_team_ad(breach.base)
    if ad.inserted:
        raise ValueError(f"{breach.base} is already a near-miss item")
    if ad.format == "image":
        screen = [*ad.on_screen_text[:-1], breach.line, ad.on_screen_text[-1]]
        voice = ad.voiceover
    else:
        screen = ad.on_screen_text
        voice = f"{ad.voiceover.strip()} {breach.line}".strip()
    item = ad.model_copy(update={
        "item_id": breach.item_id, "on_screen_text": screen, "voiceover": voice, "base": breach.base,
        "inserted": breach.line, "substance": breach.substance,
    })
    truth = GroundTruth(
        item_id=breach.item_id, kind="team", label="positive", outcome=None,
        claims=[BreachingClaim(claim=breach.line, rules=breach.rules, points=[])],
        written_by=f"{breach.written_by}: breach line in compliant team ad {breach.base}", checked_by=None,
    )
    return item, truth


def main() -> None:
    parser = argparse.ArgumentParser(description="Put one breaching line into compliant team ads.")
    parser.add_argument("breaches", type=Path)
    parser.add_argument("--split", default="v2", help="the ground-truth version to write")
    args = parser.parse_args()
    for entry in yaml.safe_load(args.breaches.read_text(encoding="utf-8")):
        item, truth = build(Breach(**entry))
        header = (f"# Near-miss item (P65): team ad {item.base} with one breaching line put in by "
                  f"scripts/near_miss.py from {args.breaches.as_posix()}.\n")  # fmt: skip
        body = yaml.safe_dump(item.model_dump(), sort_keys=False, allow_unicode=True, width=120)
        (EVAL_DIR / "items" / "team" / f"{item.item_id}.yaml").write_text(header + body, encoding="utf-8")
        write_ground_truth(args.split, truth)
        print(f"{item.item_id}: {item.base} + {item.inserted!r}")


if __name__ == "__main__":
    main()
