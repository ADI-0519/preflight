"""ASA rulings: listing search -> cached HTML pages -> Ruling records with their sections separated.

Full ruling text stays in git-ignored data/raw/rulings/ (docs/source-terms.md). The committed snapshot
holds metadata only: ID, date, advertiser, media, outcome, rules cited, URL.

    uv run python -m preflight.sources.rulings fetch --from 31/10/2023 --to 31/10/2026
    uv run python -m preflight.sources.rulings build --version 2026-10-31
"""

import argparse
import html
import json
import re
import time
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw" / "rulings"
SNAPSHOT_DIR = ROOT / "data" / "snapshots"

BASE = "https://www.asa.org.uk"
LISTING_URL = f"{BASE}/page-types/ruling_page/_filteredRuling/"
USER_AGENT = "PreFlight research crawler (+https://github.com/ADI-0519/preflight)"
DELAY_SECONDS = 10  # docs/source-terms.md: at least 10 s between requests

FOOD_TOPIC = "3706465E-E1B2-4E6A-ABCB7AB8E256827E"  # "Food, drink and supplements"
# The searches whose union makes the candidate list: the topic filter, plus P02's two phrases.
SEARCHES = [{"topic": FOOD_TOPIC}, {"q": "food supplement"}, {"q": "health claims"}]

# Rules that only a health or nutrition claim for a food can breach.
CLAIM_RULES = ("15.1", "15.1.1", "15.2", "15.6", "15.7", "15.8", "15.9", "15.17")

# Rulings the scope test gets wrong, with the reason. Checked by hand.
NOT_IN_SCOPE = {
    "G26-1332433": "less healthy food placement (rule 15.19); the page's rule link mislabels it 15.9",
}

Outcome = Literal["upheld", "upheld in part", "not upheld"]

_RULING_LINK = re.compile(r'href="(https://www\.asa\.org\.uk/rulings/[^"]+\.html)"')
_ID = re.compile(r"\b([AG]\d{2}-\d{6,8})\b", re.IGNORECASE)


class Ruling(BaseModel):
    model_config = ConfigDict(frozen=True)

    ruling_id: str
    url: str
    date: date
    advertiser: str
    media: list[str]
    outcome: Outcome
    background: str | None
    ad_description: str
    issue: str
    response: str | None
    assessment: str
    action: str | None
    cap_rules: list[str]
    bcap_rules: list[str]


class RulingMeta(BaseModel):
    """What the committed snapshot holds: no ruling text."""

    model_config = ConfigDict(frozen=True)

    ruling_id: str
    url: str
    date: date
    advertiser: str
    media: list[str]
    outcome: Outcome
    cap_rules: list[str]
    bcap_rules: list[str]
    topics: list[str]


# Keyword topics for counting. A ruling can have several; this is a count aid, not a classifier.
TOPICS = {
    "adhd-autism": r"\badhd\b|\bautis|\basd\b|attention deficit",
    "menopause-hormonal": r"menopaus|perimenopaus|\bpcos\b|hormon",
    "weight-loss": r"weight loss|lose weight|\bglp-1\b|ozempic|appetite|fat burn|slimming",
    "mushroom": r"mushroom|lion'?s mane|reishi|cordyceps|chaga",
    "magnesium": r"magnesium",
    "gut-digestion": r"\bgut\b|digest|bloat|probiotic|microbiome|\bibs\b",
    "sleep-stress-mood": r"\bsleep|insomnia|anxiety|stress|depress|\bmood\b",
    "immunity": r"immun|cold and flu|covid",
    "cbd": r"\bcbd\b|cannabidiol",
    "hangover": r"hangover",
    "skin-hair-joints": r"\bskin\b|\bhair\b|joint|collagen|arthritis",
    "children": r"\bchild|\bkids?\b|toddler|infant",
}


def text(fragment: str) -> str:
    """HTML fragment -> plain text with paragraph breaks kept."""
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", fragment)
    fragment = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    fragment = re.sub(r"(?i)</(p|h[1-6]|li|div)>", "\n\n", fragment)
    fragment = html.unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in fragment.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _sections(page: str) -> dict[str, str]:
    """Main-content h2 sections keyed by heading, as raw HTML."""
    start = page.find('class="main-content"')
    end = page.find(">More on<", start)
    body = page[start : end if end != -1 else None]
    parts = re.split(r"<h2[^>]*>(.*?)</h2>", body, flags=re.S)
    return {text(parts[i]).rstrip(": "): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def _outcome(raw: str, assessment: str) -> Outcome:
    value = raw.strip().lower()
    if value in ("upheld", "upheld in part", "not upheld"):
        return value  # type: ignore[return-value]
    if not value:
        # A few pages leave the outcome caption blank; read the assessment's point headings instead.
        points = {p.lower() for p in re.findall(r"^(?:\d+\.\s*)?(Not upheld|Upheld)\s*$", assessment, re.M | re.I)}
        if points == {"upheld"}:
            return "upheld"
        if points == {"not upheld"}:
            return "not upheld"
        if points == {"upheld", "not upheld"}:
            return "upheld in part"
    raise ValueError(f"unknown ruling outcome: {raw!r}")


def parse_ruling(page: str, url: str) -> Ruling:
    title = re.search(r'<div class="title-section">(.*?)</ul>', page, re.S)
    if not title:
        raise ValueError(f"no title section in {url}")
    head = title.group(1)
    advertiser = text(re.search(r"<h1[^>]*>(.*?)</h1>", head, re.S).group(1))
    advertiser = re.sub(r"^ASA Ruling on\s+", "", advertiser).replace("\n", " ")
    captions = [text(c) for c in re.findall(r'<span class="caption">(.*?)</span>', head, re.S)]
    outcome, *rest = captions
    ruling_date = datetime.strptime(rest[-1], "%d %B %Y").date()
    media = list(dict.fromkeys(m.strip() for c in rest[:-1] for m in c.split(",") if m.strip()))

    sections = _sections(page)
    code_html = {k: v for k, v in sections.items() if k.startswith("CAP Code") or k.startswith("BCAP Code")}
    cap = [r for k, v in code_html.items() if k.startswith("CAP") for r in re.findall(r">\s*([\d.]+)\s*</a>", v)]
    bcap = [r for k, v in code_html.items() if k.startswith("BCAP") for r in re.findall(r">\s*([\d.]+)\s*</a>", v)]

    found = _ID.search(url) or _ID.search(text(page))
    if not found:
        raise ValueError(f"no ruling ID in {url}")

    def section(name: str) -> str | None:
        return text(sections[name]) if name in sections else None

    for required in ("Ad description", "Issue", "Assessment"):
        if required not in sections:
            raise ValueError(f"{url} has no {required!r} section")
    return Ruling(
        ruling_id=found.group(1).upper(),
        url=url,
        date=ruling_date,
        advertiser=advertiser,
        media=media,
        outcome=_outcome(outcome, text(sections["Assessment"])),
        background=section("Background"),
        ad_description=section("Ad description"),
        issue=section("Issue"),
        response=section("Response"),
        assessment=section("Assessment"),
        action=section("Action"),
        cap_rules=cap,
        bcap_rules=bcap,
    )


def topics(ruling: Ruling) -> list[str]:
    haystack = f"{ruling.background or ''}\n{ruling.ad_description}".lower()
    return [name for name, pattern in TOPICS.items() if re.search(pattern, haystack)]


def in_scope(ruling: Ruling) -> bool:
    """A supplement or health-claim ruling: cites a food-claim rule, or the ad is for a supplement."""
    if ruling.ruling_id in NOT_IN_SCOPE:
        return False
    if any(r == rule or r.startswith(rule + ".") for r in ruling.cap_rules for rule in CLAIM_RULES):
        return True
    return "supplement" in f"{ruling.background or ''}\n{ruling.ad_description}".lower()


def meta(ruling: Ruling) -> RulingMeta:
    return RulingMeta(**ruling.model_dump(include=set(RulingMeta.model_fields)), topics=topics(ruling))


# Fetching


class Fetcher:
    def __init__(self, delay: float = DELAY_SECONDS):
        import httpx

        self.client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True)
        self.delay = delay
        self.last = 0.0

    def request(self, method: str, url: str, **kwargs) -> str:
        for attempt in range(5):
            wait = self.delay * (2**attempt if attempt else 1) - (time.monotonic() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()
            try:
                response = self.client.request(method, url, **kwargs)
                if response.status_code < 500 and response.status_code != 429:
                    response.raise_for_status()
                    return response.text
            except Exception as e:  # connection resets happen after bursts
                if attempt == 4:
                    raise
                print(f"  retry {attempt + 1} after {e!r}", flush=True)
        raise RuntimeError(f"gave up on {url}")


def list_rulings(fetcher: Fetcher, search: dict, from_date: str, to_date: str) -> Iterator[str]:
    seen: set[str] = set()
    for page in range(1, 100):
        form = {
            "page": page, "q": "", "date_period": "", "topic": "", "decision": "", "media_type": "",
            "capCode": "", "bCapCode": "", "from_date": from_date, "to_date": to_date,
            "complexity_type": "Formal", "sort_order": "recent", **search,
        }  # fmt: skip
        links = [u for u in dict.fromkeys(_RULING_LINK.findall(fetcher.request("POST", LISTING_URL, data=form)))]
        new = [u for u in links if u not in seen]
        if not new:
            return
        seen.update(new)
        yield from new


def cache_path(url: str) -> Path:
    return RAW_DIR / url.rsplit("/", 1)[1]


def fetch(from_date: str, to_date: str, delay: float = DELAY_SECONDS) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fetcher = Fetcher(delay)
    urls: dict[str, None] = {}
    for search in SEARCHES:
        found = list(list_rulings(fetcher, search, from_date, to_date))
        print(f"{search}: {len(found)} rulings", flush=True)
        urls.update(dict.fromkeys(found))
    (RAW_DIR / "_candidates.txt").write_text("\n".join(urls) + "\n", encoding="utf-8")
    todo = [u for u in urls if not cache_path(u).exists()]
    print(f"{len(urls)} candidates, {len(todo)} to download", flush=True)
    for i, url in enumerate(todo, 1):
        cache_path(url).write_text(fetcher.request("GET", url), encoding="utf-8")
        print(f"  [{i}/{len(todo)}] {url.rsplit('/', 1)[1]}", flush=True)


# Loading


def load_rulings(raw_dir: Path = RAW_DIR, scope_only: bool = True) -> list[Ruling]:
    """Parse every cached page; by default keep only supplement and health-claim rulings."""
    rulings = {}
    for path in sorted(raw_dir.glob("*.html")):
        url = f"{BASE}/rulings/{path.name}"
        ruling = parse_ruling(path.read_text(encoding="utf-8"), url)
        if not scope_only or in_scope(ruling):
            rulings[ruling.ruling_id] = ruling
    return sorted(rulings.values(), key=lambda r: (r.date, r.ruling_id), reverse=True)


def snapshot_path(version: str) -> Path:
    return SNAPSHOT_DIR / f"rulings-{version}.jsonl"


def load_ruling_index(version: str) -> list[RulingMeta]:
    with snapshot_path(version).open(encoding="utf-8") as f:
        return [RulingMeta.model_validate_json(line) for line in f if line.strip()]


def build(version: str) -> list[RulingMeta]:
    entries = [meta(r) for r in load_rulings()]
    path = snapshot_path(version)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for entry in entries:
            f.write(json.dumps(entry.model_dump(mode="json"), ensure_ascii=False) + "\n")
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and index ASA rulings.")
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--from", dest="from_date", required=True, help="DD/MM/YYYY")
    f.add_argument("--to", dest="to_date", required=True, help="DD/MM/YYYY")
    f.add_argument("--delay", type=float, default=DELAY_SECONDS)
    b = sub.add_parser("build")
    b.add_argument("--version", required=True)
    args = parser.parse_args()
    if args.command == "fetch":
        fetch(args.from_date, args.to_date, args.delay)
    else:
        entries = build(args.version)
        print(f"{len(entries)} in-scope rulings -> {snapshot_path(args.version)}")


if __name__ == "__main__":
    main()
