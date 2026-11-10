"""Helpers for building log-safe error reports."""

import http
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit

import elastic_transport
import elasticsearch
import httpx
import opensearchpy.exceptions as osx

MAX_CALLER_CHARS = 2000
MAX_LOG_CHARS = 300


class UnknownClusterError(ValueError):
    """Raised when a tool names a cluster that is not configured.

    Its message holds only operator-chosen cluster labels and the caller's own
    input, so it is safe to return to the caller.
    """


def sanitize_log_text(text: str, limit: int = MAX_LOG_CHARS) -> str:
    """Drop control/format characters and cap the length."""
    cleaned = "".join(c for c in text if not unicodedata.category(c).startswith("C"))
    return cleaned[:limit]


_ENDPOINT_WORD = re.compile(r"[a-z][a-z_]*")
_SAFE_TYPE = re.compile(r"[A-Za-z0-9_.]+")


def path_template(path: str) -> str:
    """Reduce a request path to a log-safe template.

    Scheme, host, userinfo, query and fragment are removed. Segment 0 is kept,
    every later segment starting with ``_`` is kept, and segment 1 is kept only
    when segment 0 starts with ``_`` (a cluster-level endpoint) and it looks
    like an endpoint word (``^[a-z][a-z_]*$``), so opaque IDs such as async
    search IDs or node names are not kept. All other segments become ``{}``.
    """
    if "://" in path:
        path = urlsplit(path).path
    path = path.split("?", 1)[0].split("#", 1)[0]
    segments = path.lstrip("/").split("/")
    out = []
    for i, seg in enumerate(segments):
        keep = (
            i == 0
            or seg.startswith("_")
            or (
                i == 1
                and segments[0].startswith("_")
                and _ENDPOINT_WORD.fullmatch(seg) is not None
            )
        )
        out.append(seg if keep else "{}")
    return sanitize_log_text("/" + "/".join(out))


_MAX_DEPTH = 20
_CHILD_KEYS = ("root_cause", "caused_by", "failed_shards", "reason")


def _walk(node: object, out: list, depth: int = 0) -> bool:
    """Collect ``(type, reason)`` entries from an Elasticsearch error object.

    ``type`` and ``reason`` are each ``None`` unless they are strings.
    Returns True if the depth cap truncated the walk (callers must fail closed).
    """
    if depth > _MAX_DEPTH:
        return isinstance(node, (dict, list))
    truncated = False
    if isinstance(node, list):
        for item in node:
            truncated |= _walk(item, out, depth + 1)
        return truncated
    if not isinstance(node, dict):
        return False
    etype, reason = node.get("type"), node.get("reason")
    etype = etype if isinstance(etype, str) else None
    reason = reason if isinstance(reason, str) else None
    if etype is not None:
        out.append((etype, reason))
    for key in _CHILD_KEYS:
        child = node.get(key)
        if isinstance(child, (dict, list)):
            truncated |= _walk(child, out, depth + 1)
    return truncated


def _entries(body: object) -> tuple[list, bool]:
    """Return ``(entries, truncated)`` for the structured ``error`` object."""
    out: list = []
    truncated = False
    if isinstance(body, dict):
        truncated = _walk(body.get("error"), out)
    return out, truncated


def extract_reasons(body: object) -> list[str]:
    """Return ``"<type>: <reason>"`` strings from the structured ``error`` object.

    Only the ``error`` value is read; raw body text is never returned. Order is
    first appearance and duplicates are dropped. Malformed input yields ``[]``.
    """
    if not isinstance(body, dict):
        return []
    error = body.get("error")
    if isinstance(error, str):
        return [f"error: {error}"]
    reasons: list[str] = []
    seen: set[str] = set()
    for etype, reason in _entries(body)[0]:
        if reason is None:
            continue
        item = f"{etype}: {reason}"
        if item not in seen:
            seen.add(item)
            reasons.append(item)
    return reasons


def top_error_type(body: object) -> str | None:
    """Return the top-level ``error.type`` if it is a string, else ``None``."""
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        etype = body["error"].get("type")
        if isinstance(etype, str):
            return etype
    return None


_IDENTITY_WORDS = (
    "security", "authorization", "authenticat", "unauthori", "forbidden",
)


def is_identity_bearing(status: int | None, body: object) -> bool:
    """True when the error may reveal user or role details.

    That is status 401/403, or any type in the cause chain containing
    ``security``, ``authorization``, ``authenticat``, ``unauthori`` or
    ``forbidden`` (case-insensitive), at any status.
    Fails closed: a chain deeper than the walk cap counts as identity-bearing.
    """
    if status in (401, 403):
        return True
    entries, truncated = _entries(body)
    if truncated:
        return True
    return any(
        any(word in t.lower() for word in _IDENTITY_WORDS)
        for t, _ in entries
    )


_TRUNCATED = "... (truncated)"


@dataclass(frozen=True)
class ErrorReport:
    caller_message: str
    log_line: str


def _cap_caller(text: str) -> str:
    if len(text) <= MAX_CALLER_CHARS:
        return text
    return text[: MAX_CALLER_CHARS - len(_TRUNCATED)] + _TRUNCATED


def _http_parts(exc: BaseException):
    """Return ``(status, method, path, body)`` for HTTP errors, else ``None``."""
    if isinstance(exc, httpx.HTTPStatusError):
        body = None
        ctype = exc.response.headers.get("content-type", "")
        if ctype.lower().startswith("application/json"):
            try:
                body = exc.response.json()
            except ValueError:
                body = None
        return (
            exc.response.status_code,
            exc.request.method,
            exc.request.url.path,
            body,
        )
    if isinstance(exc, elasticsearch.ApiError):
        return exc.meta.status, None, None, exc.body
    if (
        isinstance(exc, osx.TransportError)
        and isinstance(exc.status_code, int)
        and not isinstance(exc.status_code, bool)
    ):
        return exc.status_code, None, None, exc.info
    return None


def _non_http_phrase(exc: BaseException) -> str:
    # Connection/timeout classes must be checked before OpenSearch's generic
    # TransportError (their base) and before httpx.TransportError.
    if isinstance(
        exc,
        (httpx.TimeoutException, elastic_transport.ConnectionTimeout, osx.ConnectionTimeout),
    ):
        return "timed out"
    if isinstance(
        exc,
        (httpx.TransportError, elastic_transport.ConnectionError, osx.ConnectionError),
    ):
        return "connection failed"
    if isinstance(exc, (ValueError, TypeError)):
        return "invalid argument"
    return "internal error"


def build_report(tool_name: str, exc: BaseException) -> ErrorReport:
    """Build a caller-safe message and a log line for any tool exception."""
    if isinstance(exc, UnknownClusterError):
        return ErrorReport(
            caller_message=_cap_caller(
                f"{tool_name} failed: {sanitize_log_text(str(exc), MAX_CALLER_CHARS)}"
            ),
            log_line=sanitize_log_text(f"{tool_name} failed: {type(exc).__name__}"),
        )
    parts = _http_parts(exc)
    if parts is None:
        phrase = _non_http_phrase(exc)
        return ErrorReport(
            caller_message=_cap_caller(f"{tool_name} failed: {phrase}"),
            log_line=sanitize_log_text(f"{tool_name} failed: {type(exc).__name__}"),
        )
    status, method, path, body = parts
    if is_identity_bearing(status, body):
        text = f"{tool_name} failed: {status} not authorized"
        return ErrorReport(_cap_caller(text), sanitize_log_text(text))
    reasons = extract_reasons(body)
    if reasons:
        caller = f"{tool_name} failed: {status}\n" + "\n".join(reasons)
    else:
        try:
            phrase = http.HTTPStatus(status).phrase
        except ValueError:
            phrase = ""
        caller = f"{tool_name} failed: {status} {phrase}".rstrip()
    log = f"{tool_name} failed: {status}"
    if method and path is not None:
        log += f" {method.upper()} {path_template(path)}"
    etype = top_error_type(body)
    if etype and _SAFE_TYPE.fullmatch(etype):
        log += f" {etype}"
    return ErrorReport(_cap_caller(caller), sanitize_log_text(log))
