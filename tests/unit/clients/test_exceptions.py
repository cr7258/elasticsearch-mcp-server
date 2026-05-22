import pytest
from mcp.types import TextContent

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


def test_handle_search_exceptions_wraps_exception_into_text_content():
    @handle_search_exceptions
    def fail():
        raise RuntimeError("boom")

    result = fail()

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], TextContent)
    assert result[0].type == "text"
    assert "Unexpected error in fail" in result[0].text
    assert "boom" in result[0].text


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

    error_result = instance.failing_tool()
    assert isinstance(error_result, list)
    assert "Unexpected error in failing_tool" in error_result[0].text
    assert "bad" in error_result[0].text


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
