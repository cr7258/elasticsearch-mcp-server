import pytest

from src.clients import SearchClient
from src.clients.base import GeneralRestClient, SearchClientBase

pytestmark = pytest.mark.unit


def test_process_response_returns_primitives_unchanged():
    client = SearchClientBase.__new__(SearchClientBase)

    assert client._process_response({"ok": True}) == {"ok": True}
    assert client._process_response(["a"]) == ["a"]
    assert client._process_response("text") == "text"
    assert client._process_response(None) is None


def test_process_response_prefers_text_response_body():
    client = SearchClientBase.__new__(SearchClientBase)

    class TextResponse:
        text = "cat response"

    assert client._process_response(TextResponse()) == "cat response"


def test_process_response_uses_object_response_body():
    client = SearchClientBase.__new__(SearchClientBase)

    class ObjectResponse:
        body = {"ok": True}

    assert client._process_response(ObjectResponse()) == {"ok": True}


@pytest.mark.parametrize(
    ("username", "password", "api_key", "expected"),
    [
        (None, None, "api-key", {"api_key": "api-key"}),
        (None, None, None, {}),
        ("elastic", "secret", None, {"basic_auth": ("elastic", "secret")}),
    ],
)
def test_elasticsearch_auth_params(username, password, api_key, expected):
    client = SearchClientBase.__new__(SearchClientBase)
    client.logger = type("Logger", (), {"info": lambda *args: None, "error": lambda *args: None})()

    assert client._get_elasticsearch_auth_params(username, password, api_key) == expected


def test_general_rest_client_sends_json_request_with_api_key(monkeypatch):
    requests = []

    class FakeResponse:
        headers = {"content-type": "application/json"}

        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    class FakeHttpClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def request(self, **kwargs):
            requests.append((self.kwargs, kwargs))
            return FakeResponse()

    monkeypatch.setattr("src.clients.base.httpx.Client", FakeHttpClient)

    client = GeneralRestClient(
        base_url="https://example.com/",
        username="elastic",
        password="secret",
        api_key="api-key",
        verify_certs=True,
        timeout=5,
    )

    result = client.request("get", "/_cluster/health", {"pretty": "true"}, None)

    assert result == {"ok": True}
    assert requests == [
        (
            {"verify": True, "timeout": 5},
            {
                "method": "GET",
                "url": "https://example.com/_cluster/health",
                "params": {"pretty": "true"},
                "json": None,
                "auth": None,
                "headers": {"Authorization": "ApiKey api-key"},
            },
        )
    ]


def test_search_client_init_rejects_unsupported_engine_type():
    with pytest.raises(ValueError, match="Unsupported engine type: solr"):
        SearchClient(
            {
                "hosts": ["http://localhost:9200"],
                "username": None,
                "password": None,
                "api_key": None,
                "verify_certs": False,
                "timeout": None,
            },
            "solr",
        )


def test_search_client_init_constructs_opensearch_client_with_basic_auth(monkeypatch):
    captured = {}

    class FakeOpenSearch:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("src.clients.base.OpenSearch", FakeOpenSearch)

    SearchClient(
        {
            "hosts": ["http://localhost:9200"],
            "username": "admin",
            "password": "secret",
            "api_key": None,
            "verify_certs": False,
            "timeout": 7,
        },
        "opensearch",
    )

    assert captured["hosts"] == ["http://localhost:9200"]
    assert captured["http_auth"] == ("admin", "secret")
    assert captured["verify_certs"] is False
    assert captured["timeout"] == 7


def test_search_client_init_constructs_opensearch_client_without_auth_when_credentials_missing(
    monkeypatch,
):
    captured = {}

    class FakeOpenSearch:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("src.clients.base.OpenSearch", FakeOpenSearch)

    SearchClient(
        {
            "hosts": ["http://localhost:9200"],
            "username": None,
            "password": None,
            "api_key": None,
            "verify_certs": False,
            "timeout": None,
        },
        "opensearch",
    )

    assert captured["http_auth"] is None
    assert "timeout" not in captured


def test_general_rest_client_returns_text_response_and_uses_basic_auth(monkeypatch):
    requests = []

    class FakeResponse:
        headers = {"content-type": "text/plain"}
        text = "ok"

        def raise_for_status(self):
            return None

    class FakeHttpClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def request(self, **kwargs):
            requests.append((self.kwargs, kwargs))
            return FakeResponse()

    monkeypatch.setattr("src.clients.base.httpx.Client", FakeHttpClient)

    client = GeneralRestClient(
        base_url="https://example.com",
        username="elastic",
        password="secret",
        api_key=None,
        verify_certs=False,
    )

    result = client.request("post", "path", None, {"ok": True})

    assert result == "ok"
    assert requests[0][1]["auth"] == ("elastic", "secret")
    assert requests[0][1]["headers"] == {}
