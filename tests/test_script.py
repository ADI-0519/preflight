"""Synthetic script contracts, including a real shared-pipeline pass without media clients."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from preflight.ingest import ingest
from preflight.ingest.script import ScriptError, parse_script
from preflight.models import SparkResult
from preflight.pipeline import SNAPSHOTS, screen
from preflight.report import render_html
from preflight.schema import Ad, Claim, Screening, ScriptEvidence, ScriptLine, StageRun, verify_sources
from preflight.view import build_view


class NoMedia:
    def __getattr__(self, name):
        pytest.fail(f"script invoked a media client: {name}")


class ScriptSpark:
    def __init__(self, *, empty=False, broken=False):
        self.empty, self.broken, self.calls = empty, broken, []

    def ask(self, text, **config):
        self.calls.append(config)
        assert not config.get("image") and not config.get("video")
        if self.broken:
            raise RuntimeError("sensitive script text")
        schema = config["schema"]["properties"]
        if "claims" in schema:
            ids = schema["claims"]["items"]["properties"]["evidence"]["items"]["enum"]
            data = {"claims": [] if self.empty else [{"text": "Treats anxiety", "kind": "explicit",
                    "substance": None, "evidence": ids[:1]}]}
        else:
            assert "Script input only" in text and "VO: " in text
            ids = schema["verdicts"]["items"]["properties"]["claim_id"]["enum"]
            data = {"verdicts": [{"claim_id": i, "verdict": "possible_breach", "cap_rules": ["15.6.2"],
                    "reason": "Synthetic disease-treatment claim.", "register_ids": [],
                    "suggested_register_id": None} for i in ids]}
        return SparkResult("synthetic", "", data, {})


class NoPrecedents:
    version = SNAPSHOTS.rulings

    def top(self, *args, **kwargs):
        return []


def script_result(**changes):
    fields = dict(screening_id="synthetic-script", ad=Ad(content_hash="a" * 64, media="script"),
                  snapshots=SNAPSHOTS, screened_at=datetime.now(UTC), stages=(StageRun(stage="check", status="done"),),
                  script_lines=(ScriptLine(line_number=3, text="VO: Treats anxiety", channel="voiceover"),))
    return Screening(**(fields | changes))


def test_parser_preserves_raw_quotes_channels_and_physical_line_numbers():
    lines = parse_script(b"\xef\xbb\xbfVO: Treats anxiety\r\n\r\n  super: Orange flavour\r\n# Literal <b>copy</b>\n")
    assert [(s.line_number, s.channel, s.text) for s in lines] == [
        (1, "voiceover", "VO: Treats anxiety"), (3, "super", "  super: Orange flavour"),
        (4, "plain", "# Literal <b>copy</b>"),
    ]


@pytest.mark.parametrize(("raw", "error"), [
    (b" \nVO: \n", "empty_script"), (b"\xff", "invalid_script_encoding"),
    (b"copy\x00", "invalid_script_content"), (b"\x1b[31mcopy", "invalid_script_content"),
])
def test_invalid_scripts_have_content_free_errors(raw, error):
    with pytest.raises(ScriptError, match=f"^{error}$"):
        parse_script(raw)


def test_parser_limits_bound_bytes_and_physical_lines():
    with pytest.raises(ScriptError, match="script_too_large"):
        parse_script(b"12345", max_bytes=4)
    with pytest.raises(ScriptError, match="script_too_many_lines"):
        parse_script(b"first\n\nlast", max_lines=2)


def test_unicode_byte_limits_and_literal_markdown():
    raw = "SUPER: Café — ![image](https://untrusted.invalid/ad.png)".encode()
    assert parse_script(raw)[0].text == raw.decode()
    with pytest.raises(ScriptError, match="script_too_large"):
        parse_script(raw, max_bytes=len(raw) - 1)


@pytest.mark.parametrize("case", ["unknown-line", "changed-text", "old-version", "media-evidence", "dimensions"])
def test_script_evidence_and_mode_guards(case):
    evidence = ScriptEvidence(line_number=3, text="VO: Treats anxiety")
    fields = {}
    if case == "unknown-line":
        evidence = ScriptEvidence(line_number=4, text=evidence.text)
    elif case == "changed-text":
        evidence = ScriptEvidence(line_number=3, text="Different source words")
    elif case == "old-version":
        fields["schema_version"] = "2"
    elif case == "media-evidence":
        evidence = {"kind": "on_screen", "text_id": "fake"}
    else:
        with pytest.raises(ValidationError):
            Ad(content_hash="a" * 64, media="script", width=10, height=10)
        return
    with pytest.raises(ValidationError):
        script_result(
            claims=[Claim(claim_id="c", text="Treats anxiety", kind="explicit", evidence=(evidence,))], **fields,
        )


@pytest.mark.parametrize("version", ["1", "2"])
def test_historical_media_still_reads_and_cannot_accept_script_evidence(version):
    fields = dict(schema_version=version, ad=Ad(content_hash="b" * 64, media="image", width=10, height=10),
                  script_lines=())
    assert script_result(**fields).schema_version == version
    with pytest.raises(ValidationError):
        script_result(claims=[Claim(claim_id="c", text="Treats anxiety", kind="explicit",
                                   evidence=(ScriptEvidence(line_number=3, text="VO: Treats anxiety"),))], **fields)


@pytest.mark.parametrize(("empty", "broken"), [(False, False), (True, False), (False, True)])
def test_shared_pipeline_script_pass_has_no_perception_calls(tmp_path, caplog, empty, broken):
    source = tmp_path / "ad.md"
    source.write_text("VO: Treats anxiety\n\nSUPER: <script>alert(1)</script>\n", encoding="utf-8")
    done = ingest(source, tmp_path / "private")
    assert done.frames == () and done.audio is None and done.video is None
    spark = ScriptSpark(empty=empty, broken=broken)
    models = SimpleNamespace(spark=spark, transcribe=NoMedia(), sam=NoMedia(), image=NoMedia())
    stages = []
    result = screen(done, models, NoPrecedents(), judge_samples=1, on_stage=stages.append)
    verify_sources(result)
    assert len(stages) == 5 and all(s.status == "skipped" for s in stages[:3])
    assert "Script only" in result.headline and "finished ad" in result.headline
    assert "sensitive script text" not in caplog.text
    if broken:
        assert "Incomplete" in result.headline
    else:
        assert result.stages[-1].status == "done"
        if empty:
            assert not result.flags and "No issues found against" in result.headline
        else:
            assert result.flags and result.claims[0].evidence[0].line_number == 1
            assert build_view(result)["lines"][0]["evidence"][0]["label"] == "Script line 1"
            html = render_html(result)
            assert "Script line 1" in html and "VO: Treats anxiety" in html


def test_cli_and_agent_tool_use_the_same_script_pipeline(tmp_path, monkeypatch):
    from preflight import cli, pipeline
    from preflight.agent.tools import Toolbox
    from preflight.models import Models

    source = tmp_path / "ad.txt"
    source.write_text("VO: Treats anxiety\n", encoding="utf-8")
    models = Models(ScriptSpark(), NoMedia(), NoMedia(), NoMedia(), None)
    original = ingest
    monkeypatch.setattr(pipeline, "ingest", lambda path: original(path, tmp_path / "private"))
    monkeypatch.setattr(cli, "from_env", lambda: models)
    monkeypatch.setattr(cli, "load_precedents", lambda _: NoPrecedents())
    assert cli.main(["screen", str(source), "--out", str(tmp_path / "cli"), "--no-align"]) == 0
    saved = next((tmp_path / "cli").glob("*.view.json"))
    assert 'Script line 1' in saved.read_text(encoding="utf-8")
    result = Toolbox(models, NoPrecedents(), tmp_path / "agent").call("screen_ad", {"target": str(source)})
    assert "error" not in result and "Script only" in result["headline"]
    assert result["lines"][0]["evidence"][0]["text"] == "VO: Treats anxiety"


def test_joined_script_claim_keeps_every_source_line_and_report_escapes_copy(tmp_path):
    class Joined(ScriptSpark):
        def ask(self, text, **config):
            answer = super().ask(text, **config)
            if "claims" in answer.data and answer.data["claims"]:
                answer.data["claims"][0]["evidence"] = ["script-line-1", "script-line-3"]
            return answer
    path = tmp_path / "script.md"
    path.write_text("VO: <b>Treats\n\nSUPER: anxiety</b>\n", encoding="utf-8")
    result = screen(ingest(path, tmp_path / "private"),
                    SimpleNamespace(spark=Joined(), transcribe=NoMedia(), sam=NoMedia(), image=NoMedia()),
                    NoPrecedents(), judge_samples=1)
    assert [e.line_number for e in result.claims[0].evidence] == [1, 3]
    report = render_html(result)
    assert "&lt;b&gt;Treats" in report and "anxiety&lt;/b&gt;" in report
    assert "<b>Treats" not in report
