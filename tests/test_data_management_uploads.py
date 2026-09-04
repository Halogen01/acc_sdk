import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
from unittest.mock import patch

import requests

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


class TestSignedUrlPartUpload(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccDataManagementApi(self.base)

    def response(self, status_code=200, headers=None):
        response = MagicMock(status_code=status_code)
        response.headers = headers or {}
        if status_code >= 400:
            response.raise_for_status.side_effect = requests.HTTPError(
                f"HTTP {status_code}", response=response
            )
        return response

    def test_uploads_only_the_requested_file_segment_and_returns_etag(self):
        response = self.response(headers={"ETag": '"part-etag"'})
        uploaded = []

        def capture_upload(url, headers, data):
            uploaded.append(data.read())
            return response

        self.base.transport.put.side_effect = capture_upload

        with TemporaryDirectory() as directory:
            source = Path(directory) / "model.rvt"
            source.write_bytes(b"0123456789")

            result = self.api.upload_file_part(
                "https://example.s3.amazonaws.com/signed-part",
                source,
                offset=2,
                length=5,
            )

        self.assertEqual(result, '"part-etag"')
        self.assertEqual(uploaded, [b"23456"])
        self.base.transport.put.assert_called_once()
        _, kwargs = self.base.transport.put.call_args
        self.assertEqual(kwargs["headers"], {"Content-Length": "5"})
        response.raise_for_status.assert_called_once_with()
        response.close.assert_called_once_with()

    @patch("acc_sdk.data_management.time.sleep")
    def test_retries_transient_status_with_same_file_segment(
        self, mocked_sleep
    ):
        retry_response = self.response(503, {"Retry-After": "2"})
        success_response = self.response(200, {"ETag": '"part-etag"'})
        uploaded = []

        def capture_upload(url, headers, data):
            uploaded.append(data.read())
            return retry_response if len(uploaded) == 1 else success_response

        self.base.transport.put.side_effect = capture_upload

        with TemporaryDirectory() as directory:
            source = Path(directory) / "model.rvt"
            source.write_bytes(b"abcdefghij")

            result = self.api.upload_file_part(
                "https://example.s3.amazonaws.com/signed-part",
                source,
                offset=3,
                length=4,
                max_retries=1,
            )

        self.assertEqual(result, '"part-etag"')
        self.assertEqual(uploaded, [b"defg", b"defg"])
        mocked_sleep.assert_called_once_with(2.0)
        retry_response.close.assert_called_once_with()
        success_response.close.assert_called_once_with()

    @patch("acc_sdk.data_management.time.sleep")
    def test_retries_connection_error_with_bounded_backoff(self, mocked_sleep):
        success_response = self.response(200, {"ETag": '"part-etag"'})
        self.base.transport.put.side_effect = [requests.Timeout(), success_response]

        with TemporaryDirectory() as directory:
            source = Path(directory) / "model.rvt"
            source.write_bytes(b"content")

            result = self.api.upload_file_part(
                "https://example.s3.amazonaws.com/signed-part",
                source,
                offset=0,
                length=7,
                max_retries=1,
            )

        self.assertEqual(result, '"part-etag"')
        mocked_sleep.assert_called_once_with(0.5)

    @patch("acc_sdk.data_management.time.sleep")
    def test_does_not_retry_expired_signed_url(self, mocked_sleep):
        response = self.response(403)
        self.base.transport.put.return_value = response

        with TemporaryDirectory() as directory:
            source = Path(directory) / "model.rvt"
            source.write_bytes(b"content")

            with self.assertRaises(requests.HTTPError):
                self.api.upload_file_part(
                    "https://example.s3.amazonaws.com/expired-part",
                    source,
                    offset=0,
                    length=7,
                )

        self.base.transport.put.assert_called_once()
        mocked_sleep.assert_not_called()
        response.close.assert_called_once_with()

    def test_rejects_invalid_file_ranges_and_retry_limits_before_request(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "model.rvt"
            source.write_bytes(b"content")
            invalid_arguments = [
                {"offset": True, "length": 1},
                {"offset": -1, "length": 1},
                {"offset": 0, "length": -1},
                {"offset": 5, "length": 3},
                {"offset": 0, "length": 1, "max_retries": True},
                {"offset": 0, "length": 1, "max_retries": 6},
            ]

            for arguments in invalid_arguments:
                with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                    self.api.upload_file_part(
                        "https://example.s3.amazonaws.com/signed-part",
                        source,
                        **arguments,
                    )

        self.base.transport.put.assert_not_called()


if __name__ == "__main__":
    unittest.main()
