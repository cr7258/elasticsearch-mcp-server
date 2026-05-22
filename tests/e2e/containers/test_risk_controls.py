import logging

import pytest

from src.risk_config import HIGH_RISK_OPERATIONS
from src.tools.alias import AliasTools
from src.tools.analyzer import AnalyzerTools
from src.tools.cluster import ClusterTools
from src.tools.data_stream import DataStreamTools
from src.tools.document import DocumentTools
from src.tools.general import GeneralTools
from src.tools.index import IndexTools
from src.tools.register import ToolsRegister
from tests.e2e.containers.conftest import FakeMCP

pytestmark = pytest.mark.e2e

TOOL_CLASSES = [
    IndexTools,
    DocumentTools,
    ClusterTools,
    AliasTools,
    DataStreamTools,
    GeneralTools,
    AnalyzerTools,
]


class E2ERiskManager:
    high_risk_ops_disabled = True

    def __init__(self, disabled_operations):
        self.disabled_operations = set(disabled_operations)

    def is_operation_allowed(self, tool_class_name, operation_name):
        return operation_name not in self.disabled_operations


def _register_tools_with_disabled_operations(search_client, disabled_operations, monkeypatch):
    mcp = FakeMCP()
    monkeypatch.setattr(
        "src.tools.register.risk_manager",
        E2ERiskManager(disabled_operations),
    )
    register = ToolsRegister(logging.getLogger("e2e"), search_client, mcp)
    register.register_all_tools(TOOL_CLASSES)
    return mcp.tools


def test_default_high_risk_operations_are_hidden_from_registered_tools(
    search_engine,
    monkeypatch,
):
    engine_type, search_client = search_engine
    disabled_operations = {
        operation
        for operations in HIGH_RISK_OPERATIONS.values()
        for operation in operations
    }

    tools = _register_tools_with_disabled_operations(
        search_client, disabled_operations, monkeypatch
    )

    assert "list_indices" in tools
    assert "get_cluster_health" in tools
    assert "analyze_text" in tools
    assert disabled_operations.isdisjoint(tools)

    health = tools["get_cluster_health"]()
    assert health["status"] in {"green", "yellow"}


def test_custom_disabled_operations_hide_only_requested_tools(
    search_engine,
    monkeypatch,
):
    engine_type, search_client = search_engine

    tools = _register_tools_with_disabled_operations(
        search_client, {"delete_index", "delete_document"}, monkeypatch
    )

    assert "delete_index" not in tools
    assert "delete_document" not in tools
    assert "create_index" in tools
    assert "index_document" in tools
    assert "list_indices" in tools
