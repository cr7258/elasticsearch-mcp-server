import pytest

from src.clients.common.alias import AliasClient
from src.clients.common.analyzer import AnalyzerClient
from src.clients.common.cluster import ClusterClient
from src.clients.common.data_stream import DataStreamClient
from src.clients.common.general import GeneralClient

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("client_class", "method_name", "args", "namespace", "expected_call"),
    [
        (ClusterClient, "get_cluster_health", (), "cluster", ("health", (), {})),
        (ClusterClient, "get_cluster_stats", (), "cluster", ("stats", (), {})),
        (AliasClient, "list_aliases", (), "cat", ("aliases", (), {})),
        (
            AliasClient,
            "get_alias",
            ("logs",),
            "indices",
            ("get_alias", (), {"index": "logs"}),
        ),
        (
            AliasClient,
            "put_alias",
            ("logs", "logs-alias", {}),
            "indices",
            ("put_alias", (), {"index": "logs", "name": "logs-alias", "body": {}}),
        ),
        (
            AliasClient,
            "delete_alias",
            ("logs", "logs-alias"),
            "indices",
            ("delete_alias", (), {"index": "logs", "name": "logs-alias"}),
        ),
        (
            DataStreamClient,
            "create_data_stream",
            ("logs-stream",),
            "indices",
            ("create_data_stream", (), {"name": "logs-stream"}),
        ),
        (
            DataStreamClient,
            "get_data_stream",
            ("logs-stream",),
            "indices",
            ("get_data_stream", (), {"name": "logs-stream"}),
        ),
        (
            DataStreamClient,
            "delete_data_stream",
            ("logs-stream",),
            "indices",
            ("delete_data_stream", (), {"name": "logs-stream"}),
        ),
    ],
)
def test_feature_clients_call_expected_sdk_namespace(
    client_class,
    method_name,
    args,
    namespace,
    expected_call,
    attach_client,
    fake_response_processor,
    monkeypatch,
):
    monkeypatch.setattr(client_class, "_process_response", fake_response_processor)
    client = client_class.__new__(client_class)
    fake_client = attach_client(client)

    result = getattr(client, method_name)(*args)

    assert result["method"] == expected_call[0]
    assert getattr(fake_client, namespace).calls == [expected_call]


def test_get_data_stream_without_name_calls_sdk_without_name(
    attach_client, fake_response_processor, monkeypatch
):
    monkeypatch.setattr(DataStreamClient, "_process_response", fake_response_processor)
    client = DataStreamClient.__new__(DataStreamClient)
    fake_client = attach_client(client)

    result = client.get_data_stream()

    assert result["kwargs"] == {}
    assert fake_client.indices.calls == [("get_data_stream", (), {})]


def test_analyze_text_builds_body_and_uses_index_when_provided(
    attach_client, fake_response_processor, monkeypatch
):
    monkeypatch.setattr(AnalyzerClient, "_process_response", fake_response_processor)
    client = AnalyzerClient.__new__(AnalyzerClient)
    fake_client = attach_client(client)

    result = client.analyze_text(
        text="Hello",
        index="logs",
        analyzer="standard",
        tokenizer="keyword",
        filter=["lowercase"],
        char_filter=["html_strip"],
        explain=True,
        attributes=["type"],
    )

    assert result["kwargs"] == {
        "index": "logs",
        "body": {
            "text": "Hello",
            "analyzer": "standard",
            "tokenizer": "keyword",
            "filter": ["lowercase"],
            "char_filter": ["html_strip"],
            "explain": True,
            "attributes": ["type"],
        },
    }
    assert fake_client.indices.calls == [("analyze", (), result["kwargs"])]


def test_analyze_text_without_index_uses_cluster_level_analysis(
    attach_client, fake_response_processor, monkeypatch
):
    monkeypatch.setattr(AnalyzerClient, "_process_response", fake_response_processor)
    client = AnalyzerClient.__new__(AnalyzerClient)
    fake_client = attach_client(client)

    result = client.analyze_text(text="Hello", analyzer="standard")

    assert result["kwargs"] == {"body": {"text": "Hello", "analyzer": "standard"}}
    assert fake_client.indices.calls == [("analyze", (), result["kwargs"])]


def test_general_client_delegates_to_general_rest_client(
    fake_response_processor, monkeypatch
):
    monkeypatch.setattr(GeneralClient, "_process_response", fake_response_processor)
    client = GeneralClient.__new__(GeneralClient)
    calls = []

    class FakeGeneralRestClient:
        def request(self, method, path, params, body):
            calls.append((method, path, params, body))
            return {"ok": True}

    client.general_client = FakeGeneralRestClient()

    result = client.general_api_request(
        "GET", "/_cluster/health", {"pretty": "true"}, None
    )

    assert result == {"ok": True}
    assert calls == [("GET", "/_cluster/health", {"pretty": "true"}, None)]
