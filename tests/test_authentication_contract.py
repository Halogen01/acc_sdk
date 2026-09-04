"""Compatibility contracts for authentication used by the current consumers.

These tests deliberately mock Autodesk endpoints. They protect the public
``Authentication`` and ``Acc`` behavior used by ACC-Bulk-Manager and
Peritas-Portal without requiring credentials or making network requests.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from requests.auth import HTTPBasicAuth

from acc_sdk import Acc, Authentication
from acc_sdk.authentication import GrantType
from acc_sdk.base import AccBase


OIDC_SPEC = {
    "authorization_endpoint": "https://example.test/authorize",
    "token_endpoint": "https://example.test/token",
    "introspect_endpoint": "https://example.test/introspect",
    "revoke_endpoint": "https://example.test/revoke",
    "userinfo_endpoint": "https://example.test/userinfo",
    "jwks_uri": "https://example.test/keys",
    "scopes_supported": ["account:read", "account:write", "data:read"],
}


def make_auth(session=None):
    token_store = {} if session is None else session
    with patch.object(Authentication, "get_oidc_spec", return_value=OIDC_SPEC):
        auth = Authentication(
            client_id="client-id",
            client_secret="client-secret",
            admin_email="admin@example.com",
            session=token_store,
            callback_url="https://app.example.test/callback",
        )
    return auth, token_store


def token_response(access_token, refresh_token=None):
    response = MagicMock()
    response.status_code = 200
    payload = {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
    }
    if refresh_token:
        payload["refresh_token"] = refresh_token
    response.json.return_value = payload
    return response


def assert_confidential_client_auth(call):
    request_auth = call.kwargs["auth"]
    assert isinstance(request_auth, HTTPBasicAuth)
    assert request_auth.username == "client-id"
    assert request_auth.password == "client-secret"
    assert "client_id" not in call.kwargs["data"]
    assert "client_secret" not in call.kwargs["data"]


def test_constructor_preserves_consumer_configuration_and_session():
    session = {}

    auth, token_store = make_auth(session)

    assert auth._session is session
    assert token_store is session
    assert auth.client_id == "client-id"
    assert auth.client_secret == "client-secret"
    assert auth.admin_email == "admin@example.com"
    assert auth.callback_url == "https://app.example.test/callback"
    assert auth.token_url == OIDC_SPEC["token_endpoint"]


@patch("acc_sdk.authentication.HttpTransport.post")
def test_two_legged_token_acquisition_preserves_session_contract(mock_post):
    auth, session = make_auth()
    mock_post.return_value = token_response("first-access-token")
    before = datetime.now().timestamp()

    token = auth.request_2legged_token(scopes=["account:read", "data:read"])

    assert token is session["accapi_2legged"]
    assert token["access_token"] == "first-access-token"
    assert token["grant_type"] == GrantType.ClientCreds.value
    assert token["scopes"] == ["account:read", "data:read"]
    assert token["expires_at"] >= before + 3599
    assert auth.get_2legged_token() == "first-access-token"
    assert auth.get_token_names() == ["accapi_2legged"]
    assert_confidential_client_auth(mock_post.call_args)


@patch("acc_sdk.authentication.HttpTransport.post")
def test_explicit_two_legged_renewal_replaces_token_without_duplicate_name(mock_post):
    auth, session = make_auth()
    mock_post.side_effect = [
        token_response("first-access-token"),
        token_response("renewed-access-token"),
    ]

    auth.request_2legged_token(scopes=["account:read"])
    renewed = auth.request_2legged_token(scopes=["account:read"])

    assert renewed is session["accapi_2legged"]
    assert renewed["access_token"] == "renewed-access-token"
    assert auth.get_2legged_token() == "renewed-access-token"
    assert auth.get_token_names() == ["accapi_2legged"]
    assert_confidential_client_auth(mock_post.call_args)


@patch("acc_sdk.authentication.HttpTransport.post")
def test_expired_two_legged_token_renews_automatically(mock_post):
    session = {
        "accapi_2legged": {
            "access_token": "expired-access-token",
            "expires_at": datetime.now().timestamp() - 1,
            "grant_type": GrantType.ClientCreds.value,
            "scopes": ["account:read"],
        }
    }
    auth, _ = make_auth(session)
    mock_post.return_value = token_response("renewed-access-token")

    assert auth.get_2legged_token() == "renewed-access-token"
    assert session["accapi_2legged"]["access_token"] == "renewed-access-token"
    assert mock_post.call_args.kwargs["data"]["scope"] == "account:read"
    assert_confidential_client_auth(mock_post.call_args)


@patch("acc_sdk.authentication.HttpTransport.post")
def test_private_authorization_code_exchange_uses_basic_auth(mock_post):
    auth, session = make_auth()
    mock_post.return_value = token_response("private-access-token", "refresh-token")

    token = auth.request_authcode_access_token(
        code="authorization-code", scopes=["data:read"]
    )

    assert token is session["accapi_3legged"]
    assert token["grant_type"] == GrantType.AuthCode.value
    assert_confidential_client_auth(mock_post.call_args)


@patch("acc_sdk.authentication.HttpTransport.post")
def test_private_pkce_exchange_uses_basic_auth(mock_post):
    auth, session = make_auth()
    mock_post.return_value = token_response("pkce-access-token", "refresh-token")

    auth.request_authcode_private_pkce_access_token(
        code="authorization-code",
        code_verifier="code-verifier",
        scopes=["data:read"],
    )

    assert session["accapi_3legged"]["access_token"] == "pkce-access-token"
    assert_confidential_client_auth(mock_post.call_args)


@patch("acc_sdk.authentication.HttpTransport.post")
def test_private_refresh_uses_basic_auth(mock_post):
    session = {
        "accapi_3legged": {
            "access_token": "old-access-token",
            "refresh_token": "old-refresh-token",
            "expires_at": datetime.now().timestamp() + 3600,
            "grant_type": GrantType.AuthCode.value,
            "scopes": ["data:read"],
        }
    }
    auth, _ = make_auth(session)
    mock_post.return_value = token_response("refreshed-access-token", "new-refresh-token")

    token = auth.request_private_refresh_token(scopes=["data:read"])

    assert token is session["accapi_3legged"]
    assert token["access_token"] == "refreshed-access-token"
    assert_confidential_client_auth(mock_post.call_args)


@patch("acc_sdk.authentication.HttpTransport.post")
def test_private_introspection_uses_basic_auth(mock_post):
    session = {
        "accapi_3legged": {
            "access_token": "private-access-token",
            "expires_at": datetime.now().timestamp() + 3600,
            "grant_type": GrantType.AuthCode.value,
            "scopes": ["data:read"],
        }
    }
    auth, _ = make_auth(session)
    response = MagicMock(status_code=200)
    response.json.return_value = {"active": True}
    mock_post.return_value = response

    result = auth.introspect_private_token()

    assert result == {"active": True}
    assert_confidential_client_auth(mock_post.call_args)


@patch("acc_sdk.authentication.HttpTransport.post")
def test_public_introspection_never_sends_client_secret(mock_post):
    session = {
        "accapi_3legged": {
            "access_token": "public-access-token",
            "expires_at": datetime.now().timestamp() + 3600,
            "grant_type": GrantType.AuthCode.value,
            "scopes": ["data:read"],
        }
    }
    auth, _ = make_auth(session)
    response = MagicMock(status_code=200)
    response.json.return_value = {"active": True}
    mock_post.return_value = response

    result = auth.introspect_public_token()

    assert result == {"active": True}
    assert mock_post.call_args.kwargs["data"] == {
        "token": "public-access-token",
        "client_id": "client-id",
    }
    assert "auth" not in mock_post.call_args.kwargs


def test_acc_construction_preserves_consumer_service_surface():
    auth = MagicMock(spec=Authentication)
    auth.admin_email = "admin@example.com"
    auth.get_2legged_token.return_value = "two-legged-token"
    auth.get_3legged_token.return_value = None
    user_info = {
        "id": "user-id",
        "company_id": "company-id",
        "account_id": "account-id",
    }

    with patch.object(AccBase, "_get_user_by_email", return_value=user_info):
        acc = Acc(auth_client=auth, account_id="account-id")

    assert acc.auth_client is auth
    assert acc.base.auth_client is auth
    assert acc.base.admin_email == "admin@example.com"
    assert acc.base.account_id == "account-id"
    assert acc.base.hub_id == "b.account-id"
    assert acc.base.company_id == "company-id"
    assert acc.base.user_info == user_info
    assert acc.projects.base is acc.base
    assert acc.account_users.base is acc.base
    assert acc.project_users.base is acc.base
