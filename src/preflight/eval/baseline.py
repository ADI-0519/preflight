"""A screen with no model calls (P32), scored by the same harness, so the figures say what the models add.

It reads each item's text as written, not as heard or seen: a reconstruction's shot list, or a team ad's own lines.
A sentence is flagged when it names a register substance without the wording of an authorised entry for it (15.1,
15.1.1), or when it names a term from a fixed list of diseases, conditions and cure words (15.6, 15.6.2).
"""

import argparse
import hashlib
import re
from dataclasses import asdict
from datetime import UTC, datetime
from functools import cache

from preflight.check.shortlist import shortlist
from preflight.eval.check_reconstructions import lines
from preflight.eval.reconstruct import OUT_DIR, ShotList
from preflight.eval.registry import RESULTS, Metric, register, revision, snapshot_text, write_rows
from preflight.eval.run import kept, show
from preflight.eval.score import metrics, score_item
from preflight.eval.split import RULING_ID, load_ground_truth, load_split, load_team_ad
from preflight.pipeline import SNAPSHOTS
from preflight.schema import Ad, CapRuleRef, Claim, Flag, OnScreenEvidence, OnScreenText, Screening, StageRun
from preflight.sources.register import RegisterEntry, load_register

VERSION = "keyword-baseline-v1"
HEALTH_RULES = ("15.1", "15.1.1")
DISEASE_RULES = ("15.6", "15.6.2")
# general medical vocabulary, fixed before any run: conditions, symptoms and the words that claim to cure them
DISEASE_TERMS = (
    "acne", "addiction", "adhd", "allergy", "allergies", "alzheimer's", "alzheimers", "anaemia", "anemia", "anxiety",
    "arthritis", "asthma", "autism", "cancer", "cholesterol", "colds", "covid", "cramps", "cure", "cured", "cures",
    "dementia", "depression", "diabetes", "disease", "diseases", "disorder", "eczema", "flu", "headache",
    "headaches", "heal", "heals", "hypertension", "ibs", "illness", "infection", "infections", "inflammation",
    "insomnia", "menopause", "menopausal", "migraine", "migraines", "obesity", "osteoporosis", "pain", "pcos",
    "psoriasis", "remedy", "symptom", "symptoms", "thyroid", "virus",
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _normalise(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", text.replace("’", "'").replace("‘", "'").lower()))


def sentences(item_id: str) -> list[str]:
    if RULING_ID.match(item_id):
        shots = ShotList.model_validate_json((OUT_DIR / item_id / "shotlist.json").read_text(encoding="utf-8"))
        text = lines(shots)
    else:
        text = load_team_ad(item_id).lines
    return [s for line in text for s in _SENTENCE.split(line.strip()) if s]


@cache
def _register(version: str) -> tuple[RegisterEntry, ...]:
    return tuple(load_register(version))


def judge(sentence: str, register: tuple[RegisterEntry, ...]) -> tuple[list[str], str] | None:
    """The CAP rules a sentence is flagged under, and why, or None."""
    claim = Claim(claim_id="c", text=sentence, kind="explicit", evidence=(OnScreenEvidence(text_id="t"),))
    named = shortlist([claim], register, []).register
    said = _normalise(sentence)
    worded = [w for e in named if e.status == "authorised" and (w := _normalise(e.wording)) in said]
    rest = said
    # an authorised wording may name a condition ("normal thyroid function"); only the words around it are checked
    for w in worded:
        rest = rest.replace(w, " ")
    rules, why = [], []
    if named and not worded:
        rules += HEALTH_RULES
        why.append("names a register substance without an authorised entry's wording")
    found = [t for t in DISEASE_TERMS if re.search(rf"(?<![a-z']){re.escape(t)}(?![a-z'])", rest)]
    if found:
        rules += DISEASE_RULES
        why.append(f"names {', '.join(found)}")
    return (rules, "; ".join(why)) if rules else None


def screen_item(item_id: str) -> Screening:
    register_entries = _register(SNAPSHOTS.gb_register)
    said = sentences(item_id)
    texts = [OnScreenText(text_id=f"text-{n}", text=t, start=0, end=0) for n, t in enumerate(said)]
    claims = [
        Claim(claim_id=f"claim-{n}", text=t.text, kind="explicit", evidence=(OnScreenEvidence(text_id=t.text_id),))
        for n, t in enumerate(texts)
    ]
    flags = []
    for c in claims:
        if verdict := judge(c.text, register_entries):
            rules, why = verdict
            flags.append(Flag(flag_id=f"flag-{len(flags)}", claim_id=c.claim_id, kind="possible_breach",
                              reason=why, sources=tuple(CapRuleRef(rule=r) for r in rules)))  # fmt: skip
    return Screening(
        screening_id=f"baseline-{item_id}",
        ad=Ad(content_hash=hashlib.sha256("\n".join(said).encode()).hexdigest(), media="image", width=1, height=1),
        snapshots=SNAPSHOTS,
        stages=(StageRun(stage="check", status="done", prompt=VERSION),),
        screened_at=datetime.now(UTC),
        on_screen=texts,
        claims=claims,
        flags=flags,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Screen a split part with the keyword baseline and register it.")
    parser.add_argument("--split", default="v2")
    parser.add_argument("--part", choices=["dev", "test"], default="dev")
    args = parser.parse_args()
    sha = revision(args.part)
    truths = [load_ground_truth(args.split, i) for i in getattr(load_split(args.split), args.part)]
    scores = [score_item(t, [screen_item(t.item_id)], kept(t)) for t in truths]
    created = datetime.now(UTC)
    run_id = f"baseline-{created:%Y%m%dT%H%M%S}"
    write_rows(RESULTS / "runs" / f"{run_id}.csv", [asdict(s) for s in scores])
    run_metrics: list[Metric] = metrics(scores)
    register({
        "run_id": run_id, "created_at": created.isoformat(timespec="seconds"), "git_sha": sha, "split": args.split,
        "part": args.part, "stage": "baseline", "model": "none", "prompt": VERSION, "effort": "",
        "snapshots": snapshot_text(SNAPSHOTS),
    }, run_metrics)
    show(run_id, run_metrics)


if __name__ == "__main__":
    main()
