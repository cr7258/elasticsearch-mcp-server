"""Optional GCF response encoding for tool results.

When enabled (``RESPONSE_FORMAT=gcf``), a FastMCP middleware re-encodes each tool
result's JSON payload as GCF (Graph Compact Format) in the text content block that
the model reads, while leaving ``structuredContent`` untouched so output-schema
validation and any programmatic client keep working against the original JSON.

GCF is a token-optimized wire format: for the large, uniform record sets Elasticsearch
returns (search hits, aggregation buckets, mappings), it is materially fewer tokens
than JSON without losing information. Encoding is opt-in and fail-safe: any error,
including an integer outside GCF's canonical int64 domain (SPEC 2.3.2, which GCF
rejects rather than silently approximating), leaves the original result unchanged, so
a tool call is never dropped over encoding.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import mcp.types as mt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

from gcf import encode_generic

logger = logging.getLogger(__name__)


def gcf_encoding_enabled() -> bool:
    """True when ``RESPONSE_FORMAT=gcf`` is set in the environment."""
    return os.environ.get("RESPONSE_FORMAT", "").strip().lower() == "gcf"


class GcfResponseMiddleware(Middleware):
    """Re-encode tool-result JSON as GCF in the model-facing content block.

    ``structuredContent`` is preserved verbatim, so the tool's declared output
    schema still validates and non-model consumers still receive JSON. Only the
    text block the model reads is replaced with the GCF wire.
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        result = await call_next(context)

        payload = self._json_payload(result)
        if payload is None:
            return result

        try:
            wire = encode_generic(payload)
        except Exception as exc:  # noqa: BLE001 - liveness over correctness of format
            # An out-of-int64 value (SPEC 2.3.2) or any other encoding issue: keep the
            # original result rather than fail the tool call.
            logger.debug(
                "GCF encoding skipped for tool %r: %s",
                getattr(context.message, "name", "?"),
                exc,
            )
            return result

        return ToolResult(
            content=[TextContent(type="text", text=wire)],
            structured_content=result.structured_content,
        )

    @staticmethod
    def _json_payload(result: ToolResult) -> Any | None:
        """The JSON value to encode, or None if the result is not a single JSON body.

        Prefers ``structured_content`` (the tool's typed value); otherwise re-encodes
        only when the content is exactly one JSON text block.
        """
        if result.structured_content is not None:
            return result.structured_content

        texts = [b.text for b in result.content if isinstance(b, TextContent)]
        if len(texts) != 1:
            return None
        try:
            return json.loads(texts[0])
        except (json.JSONDecodeError, ValueError):
            return None
