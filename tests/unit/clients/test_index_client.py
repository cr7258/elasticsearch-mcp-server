import pytest

from src.clients.common.index import IndexClient

pytestmark = pytest.mark.unit


@pytest.fixture
def index_client(fake_response_processor, monkeypatch):
    monkeypatch.setattr(IndexClient, "_process_response", fake_response_processor)
    return IndexClient.__new__(IndexClient)


def test_list_indices_calls_cat_indices(index_client, attach_client):
    fake_client = attach_client(index_client)

    result = index_client.list_indices()

    assert result["method"] == "indices"
    assert fake_client.cat.calls == [("indices", (), {})]


def test_get_index_calls_indices_get(index_client, attach_client):
    fake_client = attach_client(index_client)

    result = index_client.get_index("logs")

    assert result["kwargs"] == {"index": "logs"}
    assert fake_client.indices.calls == [("get", (), {"index": "logs"})]


def test_create_index_passes_optional_body(index_client, attach_client):
    fake_client = attach_client(index_client)
    body = {"settings": {"number_of_shards": 1}}

    result = index_client.create_index("logs", body=body)

    assert result["kwargs"] == {"index": "logs", "body": body}
    assert fake_client.indices.calls == [("create", (), {"index": "logs", "body": body})]


def test_delete_index_calls_indices_delete(index_client, attach_client):
    fake_client = attach_client(index_client)

    result = index_client.delete_index("logs")

    assert result["kwargs"] == {"index": "logs"}
    assert fake_client.indices.calls == [("delete", (), {"index": "logs"})]
