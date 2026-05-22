import json

import pytest

pytestmark = pytest.mark.unit


class FakeSearchClient:
    instances = []

    def __init__(self, config, engine_type):
        self.config = config
        self.engine_type = engine_type
        self.client = self
        FakeSearchClient.instances.append(self)

    def ping(self):
        return True


@pytest.fixture(autouse=True)
def clear_search_client_instances(monkeypatch):
    FakeSearchClient.instances = []
    monkeypatch.delenv("ELASTICSEARCH_CLUSTERS", raising=False)
    monkeypatch.delenv("ELASTICSEARCH_HOSTS", raising=False)
    monkeypatch.delenv("ELASTICSEARCH_API_KEY", raising=False)
    monkeypatch.delenv("ELASTICSEARCH_USERNAME", raising=False)
    monkeypatch.delenv("ELASTICSEARCH_PASSWORD", raising=False)
    monkeypatch.delenv("DEFAULT_CLUSTER", raising=False)
    monkeypatch.delenv("VERIFY_CERTS", raising=False)
    monkeypatch.delenv("REQUEST_TIMEOUT", raising=False)


def test_creates_clients_from_multi_cluster_config_and_uses_default_cluster(
    monkeypatch,
):
    from src.clients import create_search_client_manager

    monkeypatch.setenv(
        "ELASTICSEARCH_CLUSTERS",
        json.dumps(
            {
                "prod": {
                    "hosts": ["https://prod.example.com:9200"],
                    "api_key": "prod-key",
                    "verify_certs": True,
                    "timeout": 5,
                },
                "staging": {
                    "hosts": ["https://staging.example.com:9200"],
                    "username": "elastic",
                    "password": "secret",
                },
            }
        ),
    )
    monkeypatch.setenv("DEFAULT_CLUSTER", "prod")
    monkeypatch.setattr("src.clients.load_dotenv", lambda: None)
    monkeypatch.setattr("src.clients.SearchClient", FakeSearchClient)

    manager = create_search_client_manager("elasticsearch")

    assert manager.list_clusters() == ["prod", "staging"]
    assert manager.get_client() is FakeSearchClient.instances[0]
    assert manager.get_client("staging") is FakeSearchClient.instances[1]
    assert FakeSearchClient.instances[0].config == {
        "hosts": ["https://prod.example.com:9200"],
        "username": None,
        "password": None,
        "api_key": "prod-key",
        "verify_certs": True,
        "timeout": 5,
    }


def test_uses_first_configured_cluster_as_default_when_not_specified(monkeypatch):
    from src.clients import create_search_client_manager

    monkeypatch.setenv(
        "ELASTICSEARCH_CLUSTERS",
        json.dumps(
            {
                "first": {"hosts": ["https://first.example.com:9200"]},
                "second": {"hosts": ["https://second.example.com:9200"]},
            }
        ),
    )
    monkeypatch.setattr("src.clients.load_dotenv", lambda: None)
    monkeypatch.setattr("src.clients.SearchClient", FakeSearchClient)

    manager = create_search_client_manager("elasticsearch")

    assert manager.default_cluster == "first"
    assert manager.get_client() is FakeSearchClient.instances[0]


def test_rejects_default_cluster_that_is_not_configured(monkeypatch):
    from src.clients import create_search_client_manager

    monkeypatch.setenv(
        "ELASTICSEARCH_CLUSTERS",
        json.dumps({"prod": {"hosts": ["https://prod.example.com:9200"]}}),
    )
    monkeypatch.setenv("DEFAULT_CLUSTER", "missing")
    monkeypatch.setattr("src.clients.load_dotenv", lambda: None)
    monkeypatch.setattr("src.clients.SearchClient", FakeSearchClient)

    with pytest.raises(ValueError, match="Default cluster 'missing' is not configured"):
        create_search_client_manager("elasticsearch")


def test_normalizes_comma_separated_hosts_in_cluster_config(monkeypatch):
    from src.clients import create_search_client_manager

    monkeypatch.setenv(
        "ELASTICSEARCH_CLUSTERS",
        json.dumps(
            {
                "prod": {
                    "hosts": "https://one.example.com:9200, https://two.example.com:9200"
                }
            }
        ),
    )
    monkeypatch.setattr("src.clients.load_dotenv", lambda: None)
    monkeypatch.setattr("src.clients.SearchClient", FakeSearchClient)

    create_search_client_manager("elasticsearch")

    assert FakeSearchClient.instances[0].config["hosts"] == [
        "https://one.example.com:9200",
        "https://two.example.com:9200",
    ]


def test_rejects_non_object_cluster_config(monkeypatch):
    from src.clients import create_search_client_manager

    monkeypatch.setenv("ELASTICSEARCH_CLUSTERS", json.dumps(["prod"]))
    monkeypatch.setattr("src.clients.load_dotenv", lambda: None)

    with pytest.raises(ValueError, match="ELASTICSEARCH_CLUSTERS must be a JSON object"):
        create_search_client_manager("elasticsearch")


def test_falls_back_to_single_cluster_environment_config(monkeypatch):
    from src.clients import create_search_client_manager

    monkeypatch.setenv("ELASTICSEARCH_HOSTS", "https://one.example.com:9200")
    monkeypatch.setenv("ELASTICSEARCH_API_KEY", "one-key")
    monkeypatch.setenv("VERIFY_CERTS", "true")
    monkeypatch.setenv("REQUEST_TIMEOUT", "3.5")
    monkeypatch.setattr("src.clients.load_dotenv", lambda: None)
    monkeypatch.setattr("src.clients.SearchClient", FakeSearchClient)

    manager = create_search_client_manager("elasticsearch")

    assert manager.list_clusters() == ["default"]
    assert manager.get_client() is FakeSearchClient.instances[0]
    assert FakeSearchClient.instances[0].config == {
        "hosts": ["https://one.example.com:9200"],
        "username": None,
        "password": None,
        "api_key": "one-key",
        "verify_certs": True,
        "timeout": 3.5,
    }


def test_unknown_cluster_raises_clear_error(monkeypatch):
    from src.clients import create_search_client_manager

    monkeypatch.setenv(
        "ELASTICSEARCH_CLUSTERS",
        json.dumps({"prod": {"hosts": ["https://prod.example.com:9200"]}}),
    )
    monkeypatch.setattr("src.clients.load_dotenv", lambda: None)
    monkeypatch.setattr("src.clients.SearchClient", FakeSearchClient)

    manager = create_search_client_manager("elasticsearch")

    with pytest.raises(ValueError, match="Unknown cluster 'missing'"):
        manager.get_client("missing")
