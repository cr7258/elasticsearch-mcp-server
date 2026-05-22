import uuid

import pytest

from tests.e2e.k8s.conftest import (
    call_mcp_tool,
    port_forward,
    wait_for_http,
)

pytestmark = [pytest.mark.e2e, pytest.mark.k8s]


_PORT_OFFSETS = {
    "elasticsearch": 18010,
    "opensearch": 18110,
}


def _ports(engine_type: str) -> int:
    return _PORT_OFFSETS[engine_type]


def _mcp_url(base_url: str) -> str:
    return f"{base_url}/mcp"


def test_index_tools_round_trip_through_mcp(mcp_server_in_kind):
    engine_type, release = mcp_server_in_kind
    with port_forward(release, _ports(engine_type) + 0) as base_url:
        wait_for_http(f"{base_url}/healthz")
        mcp_url = _mcp_url(base_url)
        index = f"mcp-k8s-index-{engine_type}-{uuid.uuid4().hex[:8]}"

        try:
            create = call_mcp_tool(mcp_url, "create_index", {"index": index})
            assert create["acknowledged"] is True

            indices = call_mcp_tool(mcp_url, "list_indices")
            assert index in indices

            info = call_mcp_tool(mcp_url, "get_index", {"index": index})
            assert index in info
        finally:
            call_mcp_tool(mcp_url, "delete_index", {"index": index})


def test_document_tools_round_trip_through_mcp(mcp_server_in_kind):
    engine_type, release = mcp_server_in_kind
    with port_forward(release, _ports(engine_type) + 1) as base_url:
        wait_for_http(f"{base_url}/healthz")
        mcp_url = _mcp_url(base_url)
        index = f"mcp-k8s-doc-{engine_type}-{uuid.uuid4().hex[:8]}"

        try:
            call_mcp_tool(mcp_url, "create_index", {"index": index})

            indexed = call_mcp_tool(
                mcp_url,
                "index_document",
                {"index": index, "id": "doc-1", "document": {"hello": "mcp"}},
            )
            assert indexed["result"] in {"created", "updated"}

            fetched = call_mcp_tool(
                mcp_url, "get_document", {"index": index, "id": "doc-1"}
            )
            assert fetched["_source"] == {"hello": "mcp"}

            deleted = call_mcp_tool(
                mcp_url, "delete_document", {"index": index, "id": "doc-1"}
            )
            assert deleted["result"] == "deleted"
        finally:
            call_mcp_tool(mcp_url, "delete_index", {"index": index})


def test_search_and_delete_by_query_through_mcp(mcp_server_in_kind):
    engine_type, release = mcp_server_in_kind
    with port_forward(release, _ports(engine_type) + 2) as base_url:
        wait_for_http(f"{base_url}/healthz")
        mcp_url = _mcp_url(base_url)
        index = f"mcp-k8s-search-{engine_type}-{uuid.uuid4().hex[:8]}"

        try:
            call_mcp_tool(mcp_url, "create_index", {"index": index})
            for doc_id, category in [("a", "cleanup"), ("b", "keep")]:
                call_mcp_tool(
                    mcp_url,
                    "index_document",
                    {
                        "index": index,
                        "id": doc_id,
                        "document": {"category": category},
                    },
                )
            call_mcp_tool(
                mcp_url,
                "general_api_request",
                {"method": "POST", "path": f"/{index}/_refresh"},
            )

            search = call_mcp_tool(
                mcp_url,
                "search_documents",
                {
                    "index": index,
                    "body": {"query": {"term": {"category.keyword": "cleanup"}}},
                },
            )
            assert search["hits"]["total"]["value"] == 1

            deleted = call_mcp_tool(
                mcp_url,
                "delete_by_query",
                {
                    "index": index,
                    "body": {"query": {"term": {"category.keyword": "cleanup"}}},
                },
            )
            assert deleted["deleted"] == 1
        finally:
            call_mcp_tool(mcp_url, "delete_index", {"index": index})


def test_alias_tools_round_trip_through_mcp(mcp_server_in_kind):
    engine_type, release = mcp_server_in_kind
    with port_forward(release, _ports(engine_type) + 3) as base_url:
        wait_for_http(f"{base_url}/healthz")
        mcp_url = _mcp_url(base_url)
        index = f"mcp-k8s-alias-{engine_type}-{uuid.uuid4().hex[:8]}"
        alias = f"{index}-alias"

        try:
            call_mcp_tool(mcp_url, "create_index", {"index": index})

            put = call_mcp_tool(
                mcp_url, "put_alias", {"index": index, "name": alias, "body": {}}
            )
            assert put["acknowledged"] is True

            info = call_mcp_tool(mcp_url, "get_alias", {"index": index})
            assert alias in info[index]["aliases"]

            aliases = call_mcp_tool(mcp_url, "list_aliases")
            assert alias in aliases

            deleted = call_mcp_tool(
                mcp_url, "delete_alias", {"index": index, "name": alias}
            )
            assert deleted["acknowledged"] is True
        finally:
            call_mcp_tool(mcp_url, "delete_index", {"index": index})


def test_cluster_analyzer_and_general_tools_through_mcp(mcp_server_in_kind):
    engine_type, release = mcp_server_in_kind
    with port_forward(release, _ports(engine_type) + 4) as base_url:
        wait_for_http(f"{base_url}/healthz")
        mcp_url = _mcp_url(base_url)

        health = call_mcp_tool(mcp_url, "get_cluster_health")
        assert health["status"] in {"green", "yellow"}

        general_health = call_mcp_tool(
            mcp_url,
            "general_api_request",
            {"method": "GET", "path": "/_cluster/health"},
        )
        assert general_health["status"] in {"green", "yellow"}

        analysis = call_mcp_tool(
            mcp_url,
            "analyze_text",
            {"text": "Hello MCP", "analyzer": "standard"},
        )
        tokens = [token["token"] for token in analysis["tokens"]]
        assert tokens == ["hello", "mcp"]


@pytest.fixture
def _data_stream_test_marker(mcp_server_in_kind):
    engine_type, _ = mcp_server_in_kind
    if engine_type != "elasticsearch":
        pytest.skip("Data streams in this test require an Elasticsearch index template")
    return mcp_server_in_kind


def test_data_stream_tools_round_trip_through_mcp(_data_stream_test_marker):
    engine_type, release = _data_stream_test_marker
    with port_forward(release, _ports(engine_type) + 5) as base_url:
        wait_for_http(f"{base_url}/healthz")
        mcp_url = _mcp_url(base_url)
        suffix = uuid.uuid4().hex[:8]
        template = f"mcp-k8s-template-{suffix}"
        stream = f"mcp-k8s-stream-{suffix}"
        template_created = False
        stream_created = False

        try:
            call_mcp_tool(
                mcp_url,
                "general_api_request",
                {
                    "method": "PUT",
                    "path": f"/_index_template/{template}",
                    "body": {
                        "index_patterns": [f"{stream}*"],
                        "data_stream": {},
                        "template": {
                            "mappings": {
                                "properties": {
                                    "@timestamp": {"type": "date"},
                                    "message": {"type": "text"},
                                }
                            }
                        },
                    },
                },
            )
            template_created = True

            create = call_mcp_tool(mcp_url, "create_data_stream", {"name": stream})
            assert create["acknowledged"] is True
            stream_created = True

            info = call_mcp_tool(mcp_url, "get_data_stream", {"name": stream})
            names = [item["name"] for item in info.get("data_streams", [])]
            assert stream in names
        finally:
            if stream_created:
                call_mcp_tool(mcp_url, "delete_data_stream", {"name": stream})
            if template_created:
                call_mcp_tool(
                    mcp_url,
                    "general_api_request",
                    {
                        "method": "DELETE",
                        "path": f"/_index_template/{template}",
                    },
                )
