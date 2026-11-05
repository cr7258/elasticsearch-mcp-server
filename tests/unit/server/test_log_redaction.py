import asyncio
import http.server
import json
import logging
import threading

import httpx
import pytest
from elasticsearch import Elasticsearch
from fastmcp import FastMCP
from opensearchpy import OpenSearch

from src.log_redaction import (
    LOGGER_NAMES,
    UrlRedactingFilter,
    host_for_log,
    install_url_redaction,
)
from src.server import SearchMCPServer

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _restore_filters():
    saved = {n: list(logging.getLogger(n).filters) for n in LOGGER_NAMES}
    yield
    for n, filters in saved.items():
        logging.getLogger(n).filters[:] = filters


def _record(msg, args=()):
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, args, None)


def test_filter_rewrites_httpx_record():
    record = _record(
        'HTTP Request: %s %s "%s %d %s"',
        ("POST", httpx.URL("http://u:p@h:9200/idx/_doc/1?q=s"), "HTTP/1.1", 200, "OK"),
    )
    assert UrlRedactingFilter().filter(record) is True
    assert record.getMessage() == 'HTTP Request: POST /idx/_doc/{} "HTTP/1.1 200 OK"'
    assert record.args == ()


def test_filter_rewrites_plain_string_arg():
    record = _record("GET %s done", ("https://u:p@h:9200/a/_search?x=1",))
    UrlRedactingFilter().filter(record)
    assert record.getMessage() == "GET /a/_search done"


def test_filter_tolerates_odd_records():
    f = UrlRedactingFilter()
    for rec in (
        _record("no args"),
        _record("%s %d", ("x",)),  # formatting error
        _record("%s", (object(),)),
        _record(12345),
        _record("bad %", ("a", "b")),
    ):
        assert f.filter(rec) is True
        assert isinstance(rec.getMessage(), str)


def test_filter_fallback_does_not_leak():
    record = _record("%d http://u:p@h:9200/x", ("notanint",))
    UrlRedactingFilter().filter(record)
    assert "u:p" not in record.getMessage()
    assert "h:9200" not in record.getMessage()


def test_filter_rewrites_url_in_plain_message(caplog):
    install_url_redaction()
    logger = logging.getLogger("elastic_transport.transport")
    with caplog.at_level(logging.INFO):
        logger.info("POST http://u:p@h:9200/_query?x=1 [status:400]")
    text = caplog.text
    assert "/_query" in text
    for secret in ("u:p", "h:9200", "x=1"):
        assert secret not in text


def test_install_is_idempotent():
    install_url_redaction()
    install_url_redaction()
    for name in LOGGER_NAMES:
        filters = [
            f for f in logging.getLogger(name).filters
            if isinstance(f, UrlRedactingFilter)
        ]
        assert len(filters) == 1, name


def _covered(name):
    # A filter on a parent logger is not applied to records of its children.
    return name in LOGGER_NAMES


@pytest.mark.parametrize("text,expected", [
    ("HTTPS://u:p@h:9200/x?q=1 done", "/x done"),
    ("Node <Urllib3HttpNode(http://h:9200)> has failed for 1 times in a row",
     "Node <Urllib3HttpNode(/)> has failed for 1 times in a row"),
    ("failed (http://h:9200/idx/_search?q=1).", "failed (/idx/_search)."),
    ("http://h:9200/idx/_search?q=foo(bar)secret", "/idx/_search"),
    ("http://h:9200/idx/_doc/abc(def)ghi", "/idx/_doc/{}"),
    ("see (http://h:9200/idx/_search?q=1).", "see (/idx/_search)."),
    ("(http://h:9200/idx/_search?q=f(a)b)", "(/idx/_search)"),
    ("POST http://h:9200/a,b/_search [status:200]", "POST /a,b/_search [status:200]"),
    ("HTTPS://u:p@h:9200/x?q=1", "/x"),
    ("a http://h:9200/x, b", "a /x, b"),
    ("<http://h:9200/x>", "</x>"),
])
def test_filter_url_boundaries(text, expected):
    record = _record(text)
    UrlRedactingFilter().filter(record)
    assert record.getMessage() == expected


def test_filter_httpx_info_line_hides_opaque_ids():
    record = _record(
        'HTTP Request: %s %s "%s %d %s"',
        ("GET", httpx.URL("http://h:9200/_async_search/FmRldE8zREVEUzA2"), "HTTP/1.1", 200, "OK"),
    )
    UrlRedactingFilter().filter(record)
    assert record.getMessage() == 'HTTP Request: GET /_async_search/{} "HTTP/1.1 200 OK"'


@pytest.mark.parametrize("filler,expected", [("(", "/"), (")", "/" + ")" * 50000)])
def test_filter_adversarial_parentheses_is_fast_and_leaks_nothing(filler, expected):
    record = _record("http://" + filler * 50000)
    UrlRedactingFilter().filter(record)
    assert record.getMessage() == expected


@pytest.mark.parametrize("name", ["urllib3.connectionpool", "urllib3.connection"])
def test_urllib3_loggers_are_filtered(name):
    assert name in LOGGER_NAMES
    install_url_redaction()
    try:
        raise OSError("host='h' port=9200")
    except OSError:
        import sys
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name, logging.WARNING, __file__, 1,
        "Retrying (%s) after connection broken by '%s': %s",
        ("Retry(total=1)", "NewConnectionError", "http://u:p@h:9200/idx/_search?q=1"),
        exc_info,
    )
    for f in logging.getLogger(name).filters:
        f.filter(record)
    text = logging.Formatter().format(record)
    assert text == (
        "Retrying (Retry(total=1)) after connection broken by 'NewConnectionError': "
        "/idx/_search [OSError]"
    )


def test_host_for_log():
    assert (
        host_for_log(["https://u:p@es1:9200/x?y=1", "http://es2:9200"])
        == "https://es1:9200, http://es2:9200"
    )
    assert host_for_log("http://u:p@es1:9200/a?b=1") == "http://es1:9200"


@pytest.mark.parametrize("hosts,expected", [
    ("localhost:9200", "localhost:9200"),
    ("[::1]:9200", "[::1]:9200"),
    ("http://[::1]:9200", "http://[::1]:9200"),
    ("http://u:p@[::1]:9200/x?y=1", "http://[::1]:9200"),
    (["http://a:9200", "", "http://b:9200"], "http://a:9200, http://b:9200"),
    (["http://a:9200", ""], "http://a:9200"),
    ("http://h:notaport", "<invalid host>"),
    ("u:p@localhost:9200/x?y=1", "localhost:9200"),
])
def test_host_for_log_forms(hosts, expected):
    assert host_for_log(hosts) == expected


class _Stub(http.server.BaseHTTPRequestHandler):
    def _reply(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        body = json.dumps({"ok": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-elastic-product", "Elasticsearch")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = _reply

    def log_message(self, *args):
        pass


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def test_real_clients_log_no_urls():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Stub)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = logging.getLogger()
    handler = _Capture()
    old_level = root.level
    saved = {
        n: (logging.getLogger(n).level, list(logging.getLogger(n).filters))
        for n in LOGGER_NAMES
    }
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    docid = "DOCID9f3a77"
    try:
        install_url_redaction()
        base = f"http://user:pw@127.0.0.1:{port}"
        with httpx.Client() as c:
            c.get(f"{base}/idx/_doc/{docid}?q=SECRET_QUERY")
        es = Elasticsearch(f"http://127.0.0.1:{port}")
        es.perform_request(
            "GET", f"/idx/_doc/{docid}?q=SECRET_QUERY",
            headers={"accept": "application/json"},
        )
        os_client = OpenSearch(f"{base}")
        os_client.transport.perform_request(
            "GET", f"/idx/_doc/{docid}", params={"q": "SECRET_QUERY"}
        )

        by_logger = {}
        for r in handler.records:
            by_logger.setdefault(r.name.split(".")[0], []).append(r.getMessage())
        for lib in ("httpx", "elastic_transport", "opensearch"):
            assert by_logger.get(lib), f"no record from {lib}"
            assert any("200" in m for m in by_logger[lib]), lib
        for r in handler.records:
            if r.name.split(".")[0] in ("httpx", "elastic_transport", "elasticsearch",
                                        "opensearch", "opensearchpy", "urllib3"):
                assert _covered(r.name), r.name
        for r in handler.records:
            text = r.getMessage()
            for secret in ("user:pw", "127.0.0.1", str(port), docid, "SECRET_QUERY"):
                assert secret not in text, (r.name, text)
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)
        server.shutdown()
        server.server_close()
        for n, (lvl, filters) in saved.items():
            lg = logging.getLogger(n)
            lg.setLevel(lvl)
            lg.filters[:] = filters


def test_readiness_logs_exception_class_only(caplog):
    class Raiser:
        def ping(self):
            raise ConnectionError("http://u:p@h:9200")

    class Mgr:
        def get_client(self, cluster=None):
            return type("W", (), {"client": Raiser()})()

    server = SearchMCPServer.__new__(SearchMCPServer)
    server.engine_type = "elasticsearch"
    server.logger = logging.getLogger("test_readiness_redaction")
    server.mcp = FastMCP("test-server")
    server.search_client = Mgr()
    server._register_health_routes()

    async def go():
        transport = httpx.ASGITransport(app=server.mcp.http_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.get("/readyz")

    with caplog.at_level(logging.WARNING, logger="test_readiness_redaction"):
        asyncio.run(go())
    messages = [r.getMessage() for r in caplog.records]
    assert "Readiness check failed: ConnectionError" in messages
    assert "u:p" not in caplog.text
