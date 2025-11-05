"""
Configuration for high-risk operations management.
"""
import os
from typing import Set, Dict, Any, Callable
from functools import wraps
import logging

# Define default high-risk operations per tool class (all write operations)
HIGH_RISK_OPERATIONS = {
    "IndexTools": {
        "create_index",
        "delete_index",
    },
    "DocumentTools": {
        "index_document",
        "delete_document",
        "delete_by_query",
    },
    "DataStreamTools": {
        "create_data_stream",
        "delete_data_stream",
    },
    "AliasTools": {
        "put_alias",
        "delete_alias",
    },
    "GeneralTools": {
        "general_api_request",
    },
}

class RiskManager:
    """Manages high-risk operation filtering and control."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.high_risk_ops_disabled = self._is_high_risk_disabled()
        
        if self.high_risk_ops_disabled:
            self.disabled_operations = self._get_disabled_operations()
            self.logger.info("High-risk operations are disabled")
            self.logger.info(f"Disabled operations: {self.disabled_operations}")
        else:
            self.disabled_operations = set()
            self.logger.info("High-risk operations are not disabled")
    
    def _is_high_risk_disabled(self) -> bool:
        """Check if high-risk operations should be disabled."""
        return os.environ.get("DISABLE_HIGH_RISK_OPERATIONS", "false").lower() == "true"
    
    def _get_disabled_operations(self) -> Set[str]:
        """Get the set of operations that should be disabled."""
        # Check for custom disabled operations list
        custom_ops = os.environ.get("DISABLE_OPERATIONS", "")
        if custom_ops:
            # User provided custom list
            return set(op.strip() for op in custom_ops.split(",") if op.strip())
        
        # Use default high-risk operations
        all_ops = set()
        for tool_ops in HIGH_RISK_OPERATIONS.values():
            all_ops.update(tool_ops)
        return all_ops
    
    def is_operation_allowed(self, tool_class_name: str, operation_name: str) -> bool:
        """Check if an operation is allowed to be executed."""
        # Only check against the disabled_operations set
        # (which is either custom or default based on environment variables)
        if operation_name in self.disabled_operations:
            self.logger.info(f"Operation '{operation_name}' from {tool_class_name} is disabled")
            return False
        
        return True

# Global risk manager instance
risk_manager = RiskManager()
