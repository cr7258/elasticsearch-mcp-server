"""
Authentication middleware for MCP server.

Provides Bearer Token authentication for HTTP-based transports (SSE, Streamable HTTP).
"""

import logging
import os
import secrets
from typing import Optional

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_headers
from fastmcp.exceptions import ToolError


logger = logging.getLogger(__name__)


class BearerAuthMiddleware(Middleware):
    """
    Middleware that validates Bearer token authentication.

    This middleware checks the Authorization header for a valid Bearer token.
    If no token is configured (MCP_API_KEY not set), authentication is disabled.

    Environment Variables:
        MCP_API_KEY: The API key that clients must provide to authenticate.
                     If not set, authentication is disabled.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the middleware.

        Args:
            api_key: The API key to validate against. If None, reads from MCP_API_KEY env var.
        """
        self._api_key = api_key

    @property
    def is_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return bool(self._api_key)

    def _validate_token(self, token: str) -> bool:
        """
        Validate the provided token against the configured API key.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            token: The token to validate

        Returns:
            True if valid, False otherwise
        """
        if not self._api_key:
            return True  # No API key configured, allow all
        return secrets.compare_digest(token, self._api_key)

    def _get_bearer_token(self) -> Optional[str]:
        """
        Extract Bearer token from Authorization header.

        Returns:
            The token if found and properly formatted, None otherwise
        """
        try:
            headers = get_http_headers()
            if not headers:
                return None

            auth_header = headers.get("authorization") or headers.get("Authorization")
            if not auth_header:
                return None

            # Check for Bearer scheme (case-insensitive per RFC 6750)
            scheme, _, token = auth_header.partition(" ")
            if scheme.lower() != "bearer" or not token:
                return None

            return token.strip()
        except Exception as e:
            logger.debug(f"Error getting headers: {e}")
            return None

    def _check_auth(self) -> None:
        """
        Check if the request is authenticated.

        Raises:
            ToolError: If authentication fails
        """
        token = self._get_bearer_token()

        if not token:
            logger.warning("Authentication failed: No Bearer token provided")
            raise ToolError(
                "Unauthorized: Missing or invalid Authorization header. "
                "Please provide a valid Bearer token in the Authorization header."
            )

        if not self._validate_token(token):
            logger.warning("Authentication failed: Invalid Bearer token")
            raise ToolError(
                "Unauthorized: Invalid API key. "
                "Please check your MCP_API_KEY configuration."
            )

        logger.debug("Authentication successful")

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Authenticate before calling a tool."""
        self._check_auth()
        return await call_next(context)

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        """Authenticate before listing tools."""
        self._check_auth()
        return await call_next(context)

    async def on_list_resources(self, context: MiddlewareContext, call_next):
        """Authenticate before listing resources."""
        self._check_auth()
        return await call_next(context)

    async def on_read_resource(self, context: MiddlewareContext, call_next):
        """Authenticate before reading a resource."""
        self._check_auth()
        return await call_next(context)

    async def on_list_prompts(self, context: MiddlewareContext, call_next):
        """Authenticate before listing prompts."""
        self._check_auth()
        return await call_next(context)

    async def on_get_prompt(self, context: MiddlewareContext, call_next):
        """Authenticate before getting a prompt."""
        self._check_auth()
        return await call_next(context)
