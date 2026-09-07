"""Contracts for the explicit client-credentials and auth-code factories."""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.auth import HTTPBasicAuth

from acc_sdk import Authentication
from acc_sdk.authentication import GrantType


OIDC_SPEC = {
    "authorization_endpoint": "https://example.test/authorize",
    "token_endpoint": "https://example.test/token",
    "introspect_endpoint": "https://example.test/introspect",
    "revoke_endpoint": "https://example.test/revoke",
    "userinfo_endpoint": "https://example.test/userinfo",
    "jwks_uri": "https://example.test/keys",
    "scopes_supported": ["account:read", "data:read", "data:write"],
}


def token_response(access_token: str):
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
    }
    return response


def make_client_credentials(**overrides):
    kwargs = {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "scopes": ["account:read", "data:read"],
    }
    kwargs.update(overrides)
    with patch.object(Authentication, "get_oidc_spec", return_value=OIDC_SPEC):
        return Authentication.for_client_credentials(**kwargs)


@patch("acc_sdk.authentication.HttpTransport.post")
def test_client_credentials_factory_acquires_token_lazily(mock_post):
    scopes = ["account:read", "data:read"]
    auth = make_client_credentials(scopes=scopes)
    mock_post.return_value = token_response("factory-token")

    assert mock_post.call_count == 0
    assert auth.get_2legged_token() == "factory-token"
    assert scopes == ["account:read", "data:read"]

    call = mock_post.call_args
    assert call.kwargs["data"] == {
        "grant_type": GrantType.ClientCreds.value,
        "scope": "account:read data:read",
    }
    assert isinstance(call.kwargs["auth"], HTTPBasicAuth)
    assert call.kwargs["auth"].username == "client-id"
    assert call.kwargs["auth"].password == "client-secret"


@patch("acc_sdk.authentication.HttpTransport.post")
def test_client_credentials_factory_uses_only_its_configured_token_name(mock_post):
    session = {
        "accapi_other": {
            "access_token": "unrelated-token",
            "expires_at": time.time() + 3600,
            "grant_type": GrantType.ClientCreds.value,
            "scopes": ["data:read"],
        }
    }
    auth = make_client_credentials(session=session, token_name="integration")
    mock_post.return_value = token_response("integration-token")

    assert auth.get_2legged_token() == "integration-token"
    assert session["accapi_other"]["access_token"] == "unrelated-token"
    assert session["accapi_integration"]["access_token"] == "integration-token"


@patch("acc_sdk.authentication.HttpTransport.post")
def test_client_credentials_factory_renews_token_before_expiry(mock_post):
    auth = make_client_credentials()
    mock_post.side_effect = [token_response("first-token"), token_response("renewed-token")]

    assert auth.get_2legged_token() == "first-token"
    auth._session["accapi_2legged"]["expires_at"] = time.time() + 30
    assert auth.get_2legged_token() == "renewed-token"
    assert mock_post.call_count == 2


@patch("acc_sdk.authentication.HttpTransport.post")
def test_factory_client_preserves_http_response_on_token_failure(mock_post):
    auth = make_client_credentials()
    response = MagicMock(status_code=401, text="unauthorized")
    error = requests.HTTPError("401 Client Error", response=response)
    response.raise_for_status.side_effect = error
    mock_post.return_value = response

    with pytest.raises(requests.HTTPError) as caught:
        auth.get_2legged_token()

    assert caught.value.response.status_code == 401


@patch("acc_sdk.authentication.HttpTransport.post")
def test_legacy_client_credentials_failure_shape_is_unchanged(mock_post):
    with patch.object(Authentication, "get_oidc_spec", return_value=OIDC_SPEC):
        auth = Authentication(client_id="client-id", client_secret="client-secret", session={})
    response = MagicMock(status_code=401, text="unauthorized")
    mock_post.return_value = response

    with pytest.raises(Exception, match="Failed to get 2-legged token: unauthorized"):
        auth.request_2legged_token(scopes=["data:read"])

    response.raise_for_status.assert_not_called()


def test_authorization_code_factory_supports_confidential_clients():
    session = {}
    with patch.object(Authentication, "get_oidc_spec", return_value=OIDC_SPEC):
        auth = Authentication.for_authorization_code(
            client_id="client-id",
            client_secret="client-secret",
            callback_url="https://app.example.test/callback",
            session=session,
            logout_url="https://app.example.test/logout",
        )

    assert auth._session is session
    assert auth.client_secret == "client-secret"
    assert auth.callback_url == "https://app.example.test/callback"
    assert auth.post_logout_url == "https://app.example.test/logout"
    assert auth._authorization_code_provider is True


def test_authorization_code_factory_supports_public_pkce_clients():
    with patch.object(Authentication, "get_oidc_spec", return_value=OIDC_SPEC):
        auth = Authentication.for_authorization_code(
            client_id="client-id",
            callback_url="https://app.example.test/callback",
        )

    assert auth.client_secret == ""
    assert auth._authorization_code_provider is True


def test_factory_default_sessions_are_isolated():
    first = make_client_credentials()
    second = make_client_credentials()

    first._session["marker"] = True
    assert "marker" not in second._session


@pytest.mark.parametrize(
    ("factory", "kwargs", "error_type"),
    [
        ("client", {"client_id": ""}, ValueError),
        ("client", {"client_secret": ""}, ValueError),
        ("client", {"scopes": []}, ValueError),
        ("client", {"scopes": "data:read"}, TypeError),
        ("client", {"token_name": ""}, ValueError),
        ("authorization", {"client_id": ""}, ValueError),
        ("authorization", {"callback_url": ""}, ValueError),
        ("authorization", {"client_secret": None}, TypeError),
    ],
)
def test_factories_reject_invalid_configuration_before_construction(
    factory, kwargs, error_type
):
    with patch.object(Authentication, "get_oidc_spec") as mock_oidc:
        with pytest.raises(error_type):
            if factory == "client":
                defaults = {
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                    "scopes": ["data:read"],
                }
                defaults.update(kwargs)
                Authentication.for_client_credentials(**defaults)
            else:
                defaults = {
                    "client_id": "client-id",
                    "callback_url": "https://app.example.test/callback",
                }
                defaults.update(kwargs)
                Authentication.for_authorization_code(**defaults)

    mock_oidc.assert_not_called()


def test_client_credentials_factory_rejects_unsupported_scope_before_token_request():
    with patch.object(Authentication, "get_oidc_spec", return_value=OIDC_SPEC), patch(
        "acc_sdk.authentication.HttpTransport.post"
    ) as mock_post:
        with pytest.raises(ValueError, match="unsupported-scope"):
            Authentication.for_client_credentials(
                client_id="client-id",
                client_secret="client-secret",
                scopes=["data:read", "unsupported-scope"],
            )

    mock_post.assert_not_called()
