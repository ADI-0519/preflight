import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from preflight.claims import PROMPTS, extract_claims, parse
from preflight.eval.claim_recall import score
from preflight.eval.split import EVAL_DIR, load_ground_truth, load_split
from preflight.ingest import Frame, Ingested
from preflight.models import SparkResult
from preflight.models.store import digest
from preflight.schema import Ad, Claim, OnScreenText, Region, Segment, Track, TranscriptEvidence

SEGMENT = Segment(segment_id="segment-0", turn=0, text="Feel calmer every day.", start=0.5, end=2.0, timing="word")
TEXT = OnScreenText(text_id="text-0", text="100% natural", start=1.0, end=3.0, box=(10, 10, 100, 40))
TRACK = Track(
    track_id="bottle-1",
    prompt="bottle",
    regions=(
        Region(frame_time=1.0, box=(0, 0, 50, 90)),
        Region(frame_time=1.5, box=(0, 0, 60, 100), crop="crops/bottle-1.png"),
    ),
)


def claim(text, evidence, kind="explicit", substance=None):
    return {"text": text, "kind": kind, "substance": substance, "evidence": evidence}


class FakeSpark:
    def __init__(self, claims):
        self.claims, self.calls = claims, []

    def ask(self, text, **kwargs):
        self.calls.append((text, kwargs))
        return SparkResult("muse-spark-1.3", "", {"claims": self.claims}, {})


def ingested(tmp_path: Path, media: str) -> Ingested:
    still = tmp_path / "frame.png"
    still.write_bytes(b"png")
    video = media == "video"
    ad = Ad(
        content_hash=digest(still), media=media, width=320, height=180,
        duration=4.0 if video else None, fps=2.0 if video else None,
    )
    return Ingested(
        ad=ad, source=tmp_path / "ad.mp4" if video else still, audio=None, video=None, rate=None, threshold=0.3,
        frames=(Frame(index=0, time=0.0, path=still),), keyframes=(0,),
    )


def run(tmp_path, claims, media="video", segments=(SEGMENT,), texts=(TEXT,), tracks=(TRACK,)):
    spark = FakeSpark(claims)
    found, stage = extract_claims(ingested(tmp_path, media), spark, list(segments), list(texts), list(tracks))
    return found, stage, spark.calls


def test_ids_become_evidence_of_their_kind(tmp_path):
    (c,), stage, _ = run(tmp_path, [claim("Feel calmer", ["segment-0", "text-0", "bottle-1"], substance=" ")])
    assert c.claim_id == "claim-0" and c.substance is None
    assert [e.kind for e in c.evidence] == ["transcript", "on_screen", "region"]
    # a track is cited at the frame its crop was cut from
    assert c.evidence[2].frame_time == 1.5
    assert (stage.stage, stage.status, stage.prompt) == ("claims", "done", "claims_v3")


def test_a_repeated_claim_is_merged_with_all_its_evidence(tmp_path):
    claims, _, _ = run(tmp_path, [
        claim("100% natural", ["text-0"]),
        claim("Feel calmer", ["segment-0"], kind="implied"),
        claim("100% Natural!", ["text-0", "segment-0"], substance="ashwagandha"),
    ])
    assert [(c.text, c.kind, c.substance) for c in claims] == [
        ("100% natural", "explicit", "ashwagandha"), ("Feel calmer", "implied", None),
    ]
    assert [e.kind for e in claims[0].evidence] == ["on_screen", "transcript"]


@pytest.mark.parametrize("substances", [("magnesium", "vitamin C"), ("vitamin C", "magnesium")])
def test_identical_wording_for_different_substances_keeps_its_own_evidence(substances):
    evidence = {f"s-{n}": TranscriptEvidence(segment_id=f"s-{n}") for n in range(2)}
    found = parse({"claims": [
        claim("Supports normal function", [f"s-{n}"], substance=substance)
        for n, substance in enumerate(substances)
    ]}, evidence)
    assert [(c.substance, c.evidence) for c in found] == [
        (substance, (evidence[f"s-{n}"],)) for n, substance in enumerate(substances)
    ]


@pytest.mark.parametrize("substances", [
    (None, "magnesium", "vitamin C"), ("magnesium", None, "vitamin C"), ("magnesium", "vitamin C", None),
])
def test_ambiguous_substance_is_not_assigned_to_either_named_product(substances):
    evidence = {f"s-{n}": TranscriptEvidence(segment_id=f"s-{n}") for n in range(3)}
    found = parse({"claims": [
        claim("Supports normal function", [f"s-{n}"], substance=substance)
        for n, substance in enumerate(substances)
    ]}, evidence)
    assert [(c.substance, c.evidence) for c in found] == [
        (substance, (evidence[f"s-{n}"],)) for n, substance in enumerate(substances)
    ]


def test_substance_capitalisation_and_spacing_do_not_duplicate_a_claim():
    evidence = {f"s-{n}": TranscriptEvidence(segment_id=f"s-{n}") for n in range(2)}
    found = parse({"claims": [
        claim("Supports normal function", ["s-0"], substance="Vitamin C"),
        claim("Supports normal function", ["s-1"], substance=" vitamin   c "),
    ]}, evidence)
    assert len(found) == 1
    assert found[0].substance == "Vitamin C"
    assert found[0].evidence == tuple(evidence.values())


@pytest.mark.parametrize("bad", [claim("Feel calmer", []), claim("  ", ["segment-0"])])
def test_malformed_claims_raise(tmp_path, bad):
    with pytest.raises((ValidationError, ValueError)):
        run(tmp_path, [bad])


def test_unknown_evidence_id_raises():
    with pytest.raises(KeyError):
        parse({"claims": [claim("x", ["segment-9"])]}, {"segment-0": TranscriptEvidence(segment_id="segment-0")})


def test_video_is_sent_with_the_listing_and_an_id_enum(tmp_path):
    _, _, ((prompt, kwargs),) = run(tmp_path, [])
    assert prompt.startswith((PROMPTS / "claims_v3.txt").read_text(encoding="utf-8"))
    assert 'segment-0 [0.5-2 s]: "Feel calmer every day."' in prompt
    assert "bottle-1 [bottle, 1-1.5 s]" in prompt
    assert kwargs["video"] == tmp_path / "ad.mp4" and "image" not in kwargs
    evidence = kwargs["schema"]["properties"]["claims"]["items"]["properties"]["evidence"]
    assert evidence["items"]["enum"] == ["segment-0", "text-0", "bottle-1"]


def test_still_is_sent_as_its_image_and_empty_lists_say_none(tmp_path):
    _, _, ((prompt, kwargs),) = run(tmp_path, [], media="image", segments=(), tracks=())
    assert kwargs["image"] == b"png" and "video" not in kwargs
    assert "Transcript segments:\nnone" in prompt and "Visual tracks:\nnone" in prompt


def test_nothing_to_cite_skips_the_model(tmp_path):
    claims, stage, calls = run(tmp_path, [], segments=(), texts=(), tracks=())
    assert (claims, stage.status, calls) == ([], "skipped", [])


def test_recall_counts_exact_and_near_quotes_only():
    said = [
        Claim(claim_id=f"claim-{n}", text=t, kind="explicit", evidence=(TranscriptEvidence(segment_id="s"),))
        for n, t in enumerate(["It helps you sleep better tonight", "Calm"])
    ]
    assert score(["helps you sleep better", "calm and focused all day", "sleep"], said) == [True, False, True]


def normalised(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold().replace("’", "'")))


# rule 5: no split item's wording or ID reaches the prompt
@pytest.mark.parametrize(
    "path", sorted([*PROMPTS.glob("claims_*.txt"), *PROMPTS.glob("judge_*.txt")]), ids=lambda p: p.stem
)
def test_prompt_holds_no_split_item(path):
    prompt = path.read_text(encoding="utf-8")
    assert not re.search(r"\b[AG]\d{2}-\d{6,8}\b", prompt)
    text = normalised(prompt)
    split = load_split("v1")
    assert len(list((EVAL_DIR / "ground_truth" / "v1").glob("*.json"))) == len(split.items)
    quoted = sorted({
        item_id
        for item_id in split.items
        for c in load_ground_truth("v1", item_id).claims
        # single words such as "energy" are ordinary vocabulary; a phrase of three or more is a quote
        if len(normalised(c.claim).split()) >= 3 and f" {normalised(c.claim)} " in f" {text} "
    })  # fmt: skip
    # item IDs only: pytest would print a failing assert's operands, showing a test claim to the prompt's author
    if quoted:
        pytest.fail(f"{path.name} quotes a ground-truth claim of {', '.join(quoted)}", pytrace=False)


def test_second_pass_is_shown_the_first_and_adds_what_it_missed(tmp_path):
    first = [claim("100% natural", ["text-0"])]
    answers = iter([first, [claim("Feel calmer", ["segment-0"]), *first]])

    class Twice(FakeSpark):
        def ask(self, text, **kwargs):
            self.calls.append((text, kwargs))
            return SparkResult("muse-spark-1.3", "", {"claims": next(answers)}, {})

    spark = Twice([])
    claims, stage = extract_claims(ingested(tmp_path, "video"), spark, [SEGMENT], [TEXT], [TRACK], second_pass=True)
    assert [c.text for c in claims] == ["100% natural", "Feel calmer"]
    assert stage.prompt == "claims_v3+claims_missed_v1"
    (asked, first_kwargs), (second, kwargs) = spark.calls
    assert second.startswith(asked) and '"text": "100% natural"' in second
    # the first call is keyed as a single-pass call, so its cached answer is shared
    assert (first_kwargs["prompt_version"], kwargs["prompt_version"]) == ("claims_v3", "claims_v3+claims_missed_v1")


def test_a_quote_covering_much_more_than_the_claim_scores_only_loosely():
    said = [Claim(
        claim_id="claim-0", text="Feel calmer, sleep deeper and wake up ready for anything the long day brings",
        kind="explicit", evidence=(TranscriptEvidence(segment_id="s"),),
    )]
    assert score(["sleep deeper"], said) == [False]
    assert score(["sleep deeper"], said, tight=False) == [True]
