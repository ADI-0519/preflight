import asyncio
import json
from pathlib import Path

import pytest

from preflight.agent import tools
from preflight.agent.fix import FixResult
from preflight.agent.publisher import run_publisher
from preflight.agent.tools import TOOLS, Toolbox
from preflight.models import SparkTurn
from preflight.schema import Screening

FIXTURE = Path(__file__).parent / "fixtures" / "agent" / "magnesium"
FLAGGED = Screening.model_validate_json((FIXTURE / "round0.json").read_text(encoding="utf-8"))
CLEAN = FLAGGED.model_copy(update={"flags": ()})


@pytest.fixture
def box(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "screen_target", lambda *a, **k: (FLAGGED, tmp_path / "a.json", tmp_path / "a.html"))
    return Toolbox(None, None, out=tmp_path)


def test_tools_are_strict_schemas():
    for tool in TOOLS:
        assert tool["strict"] is True
        schema = tool["parameters"]
        assert set(schema["required"]) == set(schema["properties"])
        assert schema["additionalProperties"] is False


def test_no_approve_or_publish_tool():
    assert {t["name"] for t in TOOLS} == {"screen_ad", "fix_ad"}


def test_screen_summary_returns_lines_with_sources_and_register_wording(box):
    summary = box.call("screen_ad", {"target": "ad.mp4"})
    assert summary["headline"] == FLAGGED.headline
    assert summary["notice"] == FLAGGED.notice
    lines = summary["lines"]
    assert 0 < len(lines) < len(FLAGGED.flags)
    # rule 3: every flag is shown on a line or a phrase folded under one, with its rules and evidence
    shown = [i for line in lines for i in line["flags"]["flag_ids"]]
    shown += [i for line in lines for n in line["folded"] for i in n["flag_ids"]]
    assert sorted(shown) == sorted(f.flag_id for f in FLAGGED.flags)
    keys = ("primary_rules", "other_rules", "register_refs", "on_hold_refs", "rulings")
    for line in lines:
        assert line["evidence"] and any(line[k] for k in keys)
        assert all(any(n[k] for k in keys) for n in line["folded"])
    assert any(n["on_hold_refs"] and not n["primary_rules"] for line in lines for n in line["folded"])
    # rule 2: wording as the register holds it
    wordings = {f.suggested_wording.register_id: f.suggested_wording.wording for f in FLAGGED.flags
                if f.suggested_wording}
    found = {w["register_id"]: w["wording"] for line in lines for w in line["suggested_wording"]}
    assert found and found.items() <= wordings.items()
    assert all(e["wording"] for m in summary["may_say"] for e in m["entries"])
    assert "15.1.1" in lines[0]["primary_rules"]
    assert all(line["tier"] in ("high", "medium", "low") for line in lines)
    counted = {t: sum(line["tier"] == t for line in lines) for t in ("high", "medium", "low")}
    assert {t: summary["tiers"][t] for t in counted} == counted


def fixed(state, open_=(), screening=CLEAN):
    return lambda *a, **k: FixResult(state, screening, None, Path("audit.jsonl"), list(open_))


def test_fix_awaiting_approval_leaves_approval_to_a_person(box, monkeypatch):
    monkeypatch.setattr(tools, "fix_draft", fixed("awaiting_approval"))
    result = box.call("fix_ad", {"draft": "draft.yaml"})
    assert result["state"] == "awaiting_approval"
    assert result["notice"] == CLEAN.notice
    assert result["next_step"] == tools.AWAITING
    assert "preflight approve" not in json.dumps(result)


def test_handed_over_flags_keep_sources_and_evidence(box, monkeypatch):
    flag = FLAGGED.flags[0]
    group = {"line": "0/voiceover/0", "text": "t", "flags": [
        {"flag_id": flag.flag_id, "kind": flag.kind, "why": flag.reason, "reason": "no authorised wording"},
    ]}
    monkeypatch.setattr(tools, "fix_draft", fixed("needs_person", [group], FLAGGED))
    result = box.call("fix_ad", {"draft": "draft.yaml"})
    handed = result["open"][0]["flags"][0]
    assert handed == tools.flag_summary(FLAGGED, flag) | {"handed_over": "no authorised wording"}
    assert handed["sources"] and handed["evidence"]
    assert result["next_step"] == tools.OPEN


def test_failed_stage_says_incomplete(box, monkeypatch):
    stages = tuple(r.model_copy(update={"status": "failed"}) if r.stage == "check" else r for r in CLEAN.stages)
    failed = CLEAN.model_copy(update={"stages": stages})
    monkeypatch.setattr(tools, "fix_draft", fixed("needs_person", screening=failed))
    result = box.call("fix_ad", {"draft": "draft.yaml"})
    assert result["incomplete_stages"] == ["check"]
    assert result["next_step"] == tools.INCOMPLETE


def test_skipped_check_says_incomplete(box, monkeypatch):
    stages = tuple(r.model_copy(update={"status": "skipped"}) if r.stage == "check" else r for r in CLEAN.stages)
    skipped = CLEAN.model_copy(update={"stages": stages})
    monkeypatch.setattr(tools, "fix_draft", fixed("needs_person", screening=skipped))
    result = box.call("fix_ad", {"draft": "draft.yaml"})
    assert result["incomplete_stages"] == ["check"]
    assert result["next_step"] == tools.INCOMPLETE


def test_tool_errors_are_returned_not_raised(box, monkeypatch):
    def missing(*a, **k):
        raise FileNotFoundError("no such draft")

    def no_scenes(*a, **k):
        raise KeyError("scenes")

    monkeypatch.setattr(tools, "fix_draft", missing)
    assert box.call("fix_ad", {"draft": "x"}) == {"error": "no such draft"}
    monkeypatch.setattr(tools, "fix_draft", no_scenes)
    assert "error" in box.call("fix_ad", {"draft": "x"})
    assert "error" in box.call("screen_ad", {})
    assert "error" in box.call("approve_ad", {})


def test_summary_never_says_compliant_or_approved(box, monkeypatch):
    monkeypatch.setattr(tools, "fix_draft", fixed("awaiting_approval"))
    monkeypatch.setattr(tools, "screen_target", lambda *a, **k: (CLEAN, Path("a.json"), Path("a.html")))
    texts = [
        json.dumps(box.call("screen_ad", {"target": "x"})), json.dumps(box.call("fix_ad", {"draft": "x"})),
    ]
    monkeypatch.setattr(tools, "fix_draft", fixed("needs_person"))
    texts.append(json.dumps(box.call("fix_ad", {"draft": "x"})))
    for text in texts:
        for word in ("compliant", "passes", "approved", "ready to publish", "safe", "cleared"):
            assert word not in text.lower()


class FakeBox:
    def __init__(self):
        self.calls = []

    def call(self, name, arguments):
        self.calls.append((name, arguments))
        return {"headline": "h"}


def test_mcp_lists_the_same_tools():
    pytest.importorskip("mcp")
    from preflight.agent.mcp_server import build_server

    listed = asyncio.run(build_server(FakeBox()).list_tools())
    assert {t.name: t.description for t in listed} == {t["name"]: t["description"] for t in TOOLS}
    for t in listed:
        wanted = next(x for x in TOOLS if x["name"] == t.name)["parameters"]["properties"]
        assert {k: v["description"] for k, v in t.inputSchema["properties"].items()} == {
            k: v["description"] for k, v in wanted.items()
        }


def test_mcp_error_is_a_tool_error():
    pytest.importorskip("mcp")
    from mcp.server.fastmcp.exceptions import ToolError

    from preflight.agent.mcp_server import build_server

    class Broken(FakeBox):
        def call(self, name, arguments):
            return {"error": "no such draft"}

    with pytest.raises(ToolError, match="no such draft"):
        asyncio.run(build_server(Broken()).call_tool("fix_ad", {"draft": "d.yaml"}))


def test_mcp_call_delegates_to_toolbox():
    pytest.importorskip("mcp")
    from preflight.agent.mcp_server import build_server

    fake = FakeBox()
    asyncio.run(build_server(fake).call_tool("fix_ad", {"draft": "d.yaml"}))
    assert fake.calls == [("fix_ad", {"draft": "d.yaml"})]


class ScriptedSpark:
    def __init__(self, *turns):
        self.turns, self.inputs = list(turns), []

    def respond(self, input, **kwargs):
        self.inputs.append(list(input))
        return self.turns.pop(0)


def call_turn(name="screen_ad", call_id="call-1"):
    item = {"type": "function_call", "name": name, "arguments": '{"target": "ad.mp4"}', "call_id": call_id}
    return SparkTurn("muse-spark-1.3", [item], "", {})


def text_turn(text="done"):
    return SparkTurn("muse-spark-1.3", [{"type": "message"}], text, {})


def test_publisher_calls_screen_before_finishing(tmp_path):
    spark, fake = ScriptedSpark(call_turn(), text_turn("the screening found nothing")), FakeBox()
    out = run_publisher(Path("d.yaml"), Path("d.mp4"), spark, fake, out=tmp_path)
    assert fake.calls == [("screen_ad", {"target": "ad.mp4"})]
    assert out["tool_calls"] == 1 and out["final"] == "the screening found nothing"
    saved = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
    assert saved["turns"][0]["calls"][0]["result"] == {"headline": "h"}


def test_publisher_feeds_tool_output_back(tmp_path):
    spark = ScriptedSpark(call_turn(call_id="abc"), text_turn())
    run_publisher(Path("d.yaml"), Path("d.mp4"), spark, FakeBox(), out=tmp_path)
    sent = [i for i in spark.inputs[1] if i["type"] == "function_call_output"]
    assert [i["call_id"] for i in sent] == ["abc"]
    assert json.loads(sent[0]["output"]) == {"headline": "h"}


def test_publisher_turn_limit(tmp_path):
    spark = ScriptedSpark(call_turn(), call_turn(call_id="c2"))
    out = run_publisher(Path("d.yaml"), Path("d.mp4"), spark, FakeBox(), out=tmp_path, max_turns=2)
    assert out["stopped"] == "turn limit" and out["tool_calls"] == 2


def test_publisher_answers_malformed_arguments(tmp_path):
    bad = {"type": "function_call", "name": "screen_ad", "arguments": "{not json", "call_id": "c1"}
    spark, fake = ScriptedSpark(SparkTurn("muse-spark-1.3", [bad], "", {}), text_turn()), FakeBox()
    run_publisher(Path("d.yaml"), Path("d.mp4"), spark, fake, out=tmp_path)
    assert not fake.calls
    sent = [i for i in spark.inputs[1] if i["type"] == "function_call_output"]
    assert "error" in json.loads(sent[0]["output"])


def test_publisher_keeps_run_ids_from_the_model(tmp_path):
    class Stamped(FakeBox):
        def call(self, name, arguments):
            return {"headline": "h", "screening_id": "20261101T120000-x", "report": "r.html", "log": "a.jsonl"}

    spark = ScriptedSpark(call_turn(), text_turn())
    out = run_publisher(Path("d.yaml"), Path("d.mp4"), spark, Stamped(), out=tmp_path)
    sent = [i for i in spark.inputs[1] if i["type"] == "function_call_output"]
    assert json.loads(sent[0]["output"]) == {"headline": "h"}
    assert out["turns"][0]["calls"][0]["result"]["screening_id"] == "20261101T120000-x"


def test_publisher_writes_the_transcript_when_a_turn_fails(tmp_path):
    class Failing(ScriptedSpark):
        def respond(self, input, **kwargs):
            if len(self.inputs) == 1:
                raise RuntimeError("muse-spark-1.3 response failed")
            return super().respond(input, **kwargs)

    with pytest.raises(RuntimeError):
        run_publisher(Path("d.yaml"), Path("d.mp4"), Failing(call_turn()), FakeBox(), out=tmp_path)
    saved = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert saved["tool_calls"] == 1
