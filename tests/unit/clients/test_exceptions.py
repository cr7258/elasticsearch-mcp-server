import asyncio
import logging

import httpx
import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from src.clients.error_report import build_report
from src.clients.exceptions import handle_search_exceptions, with_exception_handling

pytestmark = pytest.mark.unit


class FakeMCP:
    """MCP-like stub whose ``tool`` is a stable instance attribute.

    Production ``with_exception_handling`` saves ``mcp.tool`` and later
    reassigns it. We need ``mcp.tool`` to be the same object on every access
    so identity-based restoration assertions are meaningful (bound methods
    rebuild on each attribute access, which would give false negatives).
    """

    def __init__(self):
        self.recorded = []

        def tool(*args, **kwargs):
            def decorator(func):
                self.recorded.append(("decorate", func.__name__, func))
                return func

            return decorator

        self.tool = tool


def test_handle_search_exceptions_returns_value_when_no_exception():
    @handle_search_exceptions
    def succeed(value):
        return value * 2

    assert succeed(3) == 6


def test_handle_search_exceptions_raises_tool_error():
    @handle_search_exceptions
    def fail():
        raise RuntimeError("boom")

    with pytest.raises(ToolError) as excinfo:
        fail()

    assert str(excinfo.value) == "fail failed: internal error"
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__


def test_handler_passes_tool_error_through_unlogged(caplog):
    original = ToolError("deliberate message")

    @handle_search_exceptions
    def tool():
        raise original

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ToolError) as excinfo:
            tool()
    assert excinfo.value is original
    assert str(excinfo.value) == "deliberate message"
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


def test_handler_logs_only_log_line(caplog):
    def handler(request):
        return httpx.Response(
            400,
            json={"error": {"type": "parsing_exception", "reason": "MARKER_BODY"}},
        )

    url = "http://MARKER_HOST:9200/idx/_search?MARKER_Q=1"
    client = httpx.Client(transport=httpx.MockTransport(handler))
    response = client.post(url)
    original = None
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        original = e
    assert original is not None

    @handle_search_exceptions
    def search():
        raise original

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ToolError):
            search()

    expected = build_report("search", original).log_line
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].getMessage() == expected
    for record in caplog.records:
        assert "MARKER_" not in record.getMessage()
        assert "MARKER_" not in (record.exc_text or "")
        assert not record.exc_info


def test_handle_search_exceptions_preserves_function_metadata():
    @handle_search_exceptions
    def documented_tool(arg):
        """Docstring stays intact."""
        return arg

    assert documented_tool.__name__ == "documented_tool"
    assert documented_tool.__doc__ == "Docstring stays intact."


class _ToolThatPassesThrough:
    def register_tools(self, mcp):
        @mcp.tool()
        def succeeding_tool():
            return "fine"

        @mcp.tool()
        def failing_tool():
            raise ValueError("bad")

        self.succeeding_tool = succeeding_tool
        self.failing_tool = failing_tool


def test_with_exception_handling_wraps_registered_tools_with_exception_handler():
    mcp = FakeMCP()
    instance = _ToolThatPassesThrough()

    with_exception_handling(instance, mcp)

    # Each registered function should be exception-wrapped.
    assert instance.succeeding_tool() == "fine"

    with pytest.raises(ToolError) as excinfo:
        instance.failing_tool()
    assert str(excinfo.value) == "failing_tool failed: invalid argument"


def test_with_exception_handling_restores_original_tool_after_use():
    mcp = FakeMCP()
    original_tool = mcp.tool

    with_exception_handling(_ToolThatPassesThrough(), mcp)

    assert mcp.tool is original_tool


def test_with_exception_handling_restores_original_tool_even_on_failure():
    mcp = FakeMCP()
    original_tool = mcp.tool

    class ExplodingToolInstance:
        def register_tools(self, mcp_instance):
            raise RuntimeError("registration failed")

    with pytest.raises(RuntimeError, match="registration failed"):
        with_exception_handling(ExplodingToolInstance(), mcp)

    assert mcp.tool is original_tool


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def test_fastmcp_call_path_reports_error_without_logging_details():
    url = "http://MARKER_USER:MARKER_PW@MARKER_HOST:9200/idx/_search?MARKER_Q=1"
    response = httpx.Response(
        400,
        request=httpx.Request("POST", url),
        json={"error": {"type": "parsing_exception", "reason": "MARKER_BODY"}},
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        original = e

    class _Tools:
        def register_tools(self, mcp):
            @mcp.tool()
            def failing_search() -> dict:
                raise original

    server = FastMCP("test")
    with_exception_handling(_Tools(), server)

    async def call():
        async with Client(server) as client:
            return await client.call_tool("failing_search", {}, raise_on_error=False)

    capture = _Capture()
    targets = [logging.getLogger(n) for n in (None, "fastmcp", "mcp")]
    saved = [t.level for t in targets]
    for t in targets:
        t.addHandler(capture)
        t.setLevel(logging.DEBUG)
    try:
        result = asyncio.run(call())
    finally:
        for t, level in zip(targets, saved):
            t.removeHandler(capture)
            t.setLevel(level)

    safe_line = build_report("failing_search", original).log_line
    text = result.content[0].text
    assert result.is_error is True
    assert text == "failing_search failed: 400\nparsing_exception: MARKER_BODY"
    assert "structured_content must be" not in text

    # The caller message legitimately carries the ES reason; markers for the
    # URL parts and the reason must not appear in any log record.
    assert any("Error calling tool" in r.getMessage() for r in capture.records)
    for r in capture.records:
        blob = (r.getMessage() + (r.exc_text or "")).upper()
        for marker in ("MARKER_USER", "MARKER_PW", "MARKER_HOST", "MARKER_Q", "MARKER_BODY"):
            assert marker not in blob, (marker, r.getMessage())
        assert "TRACEBACK" not in blob
        assert not r.exc_info
    ours = [r for r in capture.records if r.getMessage() == safe_line]
    assert len(ours) >= 1 and all(r.name == "root" for r in ours)
    assert len([r for r in capture.records if r.name == "root" and r.levelno == logging.ERROR]) == 1
