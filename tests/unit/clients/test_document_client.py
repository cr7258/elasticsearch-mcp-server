import pytest

from src.clients.common.document import DocumentClient

pytestmark = pytest.mark.unit


@pytest.fixture
def document_client(fake_response_processor, monkeypatch):
    monkeypatch.setattr(DocumentClient, "_process_response", fake_response_processor)
    return DocumentClient.__new__(DocumentClient)


def test_search_documents_calls_search(document_client, attach_client):
    fake_client = attach_client(document_client)
    body = {"query": {"match_all": {}}}

    result = document_client.search_documents("logs", body)

    assert result["kwargs"] == {"index": "logs", "body": body}
    assert fake_client.calls == [("search", (), {"index": "logs", "body": body})]


def test_index_document_uses_document_parameter_for_elasticsearch(
    document_client, attach_client
):
    fake_client = attach_client(document_client, engine_type="elasticsearch")
    document = {"message": "hello"}

    result = document_client.index_document("logs", document=document, id="1")

    assert result["kwargs"] == {"index": "logs", "document": document, "id": "1"}
    assert fake_client.calls == [
        ("index", (), {"index": "logs", "document": document, "id": "1"})
    ]


def test_index_document_uses_body_parameter_for_opensearch(document_client, attach_client):
    fake_client = attach_client(document_client, engine_type="opensearch")
    document = {"message": "hello"}

    result = document_client.index_document("logs", document=document)

    assert result["kwargs"] == {"index": "logs", "body": document}
    assert fake_client.calls == [("index", (), {"index": "logs", "body": document})]


def test_get_document_calls_get(document_client, attach_client):
    fake_client = attach_client(document_client)

    result = document_client.get_document("logs", "1")

    assert result["kwargs"] == {"index": "logs", "id": "1"}
    assert fake_client.calls == [("get", (), {"index": "logs", "id": "1"})]


def test_delete_document_calls_delete(document_client, attach_client):
    fake_client = attach_client(document_client)

    result = document_client.delete_document("logs", "1")

    assert result["kwargs"] == {"index": "logs", "id": "1"}
    assert fake_client.calls == [("delete", (), {"index": "logs", "id": "1"})]


def test_delete_by_query_calls_delete_by_query(document_client, attach_client):
    fake_client = attach_client(document_client)
    body = {"query": {"match_all": {}}}

    result = document_client.delete_by_query("logs", body)

    assert result["kwargs"] == {"index": "logs", "body": body}
    assert fake_client.calls == [("delete_by_query", (), {"index": "logs", "body": body})]
