"""Consumer-specific contracts not covered by the original SDK unit tests."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from acc_sdk.account_users import AccAccountUsersApi
from acc_sdk.base import AccBase
from acc_sdk.project_users import AccProjectUsersApi
from acc_sdk.transport import HttpTransport


MEMBER_PRODUCTS = [
    {"key": "projectAdministration", "access": "none"},
    {"key": "designCollaboration", "access": "member"},
    {"key": "build", "access": "member"},
    {"key": "cost", "access": "member"},
    {"key": "modelCoordination", "access": "member"},
    {"key": "docs", "access": "member"},
    {"key": "insight", "access": "member"},
    {"key": "takeoff", "access": "member"},
]

ADMIN_PRODUCTS = [
    {"key": "projectAdministration", "access": "administrator"},
    {"key": "designCollaboration", "access": "administrator"},
    {"key": "build", "access": "administrator"},
    {"key": "cost", "access": "administrator"},
    {"key": "modelCoordination", "access": "administrator"},
    {"key": "docs", "access": "administrator"},
    {"key": "insight", "access": "administrator"},
    {"key": "takeoff", "access": "administrator"},
]


def project_users_api():
    base = MagicMock(spec=AccBase)
    base.get_private_token.return_value = "access-token"
    base.user_info = {"uid": "admin-user-id"}
    base.transport = MagicMock(spec=HttpTransport)
    return AccProjectUsersApi(base)


def account_users_api():
    base = MagicMock(spec=AccBase)
    base.get_2leggedToken.return_value = "access-token"
    base.account_id = "account-id"
    base.company_id = "company-id"
    base.user_info = {"uid": "admin-user-id"}
    return AccAccountUsersApi(base)


def test_product_access_constants_preserve_consumer_values():
    assert AccProjectUsersApi.productmember == MEMBER_PRODUCTS
    assert AccProjectUsersApi.productadmin == ADMIN_PRODUCTS


def test_post_user_preserves_roles_email_suppression_and_return_shape():
    api = project_users_api()
    created_user = {
        "id": "project-user-id",
        "email": "person@example.com",
        "products": MEMBER_PRODUCTS,
    }
    response = MagicMock(status_code=201)
    response.json.return_value = created_user
    api.base.transport.post.return_value = response
    user = {
        "email": "person@example.com",
        "products": MEMBER_PRODUCTS,
        "roleIds": ["role-id"],
        "suppressAdministrativeEmails": True,
        "ignored": "not forwarded",
    }

    result = api.post_user(project_id="project-id", user=user)

    assert result == created_user
    api.base.transport.post.assert_called_once_with(
        "https://developer.api.autodesk.com/construction/admin/v1/projects/project-id/users",
        headers={
            "Authorization": "Bearer access-token",
            "User-Id": "admin-user-id",
            "Content-Type": "application/json",
        },
        json={
            "email": "person@example.com",
            "products": MEMBER_PRODUCTS,
            "roleIds": ["role-id"],
            "suppressAdministrativeEmails": True,
        },
        timeout=100,
    )


def test_post_user_preserves_http_409_on_raised_exception():
    api = project_users_api()
    response = MagicMock(status_code=409, text="User already exists")
    error = requests.HTTPError("409 Client Error", response=response)
    response.raise_for_status.side_effect = error
    response.json.return_value = {"detail": "User already exists"}
    api.base.transport.post.return_value = response

    with pytest.raises(requests.HTTPError) as caught:
        api.post_user(
            project_id="project-id",
            user={"email": "person@example.com", "products": MEMBER_PRODUCTS},
        )

    assert caught.value.response is response
    assert caught.value.response.status_code == 409
    assert "already" in caught.value.response.text.lower()


def test_patch_project_users_preserves_bulk_consumer_call_shape():
    api = project_users_api()
    project_user = {
        "id": "project-user-id",
        "email": "person@example.com",
        "products": [{"key": "projectAdministration", "access": "member"}],
    }
    api.get_users = MagicMock(return_value=[project_user])
    api.patch_user = MagicMock(return_value={"id": "project-user-id"})

    result = api.patch_project_users(
        projects=[{"id": "project-id", "jobNumber": "P-001"}],
        users=[{"email": "person@example.com"}],
        products=ADMIN_PRODUCTS,
    )

    assert result is None
    api.get_users.assert_called_once_with("project-id", follow_pagination=True)
    api.patch_user.assert_called_once_with(
        "project-id", "project-user-id", {"products": ADMIN_PRODUCTS}
    )


def test_account_users_get_user_compatibility_alias():
    api = account_users_api()

    with patch.object(api, "get_user_by_id", return_value={"id": "user-id"}) as lookup:
        result = api.get_user(user_id="user-id", fields="uid,email")

    assert result == {"id": "user-id"}
    lookup.assert_called_once_with(user_id="user-id", fields="uid,email")
