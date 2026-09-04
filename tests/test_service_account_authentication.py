"""Offline contracts for Autodesk Secure Service Account authentication."""

import time
from unittest.mock import MagicMock, patch

import pytest
from requests.auth import HTTPBasicAuth

from acc_sdk import Authentication
from acc_sdk.authentication import GrantType


OIDC_SPEC = {
    "token_endpoint": "https://developer.api.autodesk.com/authentication/v2/token",
    "scopes_supported": ["data:read", "data:write"],
}


def token_response(access_token: str):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
    }
    return response


def make_service_account_auth(session=None):
    token_store = {} if session is None else session
    with patch.object(Authentication, "get_oidc_spec", return_value=OIDC_SPEC):
        auth = Authentication.for_service_account(
            client_id="client-id",
            client_secret="client-secret",
            service_account_id="service-account-id",
            key_id="key-id",
            private_key="PRIVATE KEY FROM SECRET STORE",
            scopes=["data:read", "data:write"],
            session=token_store,
        )
    return auth, token_store


@patch("acc_sdk.authentication.time.time", return_value=1_800_000_000.25)
@patch("acc_sdk.authentication.jwt.encode", return_value="signed-assertion")
@patch("acc_sdk.authentication.HttpTransport.post")
def test_factory_lazily_exchanges_signed_assertion_for_user_context_token(
    mock_post, mock_encode, _mock_time
):
    auth, session = make_service_account_auth()
    mock_post.return_value = token_response("ssa-access-token")

    assert mock_post.call_count == 0
    assert auth.get_3legged_token() == "ssa-access-token"

    mock_encode.assert_called_once_with(
        {
            "iss": "client-id",
            "sub": "service-account-id",
            "aud": OIDC_SPEC["token_endpoint"],
            "exp": 1_800_000_300,
            "iat": 1_800_000_000,
            "scope": ["data:read", "data:write"],
        },
        "PRIVATE KEY FROM SECRET STORE",
        algorithm="RS256",
        headers={"kid": "key-id", "alg": "RS256"},
    )
    call = mock_post.call_args
    assert call.args == (OIDC_SPEC["token_endpoint"],)
    assert call.kwargs["data"] == {
        "grant_type": GrantType.ServiceAccount.value,
        "assertion": "signed-assertion",
    }
    assert isinstance(call.kwargs["auth"], HTTPBasicAuth)
    assert call.kwargs["auth"].username == "client-id"
    assert call.kwargs["auth"].password == "client-secret"
    stored = session["accapi_service_account"]
    assert stored["grant_type"] == GrantType.ServiceAccount.value
    assert stored["scopes"] == ["data:read", "data:write"]
    assert stored["expires_at"] == 1_800_003_600.25
    assert "PRIVATE KEY" not in repr(session)


@patch("acc_sdk.authentication.jwt.encode", return_value="signed-assertion")
@patch("acc_sdk.authentication.HttpTransport.post")
def test_expiring_service_account_token_is_reissued_without_refresh_token(
    mock_post, _mock_encode
):
    auth, session = make_service_account_auth()
    mock_post.side_effect = [token_response("first-token"), token_response("second-token")]

    assert auth.get_3legged_token() == "first-token"
    session["accapi_service_account"]["expires_at"] = time.time() + 30
    assert auth.get_3legged_token() == "second-token"
    assert mock_post.call_count == 2
    assert auth.get_token_names() == ["accapi_service_account"]


def test_factory_does_not_change_legacy_constructor_or_two_legged_precedence():
    with patch.object(Authentication, "get_oidc_spec", return_value=OIDC_SPEC):
        auth = Authentication(
            client_id="client-id",
            client_secret="client-secret",
            session={
                "accapi_2legged": {
                    "access_token": "two-legged-token",
                    "expires_at": 9_999_999_999,
                    "grant_type": GrantType.ClientCreds.value,
                    "scopes": ["data:read"],
                }
            },
        )

    assert auth.get_2legged_token() == "two-legged-token"
    assert auth.get_3legged_token() is None


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [
        ("service_account_id", "", ValueError),
        ("key_id", "", ValueError),
        ("private_key", "", ValueError),
        ("scopes", [], ValueError),
        ("scopes", "data:read", TypeError),
    ],
)
def test_factory_rejects_incomplete_service_account_configuration(
    field, value, error_type
):
    kwargs = {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "service_account_id": "service-account-id",
        "key_id": "key-id",
        "private_key": "PRIVATE KEY FROM SECRET STORE",
        "scopes": ["data:read"],
    }
    kwargs[field] = value

    with pytest.raises(error_type), patch.object(
        Authentication, "get_oidc_spec", return_value=OIDC_SPEC
    ):
        Authentication.for_service_account(**kwargs)
