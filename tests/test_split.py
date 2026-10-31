import re
from collections import Counter

import pytest
import yaml

from preflight.eval.split import EVAL_DIR, advertiser_key, load_ground_truth, load_split, load_team_ad
from preflight.sources.register import load_register
from preflight.sources.rulings import load_ruling_index

DISCLAIMER = (
    "Food supplements should not be used as a substitute for a varied and balanced diet and a healthy lifestyle."
)


@pytest.fixture(scope="module")
def split():
    return load_split("v1")


def test_no_item_in_both_dev_and_test(split):
    assert not set(split.dev) & set(split.test)
    assert len(split.items) == len(set(split.items))


def test_test_rulings_are_more_recent_than_dev(split):
    index = {r.ruling_id: r for r in load_ruling_index("2026-10-31")}
    dev = [index[i].date for i in split.dev if i in index]
    test = [index[i].date for i in split.test if i in index]
    assert min(test) >= max(dev)


def test_rulings_are_in_the_corpus_and_capped_per_advertiser(split):
    index = {r.ruling_id: r for r in load_ruling_index("2026-10-31")}
    rulings = split.excluded_ruling_ids()
    assert rulings <= set(index)
    advertisers = Counter(advertiser_key(index[i].advertiser) for i in rulings)
    assert max(advertisers.values()) <= 2


def test_every_item_has_ground_truth(split):
    for item in split.items:
        truth = load_ground_truth("v1", item)
        assert truth.item_id == item
        if truth.kind == "ruling":
            assert truth.label == "positive" and truth.claims
        else:
            assert truth.label == "negative" and not truth.claims
    files = {p.stem for p in (EVAL_DIR / "ground_truth" / "v1").glob("*.json")}
    assert files == set(split.items)


def test_ground_truth_cites_cap_rule_numbers(split):
    # a ruling page's rule list can be wrong ("15.11" for 15.1.1), so rules follow the assessment text
    for item in split.excluded_ruling_ids():
        for claim in load_ground_truth("v1", item).claims:
            assert claim.rules and all(re.fullmatch(r"\d{1,2}(\.\d{1,2}){1,2}", r) for r in claim.rules), item


def test_excluded_ids_are_the_rulings_only(split):
    excluded = split.excluded_ruling_ids()
    assert not any(i.startswith("T") for i in excluded)
    assert excluded == {i for i in split.items if not i.startswith("T")}


def test_team_ads_use_only_authorised_register_wording(split):
    register = {e.register_id: e for e in load_register("2026-05-19")}
    for item in (i for i in split.items if i.startswith("T")):
        ad = load_team_ad(item)
        entries = [register[r] for r in ad.register_ids]
        assert all(e.status == "authorised" and not e.proprietary for e in entries)
        claims = ad.voiceover if ad.format == "video" else " ".join(ad.on_screen_text)
        for e in entries:
            assert e.wording in claims, (item, e.register_id)
        assert DISCLAIMER in ad.on_screen_text


def test_manifest_counts_match_lists():
    data = yaml.safe_load((EVAL_DIR / "splits" / "v1.yaml").read_text(encoding="utf-8"))
    for part in ("dev", "test"):
        teams = sum(1 for i in data[part] if i.startswith("T"))
        assert data["counts"][part] == {"positive": len(data[part]) - teams, "negative": teams}


def test_frozen_split_is_fully_checked(split):
    if split.frozen:
        assert all(load_ground_truth("v1", i).checked_by for i in split.items)
