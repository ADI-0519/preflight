import re
from collections.abc import Mapping, Sequence

from rank_bm25 import BM25Okapi

from preflight.eval.split import Split, advertiser_key, load_split
from preflight.sources.rulings import Ruling, load_ruling_index, load_rulings

_WORD = re.compile(r"\w+")


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _split_advertisers(split: Split, advertisers: Mapping[str, str]) -> set[str]:
    held_back = split.excluded_ruling_ids()
    missing = sorted(held_back - advertisers.keys())
    if missing:
        raise ValueError(f"split {split.version} ruling {missing[0]} has no advertiser on record")
    return {advertiser_key(advertisers[i]) for i in held_back}


def eligible(rulings: Sequence[Ruling], split: Split) -> list[Ruling]:
    advertisers = _split_advertisers(split, {r.ruling_id: r.advertiser for r in rulings})
    held_back = split.excluded_ruling_ids()
    return [r for r in rulings if r.ruling_id not in held_back and advertiser_key(r.advertiser) not in advertisers]


class PrecedentIndex:
    def __init__(
        self,
        rulings: Sequence[Ruling],
        split: Split,
        version: str,
        split_advertisers: Mapping[str, str] | None = None,
    ):
        if split_advertisers is None:
            split_advertisers = {m.ruling_id: m.advertiser for m in load_ruling_index(version)}
        advertisers = _split_advertisers(split, split_advertisers)
        held_back = split.excluded_ruling_ids()
        for r in rulings:
            # rule 5: held-back rulings never reach the precedent index
            if r.ruling_id in held_back or advertiser_key(r.advertiser) in advertisers:
                raise ValueError(f"ruling {r.ruling_id} is a split ruling or shares a split advertiser")
        self.version = version
        self.rulings = tuple(rulings)
        self._bm25 = BM25Okapi([_tokens(f"{r.ad_description} {r.assessment}") for r in rulings])

    def top(self, query: str, k: int = 3) -> list[Ruling]:
        scores = self._bm25.get_scores(_tokens(query))
        ranked = sorted(zip(scores, self.rulings, strict=True), key=lambda pair: pair[0], reverse=True)
        return [r for score, r in ranked[:k] if score > 0]


def load_precedents(version: str, split_version: str = "v1") -> PrecedentIndex:
    split = load_split(split_version)
    in_snapshot = {m.ruling_id for m in load_ruling_index(version)}
    rulings = [r for r in eligible(load_rulings(), split) if r.ruling_id in in_snapshot]
    if not rulings:
        raise ValueError(f"no eligible rulings in snapshot {version}")
    return PrecedentIndex(rulings, split, version)
