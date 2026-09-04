import unittest
from unittest.mock import MagicMock

from acc_sdk.base import AccBase
from acc_sdk.business_units import AccBusinessUnitsApi
from acc_sdk.transport import HttpTransport


class TestAccBusinessUnitsApi(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.account_id = "account-id"
        self.base.get_2leggedToken.return_value = "token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccBusinessUnitsApi(self.base)

    def test_get_business_units_uses_shared_transport(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {"business_units": [{"id": "unit-id"}]}
        self.base.transport.get.return_value = response

        result = self.api.get_business_units()

        self.assertEqual(result, [{"id": "unit-id"}])
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/hq/v1/accounts/account-id/business_units_structure",
            headers={"Authorization": "Bearer token"},
        )

    def test_update_business_units_uses_shared_transport(self):
        units = [{"name": "Operations"}]
        response = MagicMock(status_code=200)
        response.json.return_value = units
        self.base.transport.put.return_value = response

        result = self.api.update_business_units(units)

        self.assertEqual(result, units)
        self.base.transport.put.assert_called_once_with(
            "https://developer.api.autodesk.com/hq/v1/accounts/account-id/business_units_structure",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
            json=units,
        )

    def test_get_business_units_preserves_http_error(self):
        response = MagicMock(status_code=500)
        response.json.return_value = {}
        self.base.transport.get.return_value = response

        self.api.get_business_units()

        response.raise_for_status.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
