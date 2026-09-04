import unittest
from unittest.mock import MagicMock

from acc_sdk.base import AccBase
from acc_sdk.data_management import AccDataManagementApi
from acc_sdk.transport import HttpTransport


class TestOssSignedDownload(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.get_private_token.return_value = "private-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccDataManagementApi(self.base)

    def test_parse_storage_urn_preserves_nested_object_key(self):
        result = self.api.parse_oss_storage_urn(
            "urn:adsk.objects:os.object:wip.dm.prod/folder/My model.rvt"
        )

        self.assertEqual(result, ("wip.dm.prod", "folder/My model.rvt"))

    def test_parse_storage_urn_rejects_invalid_values(self):
        invalid_values = [
            None,
            "",
            "urn:adsk.wipprod:fs.file:file-id",
            "urn:adsk.objects:os.object:bucket-only",
            "urn:adsk.objects:os.object:/object-only",
            "urn:adsk.objects:os.object:bucket/",
        ]

        for value in invalid_values:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.api.parse_oss_storage_urn(value)

    def test_get_signed_download_encodes_keys_and_passes_documented_options(self):
        payload = {
            "status": "complete",
            "url": "https://example.s3.amazonaws.com/signed-object",
            "params": {},
            "size": 123,
        }
        response = MagicMock()
        response.json.return_value = payload
        self.base.transport.get.return_value = response

        result = self.api.get_signed_s3_download(
            "wip.dm.prod",
            "folder/My model #2.rvt",
            minutes_expiration=10,
            use_cdn=True,
            public_resource_fallback=True,
        )

        self.assertEqual(result, payload)
        response.raise_for_status.assert_called_once_with()
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/oss/v2/buckets/"
            "wip.dm.prod/objects/folder%2FMy%20model%20%232.rvt/signeds3download",
            headers={"Authorization": "Bearer private-token"},
            params={
                "minutesExpiration": 10,
                "useCdn": True,
                "public-resource-fallback": True,
            },
        )

    def test_get_signed_download_omits_unspecified_options(self):
        response = MagicMock()
        response.json.return_value = {"status": "complete"}
        self.base.transport.get.return_value = response

        self.api.get_signed_s3_download("wip.dm.prod", "model.rvt")

        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/oss/v2/buckets/"
            "wip.dm.prod/objects/model.rvt/signeds3download",
            headers={"Authorization": "Bearer private-token"},
            params={},
        )

    def test_get_signed_download_rejects_invalid_expiration_before_request(self):
        for value in [True, 0, 61, 1.5, "10"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.api.get_signed_s3_download(
                    "wip.dm.prod", "model.rvt", minutes_expiration=value
                )

        self.base.transport.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
