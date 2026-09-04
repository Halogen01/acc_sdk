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


class TestFileUploadWorkflow(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.api = AccDataManagementApi(self.base)
        self.api.get_signed_s3_upload = MagicMock()
        self.api.upload_file_part = MagicMock()
        self.api.complete_signed_s3_upload = MagicMock()

    def create_file(self, directory, size):
        source = Path(directory) / "model.rvt"
        with source.open("wb") as source_file:
            source_file.truncate(size)
        return source

    def test_uploads_and_completes_a_single_part_file(self):
        self.api.get_signed_s3_upload.return_value = {
            "uploadKey": "upload-key",
            "urls": ["https://example.s3.amazonaws.com/part-one"],
        }
        self.api.upload_file_part.return_value = '"etag-one"'
        completed = {"objectId": "urn:adsk.objects:os.object:bucket/model.rvt"}
        self.api.complete_signed_s3_upload.return_value = completed

        with TemporaryDirectory() as directory:
            source = self.create_file(directory, 3)
            result = self.api.upload_file_to_oss(
                "wip.dm.prod",
                "folder/model.rvt",
                source,
                minutes_expiration=10,
                use_acceleration=False,
            )

        self.assertEqual(result, completed)
        self.api.get_signed_s3_upload.assert_called_once_with(
            "wip.dm.prod",
            "folder/model.rvt",
            parts=1,
            first_part=1,
            upload_key=None,
            minutes_expiration=10,
            use_acceleration=False,
        )
        self.api.upload_file_part.assert_called_once_with(
            "https://example.s3.amazonaws.com/part-one",
            source,
            0,
            3,
            max_retries=2,
        )
        self.api.complete_signed_s3_upload.assert_called_once_with(
            "wip.dm.prod",
            "folder/model.rvt",
            "upload-key",
            size=3,
            e_tags=['"etag-one"'],
        )

    def test_uploads_a_multipart_file_with_ordered_etags(self):
        part_size = self.api.MIN_MULTIPART_UPLOAD_PART_SIZE
        self.api.get_signed_s3_upload.return_value = {
            "uploadKey": "upload-key",
            "urls": [
                "https://example.s3.amazonaws.com/part-one",
                "https://example.s3.amazonaws.com/part-two",
            ],
        }
        self.api.upload_file_part.side_effect = ['"etag-one"', '"etag-two"']
        self.api.complete_signed_s3_upload.return_value = {"size": part_size + 2}

        with TemporaryDirectory() as directory:
            source = self.create_file(directory, part_size + 2)
            result = self.api.upload_file_to_oss(
                "wip.dm.prod", "model.rvt", source
            )

        self.assertEqual(result, {"size": part_size + 2})
        self.api.get_signed_s3_upload.assert_called_once_with(
            "wip.dm.prod",
            "model.rvt",
            parts=2,
            first_part=1,
            upload_key=None,
            minutes_expiration=None,
            use_acceleration=None,
        )
        self.assertEqual(
            self.api.upload_file_part.call_args_list,
            [
                unittest.mock.call(
                    "https://example.s3.amazonaws.com/part-one",
                    source,
                    0,
                    part_size,
                    max_retries=2,
                ),
                unittest.mock.call(
                    "https://example.s3.amazonaws.com/part-two",
                    source,
                    part_size,
                    2,
                    max_retries=2,
                ),
            ],
        )
        self.api.complete_signed_s3_upload.assert_called_once_with(
            "wip.dm.prod",
            "model.rvt",
            "upload-key",
            size=part_size + 2,
            e_tags=['"etag-one"', '"etag-two"'],
        )

    def test_requests_additional_url_batches_with_same_upload_key(self):
        part_size = self.api.MIN_MULTIPART_UPLOAD_PART_SIZE
        first_urls = [f"https://example.test/part-{part}" for part in range(1, 26)]
        self.api.get_signed_s3_upload.side_effect = [
            {"uploadKey": "upload-key", "urls": first_urls},
            {"uploadKey": "upload-key", "urls": ["https://example.test/part-26"]},
        ]
        self.api.upload_file_part.return_value = '"etag"'
        self.api.complete_signed_s3_upload.return_value = {"size": 26 * part_size}

        with TemporaryDirectory() as directory:
            source = self.create_file(directory, 26 * part_size)
            self.api.upload_file_to_oss("wip.dm.prod", "model.rvt", source)

        self.assertEqual(self.api.get_signed_s3_upload.call_count, 2)
        self.api.get_signed_s3_upload.assert_any_call(
            "wip.dm.prod",
            "model.rvt",
            parts=25,
            first_part=1,
            upload_key=None,
            minutes_expiration=None,
            use_acceleration=None,
        )
        self.api.get_signed_s3_upload.assert_any_call(
            "wip.dm.prod",
            "model.rvt",
            parts=1,
            first_part=26,
            upload_key="upload-key",
            minutes_expiration=None,
            use_acceleration=None,
        )

    def test_refreshes_expired_part_url_with_bounded_attempt(self):
        expired_response = MagicMock(status_code=403)
        expired_error = requests.HTTPError(response=expired_response)
        self.api.get_signed_s3_upload.side_effect = [
            {"uploadKey": "upload-key", "urls": ["https://example.test/expired"]},
            {"uploadKey": "upload-key", "urls": ["https://example.test/refreshed"]},
        ]
        self.api.upload_file_part.side_effect = [expired_error, '"etag"']
        self.api.complete_signed_s3_upload.return_value = {"size": 3}

        with TemporaryDirectory() as directory:
            source = self.create_file(directory, 3)
            result = self.api.upload_file_to_oss(
                "wip.dm.prod",
                "model.rvt",
                source,
                max_url_refreshes=1,
            )

        self.assertEqual(result, {"size": 3})
        self.api.get_signed_s3_upload.assert_called_with(
            "wip.dm.prod",
            "model.rvt",
            parts=1,
            first_part=1,
            upload_key="upload-key",
            minutes_expiration=None,
            use_acceleration=None,
        )
        self.assertEqual(self.api.upload_file_part.call_count, 2)

    def test_rejects_oversized_file_and_small_multipart_parts_before_request(self):
        with TemporaryDirectory() as directory:
            source = self.create_file(directory, 2)

            with self.assertRaisesRegex(ValueError, "exceeds max_bytes"):
                self.api.upload_file_to_oss(
                    "wip.dm.prod", "model.rvt", source, max_bytes=1
                )
            with self.assertRaisesRegex(ValueError, "at least 5 MiB"):
                self.api.upload_file_to_oss(
                    "wip.dm.prod", "model.rvt", source, part_size=1
                )

        self.api.get_signed_s3_upload.assert_not_called()

    def test_rejects_invalid_session_and_completion_validation_error(self):
        with TemporaryDirectory() as directory:
            source = self.create_file(directory, 3)
            self.api.get_signed_s3_upload.return_value = {
                "uploadKey": "upload-key",
                "urls": [],
            }

            with self.assertRaisesRegex(RuntimeError, "expected 1"):
                self.api.upload_file_to_oss(
                    "wip.dm.prod", "model.rvt", source
                )

            self.api.get_signed_s3_upload.return_value = {
                "uploadKey": "upload-key",
                "urls": ["https://example.test/part-one"],
            }
            self.api.upload_file_part.return_value = None
            self.api.complete_signed_s3_upload.return_value = {
                "status": "error",
                "reason": "size mismatch",
            }

            with self.assertRaisesRegex(RuntimeError, "size mismatch"):
                self.api.upload_file_to_oss(
                    "wip.dm.prod", "model.rvt", source
                )


if __name__ == "__main__":
    unittest.main()
