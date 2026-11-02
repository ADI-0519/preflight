import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from preflight.schema import (
    NOTICE,
    WEB_SCHEMA,
    CapRuleRef,
    Claim,
    Flag,
    OnHoldRef,
    Screening,
    SuggestedWording,
    json_schema,
    verify_sources,
)
from preflight.sources.register import load_register

REGISTER = load_register("2026-05-19")
AUTHORISED = next(e for e in REGISTER if e.status == "authorised" and e.substance == "Magnesium")
NON_AUTHORISED = next(e for e in REGISTER if e.status == "non_authorised")
SPOKEN = {"kind": "transcript", "segment_id": "s1"}
BANNED = re.compile(r"complian|approv|pass|ready|publish|clear|safe", re.IGNORECASE)


def screening(**overrides) -> dict:
    fields = {
        "screening_id": "scr-1",
        "ad": {"content_hash": "a" * 64, "media": "video", "width": 1280, "height": 720, "duration": 30.0, "fps": 30},
        "snapshots": {
            "gb_register": "2026-05-19",
            "on_hold": "2021-01-12",
            "cap_rules": "2026-10-31",
            "rulings": "2026-10-31",
        },
        "stages": [
            {"stage": "transcribe", "status": "done", "model": "muse-voice-transcribe-1.0"},
            {"stage": "claims", "status": "done", "model": "muse-spark-1.3", "prompt": "1", "effort": "low"},
            {"stage": "check", "status": "done", "model": "muse-spark-1.3", "prompt": "judge_v3", "effort": "high"},
        ],
        "screened_at": "2026-10-31T12:00:00Z",
        "segments": [
            {"segment_id": "s1", "turn": 0, "start": 0.4, "end": 3.1, "text": "Calms your mind.", "timing": "word"}
        ],
        "tracks": [{"track_id": "t1", "prompt": "label", "regions": [{"frame_time": 23 / 30, "box": [1, 2, 30, 40]}]}],
        "claims": [
            {
                "claim_id": "c1",
                "text": "Calms your mind.",
                "kind": "explicit",
                "evidence": [SPOKEN, {"kind": "region", "track_id": "t1", "frame_time": 23 * (1 / 30)}],
            }
        ],
        "flags": [
            {
                "flag_id": "f1",
                "claim_id": "c1",
                "kind": "possible_breach",
                "reason": "No authorised claim for magnesium mentions calm.",
                "sources": [{"kind": "cap_rule", "rule": "15.1.1"}],
                "suggested_wording": {"register_id": AUTHORISED.register_id, "wording": AUTHORISED.wording},
            }
        ],
    }
    return fields | overrides


def with_flag(**changes) -> dict:
    fields = screening()
    fields["flags"][0] |= changes
    return fields


def test_valid_screening_round_trips():
    s = Screening.model_validate(screening())
    assert Screening.model_validate_json(s.model_dump_json()) == s
    assert s.notice == NOTICE
    verify_sources(s)


def test_frame_times_match_to_the_millisecond():
    # 23/30 and 23*(1/30) differ in the last bit; the fixture uses one for the region, the other for the evidence
    assert 23 / 30 != 23 * (1 / 30)
    Screening.model_validate(screening())


def test_rule_3_flag_needs_a_source():
    with pytest.raises(ValidationError):
        Flag(flag_id="f1", claim_id="c1", kind="possible_breach", reason="r", sources=[])


def test_rule_3_claim_needs_evidence():
    with pytest.raises(ValidationError):
        Claim(claim_id="c1", text="t", kind="explicit", evidence=[])


@pytest.mark.parametrize(
    "fields, message",
    [
        (with_flag(sources=[{"kind": "ruling", "ruling_id": "A25-1234"}]), "date"),
        (with_flag(claim_id="c9"), "unknown claim"),
        (
            screening(
                claims=[
                    {
                        "claim_id": "c1",
                        "text": "t",
                        "kind": "explicit",
                        "evidence": [{"kind": "on_screen", "text_id": "o1"}],
                    }
                ]
            ),
            "missing from the screening",
        ),
    ],
    ids=["ruling-without-date", "flag-on-unknown-claim", "dangling-evidence"],
)
def test_rule_3_references_resolve(fields, message):
    with pytest.raises(ValidationError, match=message):
        Screening.model_validate(fields)


def test_rule_2_suggested_wording_from_entry():
    wording = SuggestedWording.from_entry(AUTHORISED)
    assert (wording.register_id, wording.wording) == (AUTHORISED.register_id, AUTHORISED.wording)
    with pytest.raises(ValueError, match="not an authorised"):
        SuggestedWording.from_entry(NON_AUTHORISED)


@pytest.mark.parametrize(
    "fields",
    [
        with_flag(
            suggested_wording={"register_id": AUTHORISED.register_id, "wording": "Magnesium helps you feel calm."}
        ),
        with_flag(suggested_wording={"register_id": NON_AUTHORISED.register_id, "wording": NON_AUTHORISED.wording}),
        with_flag(sources=[{"kind": "register", "register_id": "gbhc-000000000000"}]),
        with_flag(sources=[{"kind": "cap_rule", "rule": "99.9"}]),
        with_flag(kind="on_hold", sources=[{"kind": "on_hold", "on_hold_id": "0"}]),
    ],
    ids=[
        "paraphrased-wording",
        "non-authorised-wording",
        "unknown-register-id",
        "unknown-cap-rule",
        "unknown-on-hold-id",
    ],
)
def test_rules_2_and_3_sources_verified_against_snapshots(fields):
    s = Screening.model_validate(fields)
    with pytest.raises(ValueError):
        verify_sources(s)


@pytest.mark.parametrize(
    "ruling_id, day, listed",
    [("A26-1341476", "2026-10-14", True), ("A26-1341476", "2026-10-15", False), ("A26-0000000", "2026-10-14", False)],
    ids=["listed", "wrong-date", "absent"],
)
def test_ruling_refs_are_checked_against_the_rulings_snapshot(ruling_id, day, listed):
    s = Screening.model_validate(with_flag(sources=[{"kind": "ruling", "ruling_id": ruling_id, "date": day}]))
    if listed:
        verify_sources(s)
    else:
        with pytest.raises(ValueError, match="absent from its snapshot"):
            verify_sources(s)


def test_on_hold_flags_cite_on_hold_and_breaches_cite_more():
    common = {"flag_id": "f1", "claim_id": "c1", "reason": "r"}
    with pytest.raises(ValidationError, match="cites no on-hold entry"):
        Flag(**common, kind="on_hold", sources=[CapRuleRef(rule="15.1.1")])
    with pytest.raises(ValidationError, match="not breach evidence"):
        Flag(**common, kind="possible_breach", sources=[OnHoldRef(on_hold_id="2843")])
    Flag(**common, kind="on_hold", sources=[OnHoldRef(on_hold_id="2843")])


@pytest.mark.parametrize(
    "model", ["muse-spark-1.3-contributor", "MUSE-SPARK-1.3-CONTRIBUTOR", "muse-spark-1.3-contributor@2026"]
)
def test_rule_10_contributor_model_rejected(model):
    with pytest.raises(ValidationError, match="contributor"):
        Screening.model_validate(screening(stages=[{"stage": "claims", "status": "done", "model": model}]))


def test_rule_1_clean_result_names_dated_sources():
    s = Screening.model_validate(screening(flags=[]))
    assert s.headline == (
        "No issues found against the GB register (2026-05-19), the on-hold list (2021-01-12), "
        "the CAP Code rule pack (2026-10-31) and the ASA rulings index (2026-10-31)."
    )
    assert Screening.model_validate(screening()).headline.startswith("1 flag on 1 claim, checked against")


@pytest.mark.parametrize("flags", [[], screening()["flags"]], ids=["no-flags", "with-flags"])
def test_rule_1_failed_stage_never_reads_clean(flags):
    stages = [{"stage": "transcribe", "status": "failed"}, {"stage": "claims", "status": "done"}]
    headline = Screening.model_validate(screening(stages=stages, flags=flags)).headline
    assert headline.startswith("Incomplete: transcribe failed.")
    assert "No issues found" not in headline


@pytest.mark.parametrize("version", ["", "v0", "latest"])
def test_rule_1_snapshot_versions_are_dates(version):
    fields = screening()
    fields["snapshots"] = fields["snapshots"] | {"rulings": version}
    with pytest.raises(ValidationError):
        Screening.model_validate(fields)


def test_rules_1_and_4_no_cleared_state():
    schema = json.loads(json_schema())
    words = set()

    def walk(node):
        if isinstance(node, dict):
            words.update(node.get("properties", {}))
            words.update(str(v) for v in node.get("enum", []))
            if "const" in node:
                words.add(str(node["const"]))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    assert {"flags", NOTICE} <= words
    stages = [{"stage": "claims", "status": "failed"}]
    words |= {
        Screening.model_validate(f).headline for f in (screening(), screening(flags=[]), screening(stages=stages))
    }
    assert [w for w in words if BANNED.search(w)] == []


def test_validated_screening_cannot_change():
    s = Screening.model_validate(screening())
    with pytest.raises(ValidationError):
        s.flags = ()
    assert isinstance(s.flags, tuple) and isinstance(s.stages, tuple)
    with pytest.raises(ValidationError):
        s.flags[0].model_copy(update={"sources": ()})
    assert s.model_copy(update={"flags": ()}).headline.startswith("No issues found")


@pytest.mark.parametrize(
    "fields",
    [
        screening(screened_at="2026-10-31T12:00:00"),
        screening(
            segments=[{"segment_id": "s1", "turn": 0, "start": 0, "end": float("inf"), "text": "t", "timing": "word"}]
        ),
        screening(segments=[{"segment_id": "s1", "turn": 0, "start": 29, "end": 31, "text": "t", "timing": "word"}]),
        screening(
            tracks=[{"track_id": "t1", "prompt": "label", "regions": [{"frame_time": 0.767, "box": [50, 50, 1, 1]}]}]
        ),
        screening(
            tracks=[{"track_id": "t1", "prompt": "label", "regions": [{"frame_time": 1, "box": [0, 0, 1, 1]}] * 2}]
        ),
        screening(
            ad={"content_hash": "a" * 64, "media": "image", "width": 10, "height": 10, "duration": 5.0, "fps": 1}
        ),
    ],
    ids=["naive-time", "infinite-time", "past-the-end", "inverted-box", "duplicate-frame", "timed-image"],
)
def test_bad_values_rejected(fields):
    with pytest.raises(ValidationError):
        Screening.model_validate(fields)


def test_web_schema_is_current():
    assert WEB_SCHEMA.read_text(encoding="utf-8") == json_schema(), "run: uv run python -m preflight.schema"
    schema = json.loads(WEB_SCHEMA.read_text(encoding="utf-8"))
    assert "kind" in schema["$defs"]["TranscriptEvidence"]["required"]


def test_a_v1_screening_still_reads():
    saved = json.loads((Path(__file__).parent / "fixtures" / "agent" / "magnesium" / "round0.json").read_text("utf-8"))
    assert saved["schema_version"] == "1"
    assert Screening.model_validate(saved).schema_version == "1"
    with pytest.raises(ValidationError):
        Screening.model_validate(saved | {"schema_version": "3"})
