import elastic_transport
import elasticsearch
import httpx
import opensearchpy.exceptions as osx
import pytest

from src.clients.error_report import (
    MAX_CALLER_CHARS,
    MAX_LOG_CHARS,
    UnknownClusterError,
    build_report,
    extract_reasons,
    is_identity_bearing,
    path_template,
    sanitize_log_text,
    top_error_type,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("path,expected", [
    ("/_query", "/_query"),
    ("_query", "/_query"),
    ("/idx/_doc/abc123", "/idx/_doc/{}"),
    ("/_security/user/bob", "/_security/user/{}"),
    ("/_cat/indices/log-*?format=json", "/_cat/indices/{}"),
    ("/idx/_search?q=secret", "/idx/_search"),
    ("http://user:pw@host:9200/idx/_search", "/idx/_search"),
    ("/", "/"),
    ("", "/"),
    ("/idx/_doc/abc/_source", "/idx/_doc/{}/_source"),
    ("/_cat/indices", "/_cat/indices"),
    ("/_cluster/settings", "/_cluster/settings"),
    ("/_security/user/bob/_password", "/_security/user/{}/_password"),
    ("/_search/scroll/ID", "/_search/scroll/{}"),
    ("/_snapshot/repo/snap", "/_snapshot/repo/{}"),
    ("/_nodes/n1/stats", "/_nodes/{}/{}"),
    ("/_async_search/FmRldE8zREVEUzA2", "/_async_search/{}"),
    ("/_tasks/nodeA:123", "/_tasks/{}"),
])
def test_path_template(path, expected):
    assert path_template(path) == expected


def test_path_template_strips_control_chars_and_caps():
    out = path_template("/idx\n\rINJECTED/_doc/" + "x" * 1000)
    assert out == "/idxINJECTED/_doc/{}"


def test_sanitize_log_text_removes_control_chars_and_caps():
    out = sanitize_log_text("a\nb\x00c" + "z" * 500)
    assert out.startswith("abc") and len(out) <= MAX_LOG_CHARS


ESQL_400 = {"error": {"root_cause": [{"type": "verification_exception",
    "reason": "Found 1 problem\nline 1:30: Unknown column [no_such_column]"}],
    "type": "verification_exception",
    "reason": "Found 1 problem\nline 1:30: Unknown column [no_such_column]"}, "status": 400}


def test_extract_reasons_dedupes_root_cause_and_top_level():
    assert extract_reasons(ESQL_400) == [
        "verification_exception: Found 1 problem\nline 1:30: Unknown column [no_such_column]"]


def test_extract_reasons_walks_caused_by_and_failed_shards():
    body = {"error": {"type": "search_phase_execution_exception", "reason": "all shards failed",
        "failed_shards": [{"reason": {"type": "query_shard_exception", "reason": "bad field",
            "caused_by": {"type": "number_format_exception", "reason": "For input string: x"}}}]}}
    assert extract_reasons(body) == [
        "search_phase_execution_exception: all shards failed",
        "query_shard_exception: bad field",
        "number_format_exception: For input string: x"]


def test_extract_reasons_string_error():
    assert extract_reasons({"error": "Incorrect HTTP method"}) == ["error: Incorrect HTTP method"]


def test_extract_reasons_no_error_key_or_non_dict():
    assert extract_reasons({"acknowledged": False}) == []
    assert extract_reasons("<html>bad gateway</html>") == []
    assert extract_reasons(None) == []


def test_extract_reasons_malformed_input_does_not_raise():
    assert extract_reasons([{"error": {"type": "a", "reason": "b"}}]) == []
    assert extract_reasons({"error": None}) == []
    assert extract_reasons({"error": {"type": 1, "reason": 2}}) == []
    assert extract_reasons({"error": {"root_cause": "x", "failed_shards": None}}) == []


def test_top_error_type():
    assert top_error_type(ESQL_400) == "verification_exception"
    assert top_error_type({"error": "x"}) is None
    assert top_error_type(None) is None


@pytest.mark.parametrize("status", [401, 403])
def test_identity_bearing_by_status(status):
    assert is_identity_bearing(status, {})


def test_identity_bearing_nested_security_exception_at_500():
    body = {"error": {"type": "search_phase_execution_exception", "reason": "all shards failed",
        "failed_shards": [{"reason": {"type": "security_exception",
            "reason": "action [x] is unauthorized for user [svc] with roles [r]"}}]}}
    assert is_identity_bearing(500, body)


def test_identity_bearing_authorization_type_case_insensitive():
    body = {"error": {"type": "Foo", "reason": "r",
        "caused_by": {"type": "AuthorizationException", "reason": "r2"}}}
    assert is_identity_bearing(None, body)


def test_not_identity_bearing_plain_400():
    assert not is_identity_bearing(400, ESQL_400)
    assert not is_identity_bearing(None, None)


def _chain(levels, bottom_type):
    node = {"type": bottom_type, "reason": "bottom"}
    for i in range(levels - 1):
        node = {"type": f"wrap_{i}", "reason": "r", "caused_by": node}
    return {"error": node}


def test_identity_bearing_security_type_beyond_depth_cap():
    assert is_identity_bearing(400, _chain(25, "security_exception"))


def test_identity_bearing_fails_closed_when_walk_truncated():
    assert is_identity_bearing(400, _chain(25, "plain_exception"))


def test_depth_cap_boundary():
    assert not is_identity_bearing(400, _chain(21, "plain_exception"))
    assert is_identity_bearing(400, _chain(22, "plain_exception"))


def test_shallow_chain_without_security_not_identity_bearing():
    assert not is_identity_bearing(400, _chain(5, "plain_exception"))


# --- build_report ---

def _httpx_error(status, body, method="POST", url="http://user:pw@host:9200/_query?secretparam=1",
                 content_type="application/json"):
    def handler(request):
        if isinstance(body, (dict, list)):
            return httpx.Response(status, json=body)
        return httpx.Response(status, content=body, headers={"content-type": content_type})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    resp = client.request(method, url)
    with pytest.raises(httpx.HTTPStatusError) as ei:
        resp.raise_for_status()
    return ei.value


def _es_error(status, body):
    meta = elastic_transport.ApiResponseMeta(
        status=status, http_version="1.1", headers=elastic_transport.HttpHeaders(),
        duration=0.1, node=elastic_transport.NodeConfig("http", "host", 9200),
    )
    cls = elasticsearch.BadRequestError if status == 400 else elasticsearch.ApiError
    return cls(message="x", meta=meta, body=body)


def _no_leak(*texts):
    for t in texts:
        for bad in ("host", "9200", "http", "secretparam", "pw"):
            assert bad not in t


def test_httpx_400_esql():
    body = {"error": {"type": "verification_exception",
                      "reason": "Found 1 problem\nUnknown column [no_such_column]"}, "status": 400}
    r = build_report("general_api_request", _httpx_error(400, body))
    assert r.caller_message.startswith("general_api_request failed: 400")
    assert "Unknown column [no_such_column]" in r.caller_message
    assert r.log_line == "general_api_request failed: 400 POST /_query verification_exception"
    _no_leak(r.caller_message, r.log_line)


def test_httpx_403_withholds_reason():
    body = {"error": {"type": "security_exception",
                      "reason": "action denied for user svc_account with role role_x"}}
    r = build_report("general_api_request", _httpx_error(403, body))
    assert r.caller_message == "general_api_request failed: 403 not authorized"
    assert r.log_line == r.caller_message
    for t in (r.caller_message, r.log_line):
        assert "svc_account" not in t and "role_x" not in t


def test_nested_security_at_500_withheld():
    body = {"error": {"type": "exception", "reason": "outer",
                      "caused_by": {"type": "security_exception",
                                    "reason": "user svc_account role_x"}}}
    r = build_report("general_api_request", _httpx_error(500, body))
    assert r.caller_message == "general_api_request failed: 500 not authorized"
    assert r.log_line == r.caller_message


def test_over_deep_chain_withheld():
    node = {"type": "x", "reason": "svc_account"}
    for _ in range(40):
        node = {"type": "x", "reason": "r", "caused_by": node}
    r = build_report("t", _es_error(400, {"error": node}))
    assert r.caller_message == "t failed: 400 not authorized"
    assert r.log_line == r.caller_message


def test_non_json_body():
    r = build_report("general_api_request",
                     _httpx_error(502, "<html>MARKER_HTML</html>", content_type="text/html"))
    assert r.caller_message == "general_api_request failed: 502 Bad Gateway"
    assert "MARKER_HTML" not in r.caller_message + r.log_line


def test_json_content_type_but_invalid_json():
    r = build_report("t", _httpx_error(502, "MARKER_BAD{", content_type="application/json"))
    assert r.caller_message == "t failed: 502 Bad Gateway"
    assert "MARKER_BAD" not in r.caller_message + r.log_line


def test_json_body_without_error_key():
    r = build_report("t", _httpx_error(409, {"acknowledged": False, "note": "MARKER_J"}))
    assert r.caller_message == "t failed: 409 Conflict"
    assert "MARKER_J" not in r.caller_message + r.log_line
    assert r.log_line == "t failed: 409 POST /_query"


def test_error_is_plain_string():
    r = build_report("t", _httpx_error(400, {"error": "bad thing " + "z" * 5000}))
    assert r.caller_message.startswith("t failed: 400\nerror: bad thing")
    assert len(r.caller_message) <= MAX_CALLER_CHARS
    assert r.log_line == "t failed: 400 POST /_query"


def test_es_api_error_dedicated_tool():
    body = {"error": {"type": "search_phase_execution_exception",
                      "reason": "all shards failed",
                      "root_cause": [{"type": "parse_exception",
                                      "reason": "failed to parse date field [x]"}]},
            "status": 400}
    r = build_report("search_documents", _es_error(400, body))
    assert "failed to parse date field" in r.caller_message
    assert r.log_line == "search_documents failed: 400 search_phase_execution_exception"


def test_opensearch_error_same_shape():
    body = {"error": {"type": "search_phase_execution_exception",
                      "reason": "all shards failed",
                      "root_cause": [{"type": "parse_exception",
                                      "reason": "failed to parse date field [x]"}]},
            "status": 400}
    r = build_report("search_documents", osx.RequestError(400, "x", body))
    assert "failed to parse date field" in r.caller_message
    assert r.log_line == "search_documents failed: 400 search_phase_execution_exception"


def test_opensearch_string_status_is_non_http():
    r = build_report("t", osx.TransportError("N/A", "MARKER_T", {}))
    assert r.caller_message == "t failed: internal error"
    assert "MARKER_T" not in r.caller_message + r.log_line


def test_caller_message_capped():
    body = {"error": {"type": "verification_exception", "reason": "a" * 50_000 + "\n"}}
    r = build_report("t", _httpx_error(400, body))
    assert len(r.caller_message) <= MAX_CALLER_CHARS
    assert r.caller_message.endswith("... (truncated)")
    assert len(r.log_line) <= MAX_LOG_CHARS
    assert "\n" not in r.log_line


def test_log_line_ignores_reason_newlines():
    body = {"error": {"type": "t_e", "reason": "x\n" * 20000}}
    r = build_report("t", _httpx_error(400, body))
    assert r.log_line == "t failed: 400 POST /_query t_e"


@pytest.mark.parametrize("exc,phrase,name", [
    (httpx.ReadTimeout("x http://host:9200"), "timed out", "ReadTimeout"),
    (httpx.ConnectError("x http://host:9200"), "connection failed", "ConnectError"),
    (httpx.ProxyError("x http://host:9200"), "connection failed", "ProxyError"),
    (elastic_transport.ConnectionTimeout("x http://host:9200"), "timed out", "ConnectionTimeout"),
    (elastic_transport.ConnectionError("x http://host:9200"), "connection failed", "ConnectionError"),
    (osx.ConnectionTimeout("N/A", "x http://host:9200", Exception("h")), "timed out", "ConnectionTimeout"),
    (osx.ConnectionError("N/A", "x http://host:9200", Exception("h")), "connection failed", "ConnectionError"),
    (ValueError("MARKER_V"), "invalid argument", "ValueError"),
    (TypeError("MARKER_V"), "invalid argument", "TypeError"),
    (RuntimeError("MARKER_RT http://host:9200"), "internal error", "RuntimeError"),
])
def test_non_http_exceptions(exc, phrase, name):
    r = build_report("t", exc)
    assert r.caller_message == f"t failed: {phrase}"
    assert r.log_line == f"t failed: {name}"
    _no_leak(r.caller_message, r.log_line)
    assert "MARKER" not in r.caller_message + r.log_line


def test_path_template_caps_length():
    assert len(path_template("/" + "a" * 1000)) == MAX_LOG_CHARS


@pytest.mark.parametrize("etype", [
    "authentication_exception", "AuthenticationException", "unauthorized_thing",
    "ForbiddenError", "x_forbidden_y",
])
def test_identity_bearing_extra_type_words(etype):
    assert is_identity_bearing(400, {"error": {"type": etype, "reason": "r"}})


def test_identity_bearing_dict_valued_reason_with_security_type():
    body = {"error": {"type": "outer", "reason": {"type": "security_exception", "reason": "r"}}}
    assert is_identity_bearing(400, body)


def test_identity_bearing_security_in_caused_by_at_400():
    body = {"error": {"type": "outer", "reason": "r",
                      "caused_by": {"type": "security_exception", "reason": "r2"}}}
    assert is_identity_bearing(400, body)


def test_extract_reasons_many_distinct_reasons():
    body = {"error": {"type": "t", "reason": "top", "root_cause": [
        {"type": "e", "reason": f"r{i}"} for i in range(20000)]}}
    out = extract_reasons(body)
    assert len(out) == 20001
    assert out[0] == "t: top"
    assert out[1] == "e: r0"
    assert out[-1] == "e: r19999"


def test_extract_reasons_dedupe_keeps_first_order():
    body = {"error": {"type": "a", "reason": "x", "root_cause": [
        {"type": "b", "reason": "y"}, {"type": "a", "reason": "x"}, {"type": "c", "reason": "z"}]}}
    assert extract_reasons(body) == ["a: x", "b: y", "c: z"]


def test_unknown_cluster_message_passes_through():
    exc = UnknownClusterError("Unknown cluster 'x'. Available clusters: a, b")
    r = build_report("search_documents", exc)
    assert r.caller_message == "search_documents failed: Unknown cluster 'x'. Available clusters: a, b"
    assert r.log_line == "search_documents failed: UnknownClusterError"


def test_unknown_cluster_message_sanitized_and_capped():
    r = build_report("t", UnknownClusterError("Unknown cluster 'x\ny'. " + "z" * 5000))
    assert "\n" not in r.caller_message and "\x00" not in r.caller_message
    assert r.caller_message.startswith("t failed: Unknown cluster 'xy'. zzz")
    assert len(r.caller_message) <= MAX_CALLER_CHARS


def test_plain_value_error_still_invalid_argument():
    r = build_report("t", ValueError("Unknown cluster 'x'. Available clusters: a"))
    assert r.caller_message == "t failed: invalid argument"


def test_error_type_with_free_text_is_not_logged():
    body = {"error": {"type": "x http://h:9200/ CANARY", "reason": "bad"}}
    r = build_report("t", _httpx_error(400, body))
    assert r.log_line == "t failed: 400 POST /_query"
    assert "CANARY" not in r.log_line


def test_error_type_dotted_is_logged():
    body = {"error": {"type": "org.foo.Bar_Exception", "reason": "bad"}}
    r = build_report("t", _httpx_error(400, body))
    assert r.log_line == "t failed: 400 POST /_query org.foo.Bar_Exception"


def test_bool_status_is_not_http():
    r = build_report("t", osx.TransportError(True, "MARKER_B", {"error": "x"}))
    assert r.caller_message == "t failed: internal error"
    assert r.log_line == "t failed: TransportError"


def test_opensearch_403_withheld():
    exc = osx.AuthorizationException(403, "x", {"error": {"type": "security_exception",
                                                         "reason": "user svc role_x"}})
    r = build_report("t", exc)
    assert r.caller_message == "t failed: 403 not authorized"
    assert r.log_line == "t failed: 403 not authorized"


def test_es_api_error_with_string_body_gives_status_line_only():
    r = build_report("t", _es_error(500, "MARKER_RAW body text"))
    assert r.caller_message == "t failed: 500 Internal Server Error"
    assert r.log_line == "t failed: 500"
