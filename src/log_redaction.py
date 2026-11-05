"""Keep URLs, credentials and query strings out of library and startup logs."""

import logging
import re
import sys
from urllib.parse import urlsplit

from src.clients.error_report import path_template

# Loggers that actually emit URL-bearing records. A filter on a parent logger
# is not applied to records from child loggers, so each emitter is listed.
LOGGER_NAMES = (
    "httpx",
    "elastic_transport",
    "elastic_transport.transport",
    "elastic_transport.node",
    "elastic_transport.node_pool",
    "elasticsearch",
    "opensearch",
    "opensearchpy.trace",
    "urllib3.connectionpool",
    "urllib3.connection",
)

# Stops at whitespace, quotes and angle brackets. Parentheses belong to the
# body (they occur in paths and queries); trailing punctuation and unbalanced
# closing parentheses are trimmed after matching.
_URL_RE = re.compile(r"\bhttps?://[^\s\"'<>]+", re.IGNORECASE)
_FALLBACK = "[log message withheld: could not be redacted safely]"


def _redact_url(match: re.Match) -> str:
    url = match.group(0)
    opens, closes = url.count("("), url.count(")")
    end = len(url)
    while end > 0:
        ch = url[end - 1]
        if ch in ".,":
            end -= 1
        elif ch == ")" and closes > opens:
            end -= 1
            closes -= 1
        else:
            break
    return path_template(url[:end]) + url[end:]


def _redact_text(text: str) -> str:
    return _URL_RE.sub(_redact_url, text)


def _exc_class_name(record: logging.LogRecord) -> str:
    info = record.exc_info
    if info is True:
        info = sys.exc_info()
    if isinstance(info, BaseException):
        return type(info).__name__
    if isinstance(info, tuple) and len(info) == 3 and info[0] is not None:
        exc = info[1]
        return type(exc).__name__ if exc is not None else getattr(info[0], "__name__", "")
    return ""


class UrlRedactingFilter(logging.Filter):
    """Replace absolute URLs in a record with their path template."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = _redact_text(record.getMessage())
            exc_name = _exc_class_name(record)
            if exc_name:
                rendered = f"{rendered} [{exc_name}]"
            record.msg = rendered
            record.args = ()
            # Tracebacks carry hosts and ports; keep only the class name.
            record.exc_info = None
            record.exc_text = None
        except Exception:
            record.msg = _FALLBACK
            record.args = ()
            record.exc_info = None
            record.exc_text = None
        return True


def install_url_redaction() -> None:
    """Attach the redacting filter once to every URL-emitting library logger."""
    for name in LOGGER_NAMES:
        logger = logging.getLogger(name)
        if not any(isinstance(f, UrlRedactingFilter) for f in logger.filters):
            logger.addFilter(UrlRedactingFilter())


def host_for_log(hosts) -> str:
    """Return ``[scheme://]host[:port]`` per host, without userinfo, path or query."""
    items = [hosts] if isinstance(hosts, str) else list(hosts or [])
    out = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        try:
            has_scheme = "://" in text
            parts = urlsplit(text if has_scheme else f"//{text}")
            host = parts.hostname or ""
            if ":" in host:
                host = f"[{host}]"
            port = f":{parts.port}" if parts.port else ""
            scheme = f"{parts.scheme}://" if has_scheme and parts.scheme else ""
            out.append(f"{scheme}{host}{port}")
        except Exception:
            out.append("<invalid host>")
    return ", ".join(out)
