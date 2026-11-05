import logging
import socket

import httpx
import pytest
from elasticsearch import Elasticsearch
from opensearchpy import OpenSearch

from src.log_redaction import LOGGER_NAMES, UrlRedactingFilter, install_url_redaction

pytestmark = pytest.mark.unit


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _make_calls(host, port):
    base = f"http://{host}:{port}"

    def do_httpx():
        with httpx.Client(timeout=2) as c:
            c.get(f"{base}/idx/_doc/DOC1?q=SECRET_QUERY")

    def do_es():
        es = Elasticsearch(base, max_retries=1, request_timeout=2, retry_on_timeout=True)
        es.perform_request("GET", "/idx/_doc/DOC1", headers={"accept": "application/json"})

    def do_os():
        o = OpenSearch(base, max_retries=1, timeout=2)
        o.transport.perform_request("GET", "/idx/_doc/DOC1")

    return {"httpx": do_httpx, "elastic_transport": do_es, "opensearch": do_os}


@pytest.mark.parametrize("target", ["unresolvable", "closed_port"])
def test_connection_failures_leak_no_host_or_port(target):
    port = _closed_port()
    host = "secrethost.invalid" if target == "unresolvable" else "127.0.0.1"
    names = set(LOGGER_NAMES) | {""}
    handler = _Capture()
    saved = {}
    for n in names:
        lg = logging.getLogger(n)
        saved[n] = (lg.level, list(lg.filters), list(lg.handlers))
        lg.addHandler(handler)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    try:
        install_url_redaction()
        for lib, call in _make_calls(host, port).items():
            try:
                call()
            except Exception:
                pass
        fmt = logging.Formatter()
        for r in handler.records:
            if r.name.split(".")[0] in ("httpx", "elastic_transport", "elasticsearch",
                                        "opensearch", "opensearchpy", "urllib3"):
                assert r.name in LOGGER_NAMES, r.name
        seen = set()
        for r in handler.records:
            if id(r) in seen:
                continue
            seen.add(id(r))
            text = fmt.format(r)
            for bad in ("secrethost", "127.0.0.1", str(port), "host=", "port=",
                        "Traceback", "SECRET_QUERY"):
                assert bad not in text, (r.name, text)
        for lib in ("elastic_transport", "opensearch"):
            warns = [
                fmt.format(r) for r in handler.records
                if r.name.split(".")[0] == lib and r.levelno >= logging.WARNING
            ]
            assert warns, f"no warning from {lib}"
            assert any("Error" in w or "Exception" in w for w in warns), warns
    finally:
        for n, (lvl, filters, handlers) in saved.items():
            lg = logging.getLogger(n)
            lg.setLevel(lvl)
            lg.filters[:] = filters
            lg.handlers[:] = handlers


def test_filter_drops_exc_info_keeps_class_name():
    try:
        raise ValueError("host='h' port=9200")
    except ValueError:
        import sys
        exc_info = sys.exc_info()
    rec = logging.LogRecord("t", logging.WARNING, __file__, 1, "failed", (), exc_info)
    assert UrlRedactingFilter().filter(rec) is True
    assert rec.exc_info is None and rec.exc_text is None
    assert logging.Formatter().format(rec) == "failed [ValueError]"


def test_filter_handles_bare_true_exc_info():
    rec = logging.LogRecord("t", logging.WARNING, __file__, 1, "failed", (), True)
    assert UrlRedactingFilter().filter(rec) is True
    assert rec.exc_info is None
