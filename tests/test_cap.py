import re
from pathlib import Path

import pytest

from preflight.sources.cap import load_cap_rules

SNAPSHOT = "2026-10-31"
SAMPLE = Path(__file__).resolve().parents[1] / "docs" / "notes" / "ruling-rebuildability-sample.md"


@pytest.fixture(scope="module")
def pack():
    return load_cap_rules(SNAPSHOT)


def rules_cited_in_sample() -> set[str]:
    """Every rule number in the "CAP rules cited" column of the P02 sample table."""
    cited = set()
    for line in SAMPLE.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 6 and re.match(r"^[AG]\d{2}-\d+$", cells[1]):
            cited.update(re.findall(r"\d+(?:\.\d+)+", cells[6]))
    return cited


def test_sample_parsed():
    assert len(rules_cited_in_sample()) == 18


def test_covers_every_rule_cited_by_p02_sample(pack):
    assert rules_cited_in_sample() - pack.rules.keys() == set()


def test_rule_fields(pack):
    rule = pack.rules["15.6.2"]
    assert rule.section == "15"
    assert rule.url == "https://www.asa.org.uk/type/non_broadcast/code_section/15.html"
    assert rule.screenable
    assert pack.rules["12.18"].url.endswith("/code_section/12.html")


def test_conduct_rule_not_screenable(pack):
    assert not pack.rules["1.7"].screenable


def test_version_recorded(pack):
    assert pack.version == "2026-10-31"
    assert pack.latest_amendment_seen == "2026-01-05"
