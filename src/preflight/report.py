import base64
from functools import cache
from html import escape
from pathlib import Path

from preflight.schema import Flag, Screening
from preflight.sources.cap import load_cap_rules
from preflight.sources.on_hold import load_on_hold
from preflight.sources.register import load_register
from preflight.sources.rulings import load_ruling_index
from preflight.view import build_view

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
.tier { border: 1px solid #888; border-radius: 3px; padding: 0 0.4rem; font-size: 0.8rem; font-weight: 600; }
.tier.high { background: #b42318; border-color: #b42318; color: #fff; }
.tier.medium { background: #f79009; border-color: #f79009; color: #16181b; }
.tier.low { background: #e8eaec; border-color: #e8eaec; }
.tier.unchecked { border-style: dashed; font-weight: 400; }
img { max-width: min(100%, 480px); display: block; border: 1px solid #ccc; }
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


def crop_image(crop: str | None, label: str, crops: Path | None) -> str:
    if crops is None or crop is None:
        return "crop not available"
    root = crops.resolve()
    try:
        path = (root / crop).resolve()
        if Path(crop).is_absolute() or not path.is_relative_to(root) or not path.is_file():
            return "crop not available"
        encoded = base64.b64encode(path.read_bytes()).decode()
    except (OSError, RuntimeError, ValueError):
        return "crop not available"
    return f'<img alt="crop: {escape(label)}" src="data:image/png;base64,{encoded}">'


def quote(text: str, key: str, seen: set[str]) -> str:
    # a segment cited by many claims is quoted in full once
    if key in seen:
        return " (quoted above)"
    seen.add(key)
    return f": “{escape(text)}”"


def evidence_item(e: dict, crops: Path | None, seen: set[str]) -> str:
    label = escape(e["label"])
    if e["kind"] == "region":
        return f"{label}: {crop_image(e['crop'], e['label'], crops)}"
    note = " (timing is the whole turn's, not the words')" if e["timing"] == "turn" else ""
    return f"{label}{quote(e['text'], e['label'] + e['text'], seen)}{note}"


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


def source_label(screening: Screening, ref) -> str:
    if ref.kind == "cap_rule":
        return link(_caps(screening.snapshots.cap_rules)[ref.rule].url, f"CAP {ref.rule}")
    if ref.kind == "register":
        return f"register entry {escape(ref.register_id)}"
    if ref.kind == "on_hold":
        return f"on-hold entry {escape(ref.on_hold_id)}"
    ruling = _rulings(screening.snapshots.rulings).get(ref.ruling_id)
    return link(ruling.url, ref.ruling_id) if ruling else escape(ref.ruling_id)


# rule 3: a folded phrase still cites every source; ones its line already shows in full are named only
def flag_block(screening: Screening, flag: Flag, shown: frozenset = frozenset()) -> str:
    kind = "Possible breach" if flag.kind == "possible_breach" else "On hold"
    sources = "".join(f"<li>{source_item(screening, ref)}</li>" for ref in flag.sources if ref not in shown)
    repeated = [source_label(screening, ref) for ref in flag.sources if ref in shown]
    if repeated:
        sources += f"<li>As above: {', '.join(repeated)}</li>"
    out = [f'<div class="flag"><p><span class="kind">{kind}.</span> {escape(flag.reason)}</p>', f"<ul>{sources}</ul>"]
    if flag.suggested_wording:
        w = flag.suggested_wording
        out.append(f"<p>Register wording ({escape(w.register_id)}): \u201c{escape(w.wording)}\u201d</p>")
    return "".join(out) + "</div>"


TIER_LABEL = {"high": "High", "medium": "Medium", "low": "Low", "unchecked": "Couldn\u2019t check"}
TIER_CAPTION = (
    "Tiers order the review by the CAP rules cited: disease and medicinal claims (CAP 12 and 15.6) first, "
    "then other section 15 and section 3 rules. A tier is not a finding of breach."
)


def tier_chip(tier: str) -> str:
    return f'<span class="tier {tier}">{TIER_LABEL[tier]}</span>'


# rule 1: an order for review, not a verdict
def tier_summary(tiers: dict, flags: int) -> str:
    lines = tiers["high"] + tiers["medium"] + tiers["low"]
    # the headline counts flags, the tiers count lines; say why they differ
    held = "line holds" if lines == 1 else "lines hold"
    grouped = (
        f"<p>{lines} {held} the {flags} flags; a flagged phrase inside a longer line is grouped under it.</p>"
        if flags != lines else ""
    )  # fmt: skip
    order = f"Review order: {tiers['high']} high \u00b7 {tiers['medium']} medium \u00b7 {tiers['low']} low"
    unchecked = f" \u00b7 {TIER_LABEL['unchecked']}: {tiers['unchecked']}" if tiers["unchecked"] else ""
    return f"{grouped}<p>{order}{unchecked}</p><p>{TIER_CAPTION}</p>"


def rule_links(screening: Screening, rules: list[str]) -> str:
    caps = _caps(screening.snapshots.cap_rules)
    return ", ".join(link(caps[r].url, f"CAP {r}") for r in rules)


def line_block(screening: Screening, line: dict, crops: Path | None, seen: set[str]) -> str:
    flags = {f.flag_id: f for f in screening.flags}
    items = "".join(f"<li>{evidence_item(e, crops, seen)}</li>" for e in line["evidence"])
    substance = f", substance: {escape(line['substance'])}" if line["substance"] else ""
    rules = rule_links(screening, line["primary_rules"])
    if line["other_rules"]:
        rules += f"; also under {rule_links(screening, line['other_rules'])}"
    own = [flags[i] for i in line["flags"]["flag_ids"]]
    shown = frozenset(ref for f in own for ref in f.sources)
    blocks = "".join(flag_block(screening, f) for f in own)
    folded = "".join(
        f"<li>“{escape(n['text'])}”" + "".join(flag_block(screening, flags[i], shown) for i in n["flag_ids"]) + "</li>"
        for n in line["folded"]
    )
    nested = f"<p>Flagged phrases inside this line:</p><ul>{folded}</ul>" if folded else ""
    return (
        f'<div class="claim"><h3>{tier_chip(line["tier"])} “{escape(line["text"])}”</h3>'
        f"<p>{escape(line['kind'])}{substance}</p><p>{rules}</p><ul>{items}</ul>{blocks}{nested}</div>"
    )


# rule 2: register wording quoted exactly with its ID, apart from any line's suggested wording
def may_say_block(view: dict) -> str:
    if not view["may_say"]:
        return ""
    parts = []
    for m in view["may_say"]:
        if not m["entries"]:
            parts.append(f"<h3>{escape(m['substance'])}</h3><p>No authorised register entry matches.</p>")
            continue
        entries = "".join(
            f"<li>Register entry {escape(e['register_id'])}: “{escape(e['wording'])}”"
            + (f"<br>Conditions: {escape(e['conditions'])}" if e["conditions"] else "")
            + "</li>"
            for e in m["entries"]
        )
        parts.append(f"<h3>{escape(m['substance'])}</h3><ul>{entries}</ul>")
    lead = (
        "<p>Authorised GB register wording for the substances flagged above, with conditions of use. "
        "It is context for the person deciding, separate from the wording suggested for a line.</p>"
    )
    return f"<h2>What you may say</h2>{lead}{''.join(parts)}"


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
    view = build_view(screening)
    unfinished = view["incomplete_stages"]
    if unfinished:
        unfinished = f'<p class="notice">Stages that did not finish: {escape(", ".join(unfinished))}.</p>'
    # an unjudged claim must not read as one the check let through
    checked = view["checked"]
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
    lines = "".join(line_block(screening, line, crops, seen) for line in view["lines"])
    quiet = "".join(
        f"<li>{tier_chip(c['tier']) + ' ' if c['tier'] else ''}\u201c{escape(c['text'])}\u201d</li>"
        for c in view["quiet_claims"]
    )
    summary = tier_summary(view["tiers"], len(screening.flags)) if view["lines"] else ""
    notice = f'<p class="notice">{escape(screening.notice)}</p>'
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>PreFlight screening {escape(screening.screening_id)}</title>
<style>{STYLE}</style></head><body>
<h1>{escape(screening.headline)}</h1>
{notice}
{unfinished or ""}
<h2>Sources and ad</h2>
<table>{sources}</table>
<p>{facts}</p>
<h2>Stages</h2>
<table><tr><th>Stage</th><th>Status</th><th>Model</th><th>Prompt</th><th>Effort</th></tr>{stages}</table>
<h2>Flagged lines</h2>
{summary}{lines or empty}
{may_say_block(view)}
{f"<h2>{rest}</h2><ul>{quiet}</ul>" if quiet else ""}
<h2>Notice</h2>
{notice}
</body></html>
"""
