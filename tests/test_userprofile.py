import unittest
from unittest.mock import MagicMock

from acc_sdk.base import AccBase
from acc_sdk.transport import HttpTransport
from acc_sdk.userprofile import AccUserProfileApi


class TestAccUserProfileApi(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.get_private_token.return_value = "private-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccUserProfileApi(self.base)

    def test_get_user_info_uses_shared_transport(self):
        profile = {"sub": "user-id", "email": "user@example.com"}
        response = MagicMock()
        response.json.return_value = profile
        self.base.transport.get.return_value = response

        result = self.api.get_user_info()

        self.assertEqual(result, profile)
        self.base.transport.get.assert_called_once_with(
            "https://api.userprofile.autodesk.com/userinfo",
            headers={"Authorization": "Bearer private-token"},
        )
        response.raise_for_status.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
