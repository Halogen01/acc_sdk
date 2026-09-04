import unittest
from unittest.mock import MagicMock

from acc_sdk.base import AccBase
from acc_sdk.data_management import AccDataManagementApi
from acc_sdk.transport import HttpTransport


class TestOssUploadRequests(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.get_private_token.return_value = "private-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccDataManagementApi(self.base)

    def response(self, payload):
        response = MagicMock()
        response.json.return_value = payload
        return response

    def test_get_signed_upload_encodes_keys_and_passes_all_options(self):
        payload = {
            "uploadKey": "upload-key",
            "urls": ["https://example.s3.amazonaws.com/part-10"],
        }
        response = self.response(payload)
        self.base.transport.get.return_value = response

        result = self.api.get_signed_s3_upload(
            "wip.dm.prod",
            "folder/My model #2.rvt",
            parts=1,
            first_part=10,
            upload_key="upload-key",
            minutes_expiration=10,
            use_acceleration=False,
        )

        self.assertEqual(result, payload)
        response.raise_for_status.assert_called_once_with()
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/oss/v2/buckets/"
            "wip.dm.prod/objects/folder%2FMy%20model%20%232.rvt/signeds3upload",
            headers={
                "Authorization": "Bearer private-token",
                "Content-Type": "application/json",
            },
            params={
                "parts": 1,
                "firstPart": 10,
                "uploadKey": "upload-key",
                "minutesExpiration": 10,
                "useAcceleration": False,
            },
        )

    def test_get_signed_upload_defaults_to_first_single_part(self):
        response = self.response({"uploadKey": "upload-key", "urls": ["url"]})
        self.base.transport.get.return_value = response

        self.api.get_signed_s3_upload("wip.dm.prod", "model.rvt")

        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/oss/v2/buckets/"
            "wip.dm.prod/objects/model.rvt/signeds3upload",
            headers={
                "Authorization": "Bearer private-token",
                "Content-Type": "application/json",
            },
            params={"parts": 1, "firstPart": 1},
        )

    def test_get_signed_upload_validates_bounds_before_request(self):
        invalid_arguments = [
            {"parts": True},
            {"parts": 0},
            {"parts": 26},
            {"first_part": 0},
            {"first_part": 2},
            {"minutes_expiration": 0},
            {"minutes_expiration": 61},
            {"use_acceleration": "true"},
        ]

        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.api.get_signed_s3_upload(
                    "wip.dm.prod", "model.rvt", **arguments
                )

        self.base.transport.get.assert_not_called()

    def test_complete_upload_sends_validation_values(self):
        payload = {
            "bucketKey": "wip.dm.prod",
            "objectKey": "folder/model.rvt",
            "size": 123,
        }
        response = self.response(payload)
        self.base.transport.post.return_value = response

        result = self.api.complete_signed_s3_upload(
            "wip.dm.prod",
            "folder/model.rvt",
            "upload-key",
            size=123,
            e_tags=['"etag-one"', '"etag-two"'],
        )

        self.assertEqual(result, payload)
        response.raise_for_status.assert_called_once_with()
        self.base.transport.post.assert_called_once_with(
            "https://developer.api.autodesk.com/oss/v2/buckets/"
            "wip.dm.prod/objects/folder%2Fmodel.rvt/signeds3upload",
            headers={
                "Authorization": "Bearer private-token",
                "Content-Type": "application/json",
            },
            json={
                "uploadKey": "upload-key",
                "size": 123,
                "eTags": ['"etag-one"', '"etag-two"'],
            },
        )

    def test_complete_upload_accepts_minimal_payload(self):
        response = self.response({"objectId": "storage-urn"})
        self.base.transport.post.return_value = response

        self.api.complete_signed_s3_upload(
            "wip.dm.prod", "model.rvt", "upload-key"
        )

        self.base.transport.post.assert_called_once_with(
            "https://developer.api.autodesk.com/oss/v2/buckets/"
            "wip.dm.prod/objects/model.rvt/signeds3upload",
            headers={
                "Authorization": "Bearer private-token",
                "Content-Type": "application/json",
            },
            json={"uploadKey": "upload-key"},
        )

    def test_complete_upload_validates_payload_before_request(self):
        invalid_arguments = [
            {"upload_key": ""},
            {"upload_key": "key", "size": True},
            {"upload_key": "key", "size": -1},
            {"upload_key": "key", "e_tags": []},
            {"upload_key": "key", "e_tags": [""]},
            {"upload_key": "key", "e_tags": "etag"},
        ]

        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.api.complete_signed_s3_upload(
                    "wip.dm.prod", "model.rvt", **arguments
                )

        self.base.transport.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
