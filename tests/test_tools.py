import asyncio
import json
from pathlib import Path

import pytest

from preflight.agent import tools
from preflight.agent.fix import FixResult
from preflight.agent.tools import TOOLS, Toolbox
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


def test_screen_summary_carries_sources_and_register_wording(box):
    summary = box.call("screen_ad", {"target": "ad.mp4"})
    assert summary["headline"] == FLAGGED.headline
    assert summary["notice"] == FLAGGED.notice
    assert len(summary["flags"]) == len(FLAGGED.flags)
    for found, flag in zip(summary["flags"], FLAGGED.flags, strict=True):
        assert found["sources"]
        assert found["evidence"]
        if flag.suggested_wording:
            assert found["suggested_wording"] == {
                "register_id": flag.suggested_wording.register_id, "wording": flag.suggested_wording.wording,
            }
        else:
            assert found["suggested_wording"] is None
    assert any(f["suggested_wording"] for f in summary["flags"])
    assert "CAP 15.1" in summary["flags"][0]["sources"]


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
