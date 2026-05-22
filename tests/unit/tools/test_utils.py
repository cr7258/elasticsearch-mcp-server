import pytest

from src.tools.utils import get_search_client

pytestmark = pytest.mark.unit


class _Manager:
    def __init__(self):
        self.requested = []

    def get_client(self, cluster=None):
        self.requested.append(cluster)
        return ("client-for", cluster)


def test_get_search_client_resolves_named_cluster_from_manager():
    manager = _Manager()

    result = get_search_client(manager, "staging")

    assert result == ("client-for", "staging")
    assert manager.requested == ["staging"]


def test_get_search_client_uses_default_cluster_when_omitted():
    manager = _Manager()

    result = get_search_client(manager)

    assert result == ("client-for", None)
    assert manager.requested == [None]


def test_get_search_client_returns_object_unchanged_when_not_a_manager():
    plain_client = object()

    assert get_search_client(plain_client) is plain_client
    assert get_search_client(plain_client, "anything") is plain_client
