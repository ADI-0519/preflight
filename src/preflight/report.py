import base64
from functools import cache
from html import escape
from pathlib import Path

from preflight.schema import (
    Claim,
    Flag,
    OnScreenEvidence,
    RegionEvidence,
    Screening,
    TranscriptEvidence,
)
from preflight.sources.cap import load_cap_rules
from preflight.sources.on_hold import load_on_hold
from preflight.sources.register import load_register
from preflight.sources.rulings import load_ruling_index
from preflight.view import clock, span

STYLE = """
body { font: 15px/1.5 system-ui, sans-serif; max-width: 52rem; margin: 2rem auto; padding: 0 1rem; color: #1b1b1b; }
h1 { font-size: 1.3rem; }
h2 { font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #ccc; }
h3 { font-size: 1rem; margin-bottom: 0.2rem; }
table { border-collapse: collapse; }
td, th { border: 1px solid #ccc; padding: 0.2rem 0.6rem; text-align: left; }
.notice { background: #f3f3f3; padding: 0.6rem 0.8rem; border-left: 4px solid #888; }
.claim { border: 1px solid #ccc; padding: 0.5rem 1rem; margin: 1rem 0; }
.flag { border-top: 1px solid #ddd; margin-top: 0.8rem; padding-top: 0.4rem; }
.kind { font-weight: 600; }
img { max-width: 20rem; display: block; border: 1px solid #ccc; }
"""


@cache
def _caps(version: str):
    return load_cap_rules(version).rules


@cache
def _register(version: str):
    return {e.register_id: e for e in load_register(version)}


@cache
def _on_hold(version: str):
    return {c.on_hold_id: c for c in load_on_hold(version)}


@cache
def _rulings(version: str):
    return {m.ruling_id: m for m in load_ruling_index(version)}


def link(url: str, label: str) -> str:
    return f'<a href="{escape(url)}">{escape(label)}</a>'


def crop_image(screening: Screening, e: RegionEvidence, crops: Path | None) -> str:
    track = next(t for t in screening.tracks if t.track_id == e.track_id)
    cited = next(r for r in track.regions if r.frame_time == e.frame_time)
    if crops is None or cited.crop is None:
        return "crop not available"
    root = crops.resolve()
    try:
        path = (root / cited.crop).resolve()
        if Path(cited.crop).is_absolute() or not path.is_relative_to(root) or not path.is_file():
            return "crop not available"
        encoded = base64.b64encode(path.read_bytes()).decode()
    except (OSError, RuntimeError, ValueError):
        return "crop not available"
    return f'<img alt="crop of {escape(track.prompt)}" src="data:image/png;base64,{encoded}">'


def quote(text: str, key: str, seen: set[str]) -> str:
    # a segment cited by many claims is quoted in full once
    if key in seen:
        return " (quoted above)"
    seen.add(key)
    return f": \u201c{escape(text)}\u201d"


def evidence_item(screening: Screening, e, crops: Path | None, seen: set[str]) -> str:
    if isinstance(e, TranscriptEvidence):
        s = next(s for s in screening.segments if s.segment_id == e.segment_id)
        note = " (timing is the whole turn's, not the words')" if s.timing == "turn" else ""
        return f"Heard {span(s.start, s.end)}{quote(s.text, s.segment_id, seen)}{note}"
    if isinstance(e, OnScreenEvidence):
        t = next(t for t in screening.on_screen if t.text_id == e.text_id)
        return f"On screen {span(t.start, t.end)}{quote(t.text, t.text_id, seen)}"
    track = next(t for t in screening.tracks if t.track_id == e.track_id)
    return f"Region \u201c{escape(track.prompt)}\u201d at {clock(e.frame_time)}: {crop_image(screening, e, crops)}"


def source_item(screening: Screening, ref) -> str:
    s = screening.snapshots
    if ref.kind == "cap_rule":
        rule = _caps(s.cap_rules)[ref.rule]
        return f"CAP Code rule {link(rule.url, ref.rule)}: {escape(rule.summary)}"
    if ref.kind == "register":
        entry = _register(s.gb_register)[ref.register_id]
        status = entry.status.replace("_", "-")
        return f"Register entry {escape(ref.register_id)} ({status}): \u201c{escape(entry.wording)}\u201d"
    if ref.kind == "on_hold":
        claim = _on_hold(s.on_hold)[ref.on_hold_id]
        return f"On-hold entry {escape(ref.on_hold_id)}: {escape(' '.join(claim.substance.split()))}"
    ruling = _rulings(s.rulings).get(ref.ruling_id)
    label = f"ASA ruling {ref.ruling_id}"
    name = link(ruling.url, label) if ruling else escape(label)
    return f"{name}, {ref.date:%d %B %Y}"


def flag_block(screening: Screening, flag: Flag) -> str:
    kind = "Possible breach" if flag.kind == "possible_breach" else "On hold"
    sources = "".join(f"<li>{source_item(screening, ref)}</li>" for ref in flag.sources)
    out = [f'<div class="flag"><p><span class="kind">{kind}.</span> {escape(flag.reason)}</p>', f"<ul>{sources}</ul>"]
    if flag.suggested_wording:
        w = flag.suggested_wording
        out.append(f"<p>Register wording ({escape(w.register_id)}): \u201c{escape(w.wording)}\u201d</p>")
    return "".join(out) + "</div>"


def claim_block(screening: Screening, claim: Claim, crops: Path | None, seen: set[str]) -> str:
    items = "".join(f"<li>{evidence_item(screening, e, crops, seen)}</li>" for e in claim.evidence)
    substance = f", substance: {escape(claim.substance)}" if claim.substance else ""
    flags = "".join(flag_block(screening, f) for f in screening.flags if f.claim_id == claim.claim_id)
    return (
        f'<div class="claim"><h3>\u201c{escape(claim.text)}\u201d</h3>'
        f"<p>{escape(claim.kind)}{substance}</p><ul>{items}</ul>{flags}</div>"
    )


def render_html(screening: Screening, crops: Path | None = None) -> str:
    s, ad = screening.snapshots, screening.ad
    versions = [
        ("GB register", s.gb_register), ("On-hold list", s.on_hold), ("CAP Code rule pack", s.cap_rules),
        ("ASA rulings index", s.rulings),
    ]
    sources = "".join(f"<tr><td>{name}</td><td>{version}</td></tr>" for name, version in versions)
    facts = f"{escape(ad.media)}, {ad.width} \u00d7 {ad.height}"
    if ad.duration is not None:
        facts += f", {ad.duration:g} s"
    facts += f", content {ad.content_hash[:12]}, screened {screening.screened_at:%Y-%m-%d %H:%M} UTC"
    stages = "".join(
        f"<tr><td>{escape(r.stage)}</td><td>{r.status}</td><td>{escape(r.model or '')}</td>"
        f"<td>{escape(r.prompt or '')}</td><td>{escape(r.effort or '')}</td></tr>"
        for r in screening.stages
    )
    flagged = {f.claim_id for f in screening.flags}
    # an unjudged claim must not read as one the check let through
    checked = any(r.stage == "check" and r.status == "done" for r in screening.stages)
    rest = "Claims with no flag raised" if checked else "Claims not checked"
    if not screening.claims:
        extracted = any(r.stage == "claims" and r.status == "done" for r in screening.stages)
        empty = (
            "<p>No claims were found in the ad.</p>" if extracted
            else "<p>Claim extraction did not finish; no claim result is available.</p>"
        )
    elif checked:
        empty = "<p>No flags raised.</p>"
    else:
        empty = "<p>The check did not run, so no flags were raised.</p>"
    seen: set[str] = set()
    claims = "".join(claim_block(screening, c, crops, seen) for c in screening.claims if c.claim_id in flagged)
    quiet = "".join(f"<li>\u201c{escape(c.text)}\u201d</li>" for c in screening.claims if c.claim_id not in flagged)
    notice = f'<p class="notice">{escape(screening.notice)}</p>'
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>PreFlight screening {escape(screening.screening_id)}</title>
<style>{STYLE}</style></head><body>
<h1>{escape(screening.headline)}</h1>
{notice}
<h2>Sources and ad</h2>
<table>{sources}</table>
<p>{facts}</p>
<h2>Stages</h2>
<table><tr><th>Stage</th><th>Status</th><th>Model</th><th>Prompt</th><th>Effort</th></tr>{stages}</table>
<h2>Flags, by claim</h2>
{claims or empty}
{f"<h2>{rest}</h2><ul>{quiet}</ul>" if quiet else ""}
<h2>Notice</h2>
{notice}
</body></html>
"""
