import unittest
from unittest.mock import MagicMock, mock_open, patch

from acc_sdk.base import AccBase
from acc_sdk.companies import AccCompaniesApi
from acc_sdk.transport import HttpTransport


class TestAccCompaniesApi(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.account_id = "account-id"
        self.base.user_info = {"uid": "user-id"}
        self.base.get_2leggedToken.return_value = "two-legged-token"
        self.base.get_private_token.return_value = "private-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccCompaniesApi(self.base)

    def test_get_companies_preserves_filters_and_result_shape(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "results": [{"id": "company-id"}],
            "pagination": {"totalResults": 1},
        }
        self.base.transport.get.return_value = response

        result = self.api.get_companies(
            filter_name="Builder",
            orFilters=["name", "trade"],
            sort=["name"],
            fields=["id", "name"],
            limit=50,
            offset=10,
        )

        self.assertEqual(result, [{"id": "company-id"}])
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/construction/admin/v1/accounts/account-id/companies",
            headers={
                "Authorization": "Bearer two-legged-token",
                "user_id": "user-id",
            },
            params={
                "filter[name]": "Builder",
                "orFilters": "name,trade",
                "sort": "name",
                "fields": "id,name",
                "limit": 50,
                "offset": 10,
            },
        )

    def test_get_company_uses_private_token(self):
        company = {"id": "company-id", "name": "Builder"}
        response = MagicMock(status_code=200)
        response.json.return_value = company
        self.base.transport.get.return_value = response

        result = self.api.get_company("company-id")

        self.assertEqual(result, company)
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/hq/v1/accounts/account-id/companies/company-id",
            headers={
                "Authorization": "Bearer private-token",
                "User-Id": "user-id",
            },
        )

    def test_update_company_preserves_region_endpoint_and_payload(self):
        company = {"id": "company-id", "name": "Builder"}
        response = MagicMock(status_code=200)
        response.json.return_value = company
        self.base.transport.patch.return_value = response

        result = self.api.update_company(
            "account-id", "company-id", {"name": "Builder"}, region="EMEA"
        )

        self.assertEqual(result, company)
        self.base.transport.patch.assert_called_once_with(
            "https://developer.api.autodesk.com/hq/v1/regions/eu/accounts/account-id/companies/company-id",
            json={"name": "Builder"},
            headers={
                "Authorization": "Bearer two-legged-token",
                "Content-Type": "application/json",
                "Region": "EMEA",
            },
        )

    def test_update_company_image_preserves_multipart_upload(self):
        company = {"id": "company-id"}
        response = MagicMock(status_code=200)
        response.json.return_value = company
        self.base.transport.patch.return_value = response
        file_reader = mock_open(read_data=b"image")

        with patch("acc_sdk.companies.open", file_reader, create=True):
            result = self.api.update_company_image(
                "account-id",
                "company-id",
                "company.png",
                mime_type="image/png",
            )

        self.assertEqual(result, company)
        self.base.transport.patch.assert_called_once_with(
            "https://developer.api.autodesk.com/hq/v1/accounts/account-id/companies/company-id/image",
            headers={"Authorization": "Bearer two-legged-token"},
            files={"chunk": ("company.png", file_reader(), "image/png")},
        )


if __name__ == "__main__":
    unittest.main()
