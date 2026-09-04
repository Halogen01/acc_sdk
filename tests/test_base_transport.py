from unittest.mock import MagicMock, patch

from acc_sdk.authentication import Authentication
from acc_sdk.base import AccBase
from acc_sdk.transport import HttpTransport


def make_base(account_id="account-id"):
    auth = MagicMock(spec=Authentication)
    auth.admin_email = ""
    auth.get_2legged_token.return_value = "two-legged-token"
    auth.get_3legged_token.return_value = None
    transport = MagicMock(spec=HttpTransport)
    auth.transport = transport

    with patch.object(AccBase, "_get_company_id", return_value=None):
        base = AccBase(auth_client=auth, account_id=account_id)

    return base, transport


def test_base_reuses_the_authenticated_clients_transport():
    base, transport = make_base()

    assert base.transport is transport
    assert base.auth_client.transport is transport


def test_company_lookup_uses_shared_transport_and_bearer_header():
    base, transport = make_base()
    response = MagicMock(status_code=200)
    response.json.return_value = {"results": [{"id": "company-id"}]}
    transport.get.return_value = response

    result = base._get_company_id()

    assert result == "company-id"
    transport.get.assert_called_once_with(
        "https://developer.api.autodesk.com/construction/admin/v1/accounts/account-id/companies",
        headers={"Authorization": "Bearer two-legged-token"},
    )


def test_hub_lookup_uses_shared_transport_and_preserves_response_shape():
    base, transport = make_base()
    response = MagicMock(status_code=200)
    response.json.return_value = {"data": [{"id": "b.account-id"}]}
    transport.get.return_value = response

    result = base._get_hub_id()

    assert result == "b.account-id"
    transport.get.assert_called_once_with(
        "https://developer.api.autodesk.com/project/v1/hubs",
        headers={"Authorization": "Bearer two-legged-token"},
    )
