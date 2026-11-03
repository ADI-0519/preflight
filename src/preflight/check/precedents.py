import re
from collections.abc import Mapping, Sequence
from datetime import date

from rank_bm25 import BM25Okapi

from preflight.eval.split import RULING_ID, Split, advertiser_key, load_split
from preflight.sources.rulings import Ruling, cache_path, load_ruling_index, parse_ruling, ruling_fingerprint

_WORD = re.compile(r"\w+")


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _barred(split: Split, item_id: str | None) -> set[str]:
    if item_id is None:
        return split.excluded_ruling_ids()
    if item_id not in split.items:
        raise ValueError("evaluation item must belong to the requested split")
    # leave one out: on an evaluation item the other dev rulings are fair precedents, test rulings never are
    return {i for i in split.test if RULING_ID.match(i)} | ({item_id} if RULING_ID.match(item_id) else set())


def _barred_advertisers(barred: set[str], split: Split, advertisers: Mapping[str, str]) -> set[str]:
    missing = sorted(barred - advertisers.keys())
    if missing:
        raise ValueError(f"split {split.version} ruling {missing[0]} has no advertiser on record")
    return {advertiser_key(advertisers[i]) for i in barred}


def _published_before(rulings: Sequence[Ruling], item_id: str | None) -> date | None:
    # an item's precedents are the rulings out before its own, so a sibling from the same ASA sweep never counts
    before = next((r.date for r in rulings if r.ruling_id == item_id), None)
    if item_id and RULING_ID.fullmatch(item_id) and before is None:
        raise ValueError("evaluation ruling is missing its publication date")
    return before


def eligible(rulings: Sequence[Ruling], split: Split, item_id: str | None = None) -> list[Ruling]:
    barred = _barred(split, item_id)
    advertisers = _barred_advertisers(barred, split, {r.ruling_id: r.advertiser for r in rulings})
    before = _published_before(rulings, item_id)
    return [
        r for r in rulings
        if r.ruling_id not in barred and advertiser_key(r.advertiser) not in advertisers
        and (before is None or r.date < before)
    ]  # fmt: skip


class PrecedentIndex:
    def __init__(
        self,
        rulings: Sequence[Ruling],
        split: Split,
        version: str,
        split_advertisers: Mapping[str, str] | None = None,
        item_id: str | None = None,
        before: date | None = None,
    ):
        if item_id and RULING_ID.match(item_id) and before is None:
            # rule 5: an item on a ruling needs its ruling's date, or later rulings from its sweep slip in
            raise ValueError(f"an index for {item_id} needs the date of its ruling")
        if split_advertisers is None:
            split_advertisers = {m.ruling_id: m.advertiser for m in load_ruling_index(version)}
        barred = _barred(split, item_id)
        advertisers = _barred_advertisers(barred, split, split_advertisers)
        for r in rulings:
            # rule 5: held-back rulings never reach the precedent index
            if r.ruling_id in barred or advertiser_key(r.advertiser) in advertisers:
                raise ValueError(f"ruling {r.ruling_id} is a split ruling or shares a split advertiser")
            if before and r.date >= before:
                raise ValueError(f"ruling {r.ruling_id} was published on or after the item's own ruling")
        self.version = version
        self.rulings = tuple(rulings)
        self._bm25 = BM25Okapi([_tokens(f"{r.ad_description} {r.assessment}") for r in rulings])

    def top(self, query: str, k: int = 3) -> list[Ruling]:
        scores = self._bm25.get_scores(_tokens(query))
        ranked = sorted(zip(scores, self.rulings, strict=True), key=lambda pair: pair[0], reverse=True)
        return [r for score, r in ranked[:k] if score > 0]


def load_precedents(version: str, split_version: str = "v1", item_id: str | None = None) -> PrecedentIndex:
    split = load_split(split_version)
    snapshot = load_ruling_index(version)
    if len({entry.ruling_id for entry in snapshot}) != len(snapshot):
        raise ValueError("snapshot contains duplicate ruling identities")
    advertisers = {entry.ruling_id: entry.advertiser for entry in snapshot}
    before = _published_before(snapshot, item_id)
    rulings = []
    # Select using metadata before reading any page, including held-out pages.
    for entry in eligible(snapshot, split, item_id):
        path = cache_path(entry.url)
        if not path.is_file():
            raise ValueError(f"eligible ruling {entry.ruling_id} is missing from the local source cache")
        ruling = parse_ruling(path.read_text(encoding="utf-8"), entry.url)
        if (ruling.ruling_id != entry.ruling_id or ruling.date != entry.date
                or advertiser_key(ruling.advertiser) != advertiser_key(entry.advertiser)
                or (entry.content_sha256 and entry.content_sha256 != ruling_fingerprint(ruling))):
            raise ValueError(f"cached ruling differs from snapshot {version}")
        rulings.append(ruling)
    if not rulings:
        raise ValueError(f"no eligible rulings in snapshot {version}")
    return PrecedentIndex(rulings, split, version, advertisers, item_id, before)
