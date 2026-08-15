import asyncio
import json
from types import SimpleNamespace

import pytest
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

from src.response_format import GcfResponseMiddleware, gcf_encoding_enabled

pytestmark = pytest.mark.unit


def _ctx(name: str = "search_documents"):
    return SimpleNamespace(message=SimpleNamespace(name=name))


def _run(result: ToolResult) -> ToolResult:
    async def call_next(context):
        return result

    return asyncio.run(GcfResponseMiddleware().on_call_tool(_ctx(), call_next))


def test_encodes_structured_content_as_gcf():
    data = {"hits": [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]}
    result = ToolResult(
        content=[TextContent(type="text", text=json.dumps(data))],
        structured_content=data,
    )
    out = _run(result)
    text = out.content[0].text
    assert text.startswith("GCF profile=generic")
    assert "## hits [2]{id,name}" in text
    # structuredContent is preserved verbatim (schema validation / non-model clients).
    assert out.structured_content == data


def test_encodes_json_text_when_no_structured_content():
    data = [{"a": 1}, {"a": 2}]
    result = ToolResult(
        content=[TextContent(type="text", text=json.dumps(data))],
        structured_content=None,
    )
    out = _run(result)
    assert out.content[0].text.startswith("GCF profile=generic")


def test_out_of_int64_value_falls_back_to_original():
    # 2^63 is outside GCF's canonical int64 domain (SPEC 2.3.2); encode raises, so the
    # middleware returns the original result unchanged rather than drop the tool call.
    data = {"seq": 2 ** 63}
    original = json.dumps(data)
    result = ToolResult(
        content=[TextContent(type="text", text=original)],
        structured_content=data,
    )
    out = _run(result)
    assert out.content[0].text == original
    assert out.structured_content == data


def test_non_json_content_is_unchanged():
    result = ToolResult(
        content=[TextContent(type="text", text="plain non-JSON message")],
        structured_content=None,
    )
    out = _run(result)
    assert out.content[0].text == "plain non-JSON message"


def test_gcf_encoding_enabled_reads_env(monkeypatch):
    monkeypatch.delenv("RESPONSE_FORMAT", raising=False)
    assert gcf_encoding_enabled() is False
    for value in ("gcf", "GCF", " gcf "):
        monkeypatch.setenv("RESPONSE_FORMAT", value)
        assert gcf_encoding_enabled() is True
    monkeypatch.setenv("RESPONSE_FORMAT", "json")
    assert gcf_encoding_enabled() is False
