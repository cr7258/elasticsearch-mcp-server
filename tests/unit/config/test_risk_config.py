import pytest

from src.risk_config import HIGH_RISK_OPERATIONS, RiskManager

pytestmark = pytest.mark.unit


def test_risk_manager_disabled_flag_defaults_to_false(monkeypatch):
    monkeypatch.delenv("DISABLE_HIGH_RISK_OPERATIONS", raising=False)

    manager = RiskManager()

    assert manager.high_risk_ops_disabled is False
    assert manager.disabled_operations == set()


def test_risk_manager_uses_default_write_operations_when_disabled(monkeypatch):
    monkeypatch.setenv("DISABLE_HIGH_RISK_OPERATIONS", "true")
    monkeypatch.delenv("DISABLE_OPERATIONS", raising=False)

    manager = RiskManager()

    expected = set()
    for operations in HIGH_RISK_OPERATIONS.values():
        expected.update(operations)

    assert manager.high_risk_ops_disabled is True
    assert manager.disabled_operations == expected
    assert manager.is_operation_allowed("IndexTools", "list_indices") is True
    assert manager.is_operation_allowed("IndexTools", "delete_index") is False


def test_risk_manager_uses_custom_disabled_operations(monkeypatch):
    monkeypatch.setenv("DISABLE_HIGH_RISK_OPERATIONS", "true")
    monkeypatch.setenv("DISABLE_OPERATIONS", "delete_index, delete_document")

    manager = RiskManager()

    assert manager.disabled_operations == {"delete_index", "delete_document"}
    assert manager.is_operation_allowed("IndexTools", "create_index") is True
    assert manager.is_operation_allowed("IndexTools", "delete_index") is False
