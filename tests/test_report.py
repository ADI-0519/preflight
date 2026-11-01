import re
from datetime import UTC, date, datetime
from html import escape

import pytest

from preflight.report import render_html
from preflight.schema import (
    NOTICE,
    Ad,
    CapRuleRef,
    Claim,
    Flag,
    OnScreenEvidence,
    OnScreenText,
    Region,
    RegionEvidence,
    RegisterRef,
    RulingRef,
    Screening,
    Segment,
    Snapshots,
    StageRun,
    SuggestedWording,
    Track,
    TranscriptEvidence,
)
from preflight.sources.register import load_register

REGISTER = {e.register_id: e for e in load_register("2026-05-19")}
TIREDNESS = "gbhc-e1f78000ec6b"
SNAPSHOTS = Snapshots(gb_register="2026-05-19", on_hold="2021-01-12", cap_rules="2026-10-31", rulings="2026-11-01")
RULING = "A26-1341476"
REASON = "Nothing on the register covers this wording."
STAGES = tuple(StageRun(stage=s, status="done", model="m", prompt="p") for s in ("transcribe", "claims", "check"))
FORBIDDEN = re.compile(r"\b(compliant|compliance|pass(es|ed)?|approv\w*|cleared|ready to (run|publish))\b", re.I)


def build(*, flags=(), claims=None, stages=STAGES, tracks=(), claim_text="Boosts energy all day") -> Screening:
    segments = (
        Segment(segment_id="segment-0", turn=0, text="Boosts energy all day", start=1.0, end=3.5, timing="turn"),
    )
    on_screen = (OnScreenText(text_id="text-0", text="Natural focus", start=0.5, end=4.0),)
    claims = claims or (
        Claim(
            claim_id="claim-0", text=claim_text, kind="explicit", substance="caffeine",
            evidence=(TranscriptEvidence(segment_id="segment-0"), OnScreenEvidence(text_id="text-0")),
        ),
        Claim(
            claim_id="claim-1", text="Made in Britain", kind="explicit",
            evidence=(OnScreenEvidence(text_id="text-0"),),
        ),
    )
    return Screening(
        screening_id="scr-1",
        ad=Ad(content_hash="a" * 64, media="video", width=320, height=180, duration=8.0, fps=2.0),
        snapshots=SNAPSHOTS, stages=stages, screened_at=datetime(2026, 11, 1, 9, 30, tzinfo=UTC),
        segments=segments, on_screen=on_screen, tracks=tracks, claims=claims, flags=flags,
    )


def breach(flag_id="flag-0", rules=("15.1.1",), wording=None) -> Flag:
    return Flag(
        flag_id=flag_id, claim_id="claim-0", kind="possible_breach", reason=REASON,
        sources=tuple(CapRuleRef(rule=r) for r in rules), suggested_wording=wording,
    )


def variants():
    wording = SuggestedWording.from_entry(REGISTER[TIREDNESS])
    flagged = build(flags=(breach(wording=wording), breach("flag-1", ("3.7",))))
    failed = (*STAGES[:2], StageRun(stage="check", status="failed", model="m"))
    return [build(), flagged, build(stages=failed)]


def test_clean_result_names_every_dated_source():
    page = render_html(build())
    assert "No issues found against" in page
    for day in ("2026-05-19", "2021-01-12", "2026-10-31", "2026-11-01"):
        assert day in page


@pytest.mark.parametrize("status", ["failed", "skipped", None])
def test_unfinished_extraction_does_not_claim_that_the_ad_has_no_claims(status):
    stages = (() if status is None else (StageRun(stage="claims", status=status),))
    stages += (StageRun(stage="check", status="skipped"),)
    screening = build(stages=stages).model_copy(update={"claims": ()})
    page = render_html(screening)
    assert "No claims were found in the ad" not in page
    assert "no claim result is available" in page


def test_completed_empty_extraction_can_report_that_no_claims_were_found():
    screening = build().model_copy(update={"claims": ()})
    assert "No claims were found in the ad" in render_html(screening)


@pytest.mark.parametrize("screening", variants())
def test_notice_is_on_every_report(screening):
    assert escape(NOTICE) in render_html(screening)


# rules 1 and 4: nothing in our wording clears an ad
@pytest.mark.parametrize("screening", variants())
def test_no_clearance_wording(screening):
    page = render_html(screening)
    for quoted in (REASON, escape(REGISTER[TIREDNESS].wording)):
        page = page.replace(quoted, "")
    assert FORBIDDEN.search(page) is None


def test_flags_on_one_claim_are_grouped():
    page = render_html(build(flags=(breach(), breach("flag-1", ("3.7",)))))
    assert page.count("<h3>") == 1
    claim_part = page.split("Boosts energy all day”</h3>")[1].split("Claims with no flag raised")[0]
    assert claim_part.count('class="flag"') == 2
    assert "15.1.1" in claim_part and "3.7" in claim_part
    assert "Made in Britain" in page.split("Claims with no flag raised")[1]


def test_flag_sources_and_evidence_are_shown():
    flag = Flag(
        flag_id="flag-0", claim_id="claim-0", kind="possible_breach", reason=REASON,
        sources=(
            CapRuleRef(rule="15.1.1"), RegisterRef(register_id=TIREDNESS),
            RulingRef(ruling_id=RULING, date=date(2026, 10, 14)),
        ),
    )
    page = render_html(build(flags=(flag,)))
    assert "Possible breach" in page and TIREDNESS in page
    assert f"{RULING}</a>, 14 October 2026" in page
    assert 'href="https://www.asa.org.uk/rulings/unicorn-brands-ltd-a26-1341476' in page
    assert "Heard 0:01.0–0:03.5" in page and "whole turn" in page
    assert "On screen 0:00.5–0:04.0" in page


def test_suggested_wording_is_shown_verbatim_with_its_id():
    wording = SuggestedWording.from_entry(REGISTER[TIREDNESS])
    page = render_html(build(flags=(breach(wording=wording),)))
    assert f"Register wording ({TIREDNESS}): “{escape(wording.wording)}”" in page


def test_ad_text_is_escaped():
    page = render_html(build(claim_text="<script>alert(1)</script>"))
    assert "<script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def with_track(crop):
    region = Region(frame_time=1.0, box=(0, 0, 10, 10), crop=crop)
    track = Track(track_id="track-0", prompt="label", regions=(region,))
    claim = Claim(
        claim_id="claim-0", text="Label claim", kind="explicit",
        evidence=(RegionEvidence(track_id="track-0", frame_time=1.0),),
    )
    return build(flags=(breach(),), claims=(claim,), tracks=(track,))


def test_region_crop_is_embedded(tmp_path):
    (tmp_path / "crops").mkdir()
    (tmp_path / "crops" / "c.png").write_bytes(b"png")
    assert "data:image/png;base64,cG5n" in render_html(with_track("crops/c.png"), tmp_path)


def test_missing_crop_is_said(tmp_path):
    assert "crop not available" in render_html(with_track("crops/gone.png"), tmp_path)
    assert "crop not available" in render_html(with_track(None))


def test_claims_are_not_listed_as_unflagged_when_the_check_failed():
    page = render_html(variants()[2])
    assert "Claims not checked" in page and "Claims with no flag raised" not in page


def test_evidence_cited_by_several_claims_is_quoted_once():
    page = render_html(build(flags=(breach(), breach("flag-1", ("3.7",)).model_copy(update={"claim_id": "claim-1"}))))
    assert page.count("“Natural focus”") == 1 and "(quoted above)" in page


def test_an_ad_with_no_claims_says_so():
    skipped = (*STAGES[:2], StageRun(stage="check", status="skipped"))
    page = render_html(build(stages=skipped).model_copy(update={"claims": ()}))
    assert "No claims were found" in page and "Incomplete" in page and "No issues found against" not in page


@pytest.mark.parametrize("absolute", [False, True])
def test_crop_cannot_read_outside_its_root(tmp_path, absolute):
    root = tmp_path / "crops"
    root.mkdir()
    sentinel = tmp_path / "synthetic.txt"
    sentinel.write_bytes(b"SYNTHETIC_SENTINEL")
    path = str(sentinel) if absolute else "../synthetic.txt"
    page = render_html(with_track(path), root)
    assert "crop not available" in page and "data:image/png;base64," not in page


def test_crop_symlink_cannot_escape_its_root(tmp_path):
    root = tmp_path / "crops"
    root.mkdir()
    sentinel = tmp_path / "synthetic.txt"
    sentinel.write_bytes(b"SYNTHETIC_SENTINEL")
    try:
        (root / "escape.png").symlink_to(sentinel)
    except OSError:
        pytest.skip("symlinks are not permitted on this system")
    assert "crop not available" in render_html(with_track("escape.png"), root)


def test_crop_at_another_time_is_not_shown_as_the_cited_frame(tmp_path):
    (tmp_path / "c.png").write_bytes(b"png")
    s = with_track(None)
    track = s.tracks[0].model_copy(update={"regions": (
        Region(frame_time=1.0, box=(0, 0, 10, 10)),
        Region(frame_time=2.0, box=(0, 0, 10, 10), crop="c.png"),
    )})
    assert "crop not available" in render_html(s.model_copy(update={"tracks": (track,)}), tmp_path)
