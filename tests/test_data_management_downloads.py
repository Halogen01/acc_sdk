import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
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


class TestSignedUrlStreaming(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccDataManagementApi(self.base)

    def response(self, chunks, content_length=None):
        response = MagicMock()
        response.headers = {}
        if content_length is not None:
            response.headers["Content-Length"] = str(content_length)
        response.iter_content.return_value = chunks
        return response

    def test_streams_to_file_with_bounded_chunks_and_skips_empty_chunks(self):
        response = self.response([b"first", b"", b"second"], content_length=11)
        self.base.transport.get.return_value = response

        with TemporaryDirectory() as directory:
            destination = Path(directory) / "model.rvt"

            result = self.api.download_from_signed_url(
                "https://example.s3.amazonaws.com/signed-object",
                destination,
                chunk_size=4096,
                max_bytes=20,
            )

            self.assertEqual(result, str(destination))
            self.assertEqual(destination.read_bytes(), b"firstsecond")
            self.assertEqual(list(destination.parent.glob("*.part")), [])

        self.base.transport.get.assert_called_once_with(
            "https://example.s3.amazonaws.com/signed-object", stream=True
        )
        response.raise_for_status.assert_called_once_with()
        response.iter_content.assert_called_once_with(chunk_size=4096)
        response.close.assert_called_once_with()

    def test_stream_failure_keeps_existing_destination_and_removes_partial_file(self):
        response = self.response([b"1234", b"5678"])
        self.base.transport.get.return_value = response

        with TemporaryDirectory() as directory:
            destination = Path(directory) / "model.rvt"
            destination.write_bytes(b"existing")

            with self.assertRaisesRegex(ValueError, "exceeds max_bytes"):
                self.api.download_from_signed_url(
                    "https://example.s3.amazonaws.com/signed-object",
                    destination,
                    max_bytes=6,
                )

            self.assertEqual(destination.read_bytes(), b"existing")
            self.assertEqual(list(destination.parent.glob("*.part")), [])

        response.close.assert_called_once_with()

    def test_content_length_over_limit_fails_before_creating_a_file(self):
        response = self.response([], content_length=100)
        self.base.transport.get.return_value = response

        with TemporaryDirectory() as directory:
            destination = Path(directory) / "model.rvt"

            with self.assertRaisesRegex(ValueError, "exceeds max_bytes"):
                self.api.download_from_signed_url(
                    "https://example.s3.amazonaws.com/signed-object",
                    destination,
                    max_bytes=99,
                )

            self.assertFalse(destination.exists())
            self.assertEqual(list(destination.parent.glob("*.part")), [])

        response.iter_content.assert_not_called()
        response.close.assert_called_once_with()

    def test_rejects_invalid_limits_before_request(self):
        invalid_arguments = [
            {"chunk_size": True},
            {"chunk_size": 0},
            {"chunk_size": self.api.MAX_DOWNLOAD_CHUNK_SIZE + 1},
            {"max_bytes": True},
            {"max_bytes": 0},
        ]

        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.api.download_from_signed_url(
                    "https://example.s3.amazonaws.com/signed-object",
                    "model.rvt",
                    **arguments,
                )

        self.base.transport.get.assert_not_called()


class TestVersionDownloadWorkflow(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.api = AccDataManagementApi(self.base)
        self.api.get_version = MagicMock()
        self.api.get_signed_s3_download = MagicMock()
        self.api.download_from_signed_url = MagicMock(return_value="saved/model.rvt")

    def test_resolves_version_storage_and_streams_single_url(self):
        self.api.get_version.return_value = {
            "relationships": {
                "storage": {
                    "data": {
                        "type": "objects",
                        "id": "urn:adsk.objects:os.object:wip.dm.prod/folder/model.rvt",
                    }
                }
            }
        }
        self.api.get_signed_s3_download.return_value = {
            "status": "complete",
            "url": "https://example.s3.amazonaws.com/signed-object",
            "size": 123,
        }

        result = self.api.download_version(
            "project-id",
            "version-id",
            "saved/model.rvt",
            user_id="user-id",
            minutes_expiration=5,
            use_cdn=True,
            chunk_size=4096,
            max_bytes=200,
        )

        self.assertEqual(result, "saved/model.rvt")
        self.api.get_version.assert_called_once_with(
            "project-id", "version-id", user_id="user-id"
        )
        self.api.get_signed_s3_download.assert_called_once_with(
            "wip.dm.prod",
            "folder/model.rvt",
            minutes_expiration=5,
            use_cdn=True,
            public_resource_fallback=True,
        )
        self.api.download_from_signed_url.assert_called_once_with(
            "https://example.s3.amazonaws.com/signed-object",
            "saved/model.rvt",
            chunk_size=4096,
            max_bytes=200,
        )

    def test_rejects_version_without_storage_relationship(self):
        self.api.get_version.return_value = {"relationships": {}}

        with self.assertRaisesRegex(ValueError, "storage relationship"):
            self.api.download_version("project-id", "version-id", "model.rvt")

        self.api.get_signed_s3_download.assert_not_called()
        self.api.download_from_signed_url.assert_not_called()

    def test_rejects_chunked_response_when_single_url_is_unavailable(self):
        self.api.get_version.return_value = {
            "relationships": {
                "storage": {
                    "data": {
                        "id": "urn:adsk.objects:os.object:wip.dm.prod/model.rvt"
                    }
                }
            }
        }
        self.api.get_signed_s3_download.return_value = {
            "status": "chunked",
            "urls": {"0-9": "https://example.s3.amazonaws.com/part-one"},
            "size": 10,
        }

        with self.assertRaisesRegex(RuntimeError, "download status: chunked"):
            self.api.download_version("project-id", "version-id", "model.rvt")

        self.api.download_from_signed_url.assert_not_called()

    def test_rejects_signed_metadata_over_size_limit_before_streaming(self):
        self.api.get_version.return_value = {
            "relationships": {
                "storage": {
                    "data": {
                        "id": "urn:adsk.objects:os.object:wip.dm.prod/model.rvt"
                    }
                }
            }
        }
        self.api.get_signed_s3_download.return_value = {
            "status": "complete",
            "url": "https://example.s3.amazonaws.com/signed-object",
            "size": 101,
        }

        with self.assertRaisesRegex(ValueError, "exceeds max_bytes"):
            self.api.download_version(
                "project-id", "version-id", "model.rvt", max_bytes=100
            )

        self.api.download_from_signed_url.assert_not_called()

    def test_rejects_invalid_limits_before_version_lookup(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            self.api.download_version(
                "project-id", "version-id", "model.rvt", max_bytes=0
            )

        self.api.get_version.assert_not_called()


if __name__ == "__main__":
    unittest.main()
