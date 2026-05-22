import pytest
from fastmcp.exceptions import ToolError

from src import auth
from src.auth import BearerAuthMiddleware

pytestmark = pytest.mark.unit


def test_bearer_token_is_extracted_case_insensitively(monkeypatch):
    monkeypatch.setattr(
        auth,
        "get_http_headers",
        lambda: {"Authorization": "Bearer secret-token"},
    )

    assert auth._get_bearer_token() == "secret-token"


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic secret-token"},
        {"Authorization": "Bearer "},
    ],
)
def test_bearer_token_returns_none_for_missing_or_invalid_header(monkeypatch, headers):
    monkeypatch.setattr(auth, "get_http_headers", lambda: headers)

    assert auth._get_bearer_token() is None


def test_auth_middleware_allows_requests_when_disabled(monkeypatch):
    middleware = BearerAuthMiddleware(api_key=None)
    monkeypatch.setattr(auth, "_get_bearer_token", lambda: None)

    middleware._check_auth()

    assert middleware.is_enabled is False


def test_auth_middleware_accepts_valid_token(monkeypatch):
    middleware = BearerAuthMiddleware(api_key="secret")
    monkeypatch.setattr(auth, "_get_bearer_token", lambda: "secret")

    middleware._check_auth()


def test_auth_middleware_rejects_missing_token(monkeypatch):
    middleware = BearerAuthMiddleware(api_key="secret")
    monkeypatch.setattr(auth, "_get_bearer_token", lambda: None)

    with pytest.raises(ToolError, match="Missing or invalid Authorization header"):
        middleware._check_auth()


def test_auth_middleware_rejects_invalid_token(monkeypatch):
    middleware = BearerAuthMiddleware(api_key="secret")
    monkeypatch.setattr(auth, "_get_bearer_token", lambda: "wrong")

    with pytest.raises(ToolError, match="Invalid API key"):
        middleware._check_auth()
