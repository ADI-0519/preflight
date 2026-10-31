"""CAP Code rule pack: dated YAML snapshot -> CapRule records the checker cites by rule number."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

SNAPSHOT_DIR = Path(__file__).resolve().parents[3] / "data" / "snapshots"


class CapRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule: str
    section: str
    summary: str
    breach_evidence: str
    screenable: bool
    url: str


class CapRulePack(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    latest_amendment_seen: str
    rules: dict[str, CapRule]


def snapshot_path(version: str) -> Path:
    return SNAPSHOT_DIR / f"cap-s15-{version}.yaml"


def load_cap_rules(snapshot: str | Path) -> CapRulePack:
    """Load a rule pack by version (e.g. "2026-10-31") or by path."""
    path = Path(snapshot) if str(snapshot).endswith(".yaml") else snapshot_path(str(snapshot))
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = {}
    for item in data["rules"]:
        section = item["rule"].split(".")[0]
        if item["rule"] in rules:
            raise ValueError(f"duplicate CAP rule {item['rule']} in {path.name}")
        rules[item["rule"]] = CapRule(section=section, url=data["sections"][section], **item)
    return CapRulePack(
        version=str(data["version"]),
        latest_amendment_seen=str(data["latest_amendment_seen"]),
        rules=rules,
    )
