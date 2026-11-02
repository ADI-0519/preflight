from functools import cache

from preflight.check.shortlist import shortlist
from preflight.eval.check_reconstructions import words
from preflight.schema import Claim, Flag, Screening
from preflight.sources.on_hold import load_on_hold
from preflight.sources.register import load_register
from preflight.sources.rulings import load_ruling_index


@cache
def _register(version: str):
    return load_register(version)


@cache
def _on_hold(version: str):
    return load_on_hold(version)


@cache
def _rulings(version: str):
    return {m.ruling_id: m for m in load_ruling_index(version)}


def clock(t: float) -> str:
    minutes, seconds = divmod(t, 60)
    return f"{int(minutes)}:{seconds:04.1f}"


def span(start: float, end: float) -> str:
    return f"{clock(start)}–{clock(end)}"


def evidence_key(e) -> str:
    if e.kind == "transcript":
        return e.segment_id
    if e.kind == "on_screen":
        return e.text_id
    return f"{e.track_id}@{e.frame_time}"


def _contained(a: str, b: str) -> bool:
    # whole words only, so "cure" is not inside "secure"
    return a != b and f" {a} " in f" {b} "


def fold(screening: Screening) -> list[tuple[Claim, list[Claim]]]:
    flagged_ids = {f.claim_id for f in screening.flags}
    flagged = [c for c in screening.claims if c.claim_id in flagged_ids]
    text = {c.claim_id: " ".join(words(c.text)) for c in flagged}
    keys = {c.claim_id: {evidence_key(e) for e in c.evidence} for c in flagged}
    host: dict[str, Claim] = {}
    for c in flagged:
        # a claim folds under a longer flagged claim that contains it and shares evidence with it
        hosts = [
            h for h in flagged
            if _contained(text[c.claim_id], text[h.claim_id]) and keys[c.claim_id] & keys[h.claim_id]
        ]  # fmt: skip
        if hosts:
            host[c.claim_id] = max(hosts, key=lambda h: len(text[h.claim_id]))
    folded: dict[str, list[Claim]] = {c.claim_id: [] for c in flagged if c.claim_id not in host}
    for c in flagged:
        if c.claim_id in host:
            top = host[c.claim_id]
            while top.claim_id in host:
                top = host[top.claim_id]
            folded[top.claim_id].append(c)
    return [(c, folded[c.claim_id]) for c in flagged if c.claim_id in folded]


def _related(a: str, b: str) -> bool:
    return a == b or a.startswith(b + ".") or b.startswith(a + ".")


def _rules(flags: list[Flag]) -> list[str]:
    seen: dict[str, None] = {}
    for f in flags:
        for r in f.sources:
            if r.kind == "cap_rule":
                seen.setdefault(r.rule)
    return list(seen)


def _split_rules(rules: list[str]) -> tuple[list[str], list[str]]:
    # section 15 rules (food, supplements, health claims) lead
    ordered = [r for r in rules if r.split(".")[0] == "15"] + [r for r in rules if r.split(".")[0] != "15"]
    ancestors = [r for r in ordered if any(o.startswith(r + ".") for o in ordered)]
    return [r for r in ordered if r not in ancestors], ancestors


def _evidence(screening: Screening, e) -> dict:
    out = {"kind": e.kind, "start": None, "end": None, "frame_time": None, "text": None, "track_id": None, "crop": None}
    if e.kind == "region":
        track = next(t for t in screening.tracks if t.track_id == e.track_id)
        cited = next(r for r in track.regions if r.frame_time == e.frame_time)
        # rule 3: the crop shown is the cited frame's own
        crop = cited.crop
        label = f"Region “{track.prompt}” at {clock(e.frame_time)}"
        return out | {"label": label, "frame_time": e.frame_time, "track_id": e.track_id, "crop": crop}
    if e.kind == "transcript":
        s = next(s for s in screening.segments if s.segment_id == e.segment_id)
        return out | {"label": f"Heard {span(s.start, s.end)}", "start": s.start, "end": s.end, "text": s.text}
    t = next(t for t in screening.on_screen if t.text_id == e.text_id)
    if t.end <= t.start:
        label = "On screen (still)" if screening.ad.media == "image" else "On screen, time not read"
    else:
        label = f"On screen {span(t.start, t.end)}"
    return out | {"label": label, "start": t.start, "end": t.end, "text": t.text}


def _first_time(item: dict) -> float:
    t = item["start"] if item["frame_time"] is None else item["frame_time"]
    return float("inf") if t is None or (item["kind"] == "on_screen" and item["end"] <= item["start"]) else t


def _wordings(flags: list[Flag]) -> list[dict]:
    seen: dict[str, dict] = {}
    for f in flags:
        if f.suggested_wording:
            w = f.suggested_wording
            seen.setdefault(w.register_id, {"register_id": w.register_id, "wording": w.wording})
    return list(seen.values())


def _flags_on(screening: Screening, claim: Claim) -> list[Flag]:
    return [f for f in screening.flags if f.claim_id == claim.claim_id]


# rule 3: a line or folded phrase keeps every source its flags cite
def _sources(screening: Screening, flags: list[Flag]) -> dict:
    cited = _rules(flags)
    primary, other = _split_rules(cited)
    index = _rulings(screening.snapshots.rulings)
    rulings = {}
    for f in flags:
        for r in f.sources:
            if r.kind == "ruling" and r.ruling_id not in rulings:
                meta = index.get(r.ruling_id)
                relevant = meta is not None and any(_related(a, b) for a in cited for b in meta.cap_rules)
                rulings[r.ruling_id] = {
                    "ruling_id": r.ruling_id, "date": r.date.isoformat(), "url": meta.url if meta else None,
                    "relevant": relevant,
                }  # fmt: skip
    return {
        "flag_ids": [f.flag_id for f in flags], "reasons": [f.reason for f in flags],
        "primary_rules": primary, "other_rules": other,
        "register_refs": sorted({r.register_id for f in flags for r in f.sources if r.kind == "register"}),
        "on_hold_refs": sorted({r.on_hold_id for f in flags for r in f.sources if r.kind == "on_hold"}),
        "rulings": list(rulings.values()),
    }  # fmt: skip


def _line(screening: Screening, claim: Claim, nested: list[Claim]) -> dict:
    flags = _flags_on(screening, claim)
    sources = _sources(screening, flags)
    folded = [{"claim_id": n.claim_id, "text": n.text} | _sources(screening, _flags_on(screening, n)) for n in nested]
    return {
        "claim_id": claim.claim_id, "text": claim.text, "kind": claim.kind, "substance": claim.substance,
        "evidence": [_evidence(screening, e) for e in claim.evidence],
        "flags": {
            "flag_ids": sources["flag_ids"], "kinds": [f.kind for f in flags], "reasons": sources["reasons"],
        },
        "primary_rules": sources["primary_rules"], "other_rules": sources["other_rules"],
        "suggested_wording": _wordings(flags),
        "register_refs": sources["register_refs"], "on_hold_refs": sources["on_hold_refs"],
        "rulings": sources["rulings"], "folded": folded,
    }  # fmt: skip


# rule 2: wording is the register snapshot's own text
def _may_say(screening: Screening, claims: list[Claim]) -> list[dict]:
    register, on_hold = _register(screening.snapshots.gb_register), _on_hold(screening.snapshots.on_hold)
    by_substance: dict[str, Claim] = {}
    for c in claims:
        if c.substance:
            by_substance.setdefault(" ".join(c.substance.casefold().split()), c)
    shown: set[str] = set()
    out = []
    for claim in by_substance.values():
        entries = []
        for e in shortlist([claim], register, on_hold).register:
            if e.status == "authorised" and e.register_id not in shown:
                shown.add(e.register_id)
                entries.append({"register_id": e.register_id, "wording": e.wording, "conditions": e.conditions})
        out.append({"substance": claim.substance, "entries": entries})
    return out


def _first_line_time(line: dict) -> float:
    return min((_first_time(e) for e in line["evidence"]), default=float("inf"))


def incomplete_stages(screening: Screening) -> list[str]:
    failed = [r.stage for r in screening.stages if r.status == "failed"]
    # rule 1: a check that did not finish leaves the ad unscreened, as a failed one does
    checked = any(r.stage == "check" and r.status == "done" for r in screening.stages)
    return failed if checked or "check" in failed else [*failed, "check"]


def build_view(screening: Screening) -> dict:
    groups = fold(screening)
    lines = sorted((_line(screening, c, nested) for c, nested in groups), key=_first_line_time)
    flagged = {f.claim_id for f in screening.flags}
    ad = screening.ad
    return {
        "screening_id": screening.screening_id, "headline": screening.headline, "notice": screening.notice,
        "snapshots": screening.snapshots.model_dump(),
        "ad": {"media": ad.media, "width": ad.width, "height": ad.height, "duration": ad.duration},
        "incomplete_stages": incomplete_stages(screening),
        "checked": any(r.stage == "check" and r.status == "done" for r in screening.stages),
        "lines": lines,
        "quiet_claims": [{"claim_id": c.claim_id, "text": c.text} for c in screening.claims
                         if c.claim_id not in flagged],
        "may_say": _may_say(screening, [c for c in screening.claims if c.claim_id in flagged]),
    }  # fmt: skip
