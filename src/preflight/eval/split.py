"""Evaluation split manifests, ground truth and team-written items (docs/plan.md, evaluation protocol)."""

import json
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "eval"

RULING_ID = re.compile(r"^[AG]\d{2}-\d{6,8}$")


class Split(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    frozen: bool
    created: str
    dev: list[str]
    test: list[str]

    @property
    def items(self) -> list[str]:
        return [*self.dev, *self.test]

    def excluded_ruling_ids(self) -> set[str]:
        """Rulings that must never reach prompts, examples or the precedent index (rule 5)."""
        return {i for i in self.items if RULING_ID.match(i)}


class BreachingClaim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim: str  # quoted exactly as it appears in the ruling's ad description
    rules: list[str]  # CAP rules the assessment found this claim to breach
    point: int | None = None  # the numbered point of the assessment it comes from


class GroundTruth(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: str
    kind: Literal["ruling", "team"]
    label: Literal["positive", "negative"]
    outcome: str | None  # the ruling's outcome; None for team items
    claims: list[BreachingClaim]
    written_by: str
    checked_by: str | None


class TeamAd(BaseModel):
    """An ad the team wrote using only verbatim authorised register wording."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: str
    format: Literal["image", "video"]
    product: str
    register_ids: list[str]
    on_screen_text: list[str]
    voiceover: str


def load_split(version: str = "v1") -> Split:
    data = yaml.safe_load((EVAL_DIR / "splits" / f"{version}.yaml").read_text(encoding="utf-8"))
    return Split(**{k: data[k] for k in Split.model_fields})


def load_ground_truth(version: str, item_id: str) -> GroundTruth:
    path = EVAL_DIR / "ground_truth" / version / f"{item_id}.json"
    return GroundTruth.model_validate_json(path.read_text(encoding="utf-8"))


def load_team_ad(item_id: str) -> TeamAd:
    path = EVAL_DIR / "items" / "team" / f"{item_id}.yaml"
    return TeamAd(**yaml.safe_load(path.read_text(encoding="utf-8")))


def write_ground_truth(version: str, truth: GroundTruth) -> None:
    path = EVAL_DIR / "ground_truth" / version / f"{truth.item_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(truth.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
