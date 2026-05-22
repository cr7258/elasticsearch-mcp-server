import logging

import pytest

from src.tools.register import ToolsRegister

pytestmark = pytest.mark.unit


class FakeMCP:
    def __init__(self):
        self.registered = []

    def tool(self, *args, **kwargs):
        def decorator(func):
            self.registered.append(func.__name__)
            return func

        return decorator


class FakeToolClass:
    def __init__(self, search_client):
        self.search_client = search_client

    def register_tools(self, mcp):
        @mcp.tool()
        def read_operation():
            return "read"

        @mcp.tool()
        def write_operation():
            return "write"


def test_register_all_tools_delegates_to_exception_handling_when_risk_disabled(
    monkeypatch,
):
    calls = []

    class FakeRiskManager:
        high_risk_ops_disabled = False

    def fake_with_exception_handling(tool_instance, mcp):
        calls.append((tool_instance, mcp))

    monkeypatch.setattr("src.tools.register.risk_manager", FakeRiskManager())
    monkeypatch.setattr(
        "src.tools.register.with_exception_handling", fake_with_exception_handling
    )

    mcp = FakeMCP()
    search_client = object()
    register = ToolsRegister(logging.getLogger("test"), search_client, mcp)

    register.register_all_tools([FakeToolClass])

    assert len(calls) == 1
    assert calls[0][0].search_client is search_client
    assert calls[0][1] is mcp


def test_register_all_tools_filters_disabled_operations_when_risk_enabled(monkeypatch):
    class FakeRiskManager:
        high_risk_ops_disabled = True

        def is_operation_allowed(self, tool_class_name, operation_name):
            return operation_name != "write_operation"

    def call_register_tools(tool_instance, mcp):
        tool_instance.register_tools(mcp)

    monkeypatch.setattr("src.tools.register.risk_manager", FakeRiskManager())
    monkeypatch.setattr("src.tools.register.with_exception_handling", call_register_tools)

    mcp = FakeMCP()
    register = ToolsRegister(logging.getLogger("test"), object(), mcp)

    register.register_all_tools([FakeToolClass])

    assert mcp.registered == ["read_operation"]
    assert mcp.tool.__self__ is mcp
