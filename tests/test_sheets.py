import unittest
from unittest.mock import MagicMock, mock_open, patch

from acc_sdk.base import AccBase
from acc_sdk.sheets import AccSheetsApi
from acc_sdk.transport import HttpTransport


class TestAccSheetsVersionSets(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.get_private_token.return_value = "private-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccSheetsApi(self.base)
        self.json_headers = {
            "Authorization": "Bearer private-token",
            "Content-Type": "application/json",
        }

    def response(self, status_code, payload=None):
        response = MagicMock(status_code=status_code)
        response.json.return_value = payload
        return response

    def test_create_version_set(self):
        payload = {"id": "version-set-id"}
        self.base.transport.post.return_value = self.response(201, payload)

        result = self.api.create_version_set("project-id", "2026-09-04", "Issued")

        self.assertEqual(result, payload)
        self.base.transport.post.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/version-sets",
            headers=self.json_headers,
            json={"name": "Issued", "issuanceDate": "2026-09-04T00:00:00.000Z"},
        )

    def test_get_version_sets_uses_supported_query_keyword(self):
        self.base.transport.get.return_value = self.response(
            200, {"results": [{"id": "version-set-id"}]}
        )

        result = self.api.get_version_sets("project-id", {"limit": 10})

        self.assertEqual(result, [{"id": "version-set-id"}])
        self.base.transport.get.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/version-sets",
            headers={"Authorization": "Bearer private-token"},
            params={"limit": 10},
        )

    def test_patch_version_set(self):
        self.base.transport.patch.return_value = self.response(200)

        result = self.api.patch_version_set(
            "project-id", "version-set-id", "2026-09-04", "Issued"
        )

        self.assertIsNone(result)
        self.base.transport.patch.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/version-sets/version-set-id",
            headers=self.json_headers,
            json={"name": "Issued", "issuanceDate": "2026-09-04T00:00:00.000Z"},
        )

    def test_batch_get_version_sets(self):
        self.base.transport.post.return_value = self.response(
            200, {"results": [{"id": "one"}, {"id": "two"}]}
        )

        result = self.api.batch_get_version_sets("project-id", ["one", "two"])

        self.assertEqual(result, [{"id": "one"}, {"id": "two"}])
        self.base.transport.post.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/version-sets:batch-get",
            headers=self.json_headers,
            json={"ids": ["one", "two"]},
        )

    def test_delete_version_set(self):
        self.base.transport.delete.return_value = self.response(204)

        result = self.api.delete_version_set("project-id", "version-set-id")

        self.assertIsNone(result)
        self.base.transport.delete.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/version-sets/version-set-id",
            headers={"Authorization": "Bearer private-token"},
        )

    def test_batch_delete_version_sets(self):
        self.base.transport.post.return_value = self.response(204)

        result = self.api.batch_delete_version_sets("project-id", ["one", "two"])

        self.assertIsNone(result)
        self.base.transport.post.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/version-sets:batch-delete",
            headers=self.json_headers,
            json={"ids": ["one", "two"]},
        )


class TestAccSheetsUploads(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.get_private_token.return_value = "private-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccSheetsApi(self.base)
        self.json_headers = {
            "Authorization": "Bearer private-token",
            "Content-Type": "application/json",
        }

    def response(self, status_code, payload=None):
        response = MagicMock(status_code=status_code)
        response.json.return_value = payload
        return response

    def test_upload_file_to_autodesk_returns_storage_keys(self):
        self.base.transport.post.return_value = self.response(
            201, {"urn": "urn:adsk.objects:os.object:bucket-key/folder/sheet.pdf"}
        )

        result = self.api.upload_file_to_autodesk("project-id", "sheet.pdf")

        self.assertEqual(result, ("bucket-key", "folder/sheet.pdf"))
        self.base.transport.post.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/storage",
            headers=self.json_headers,
            json={"fileName": "sheet.pdf"},
        )

    def test_get_signed_s3_upload_encodes_object_key(self):
        payload = {"urls": ["https://example.com/signed-upload"]}
        self.base.transport.get.return_value = self.response(200, payload)

        result = self.api.get_signed_s3_upload("bucket-key", "folder/sheet 1.pdf")

        self.assertEqual(result, payload)
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/oss/v2/buckets/bucket-key/objects/folder%2Fsheet%201.pdf/signeds3upload",
            headers={"Authorization": "Bearer private-token"},
        )

    @patch("acc_sdk.sheets.os.path.isfile", return_value=True)
    @patch("acc_sdk.sheets.open", new_callable=mock_open, read_data=b"pdf")
    def test_upload_pdf_to_signed_url_uses_shared_transport(
        self, file_open, _is_file
    ):
        self.base.transport.put.return_value = self.response(200)

        result = self.api.upload_pdf_to_signed_url(
            "https://example.com/signed-upload", "sheet.pdf"
        )

        self.assertEqual(result, 200)
        self.base.transport.put.assert_called_once_with(
            "https://example.com/signed-upload", data=file_open()
        )

    def test_complete_s3_upload_encodes_object_key(self):
        payload = {"status": "complete"}
        self.base.transport.post.return_value = self.response(200, payload)

        result = self.api.complete_s3_upload(
            "bucket-key", "folder/sheet 1.pdf", "upload-key"
        )

        self.assertEqual(result, payload)
        self.base.transport.post.assert_called_once_with(
            "https://developer.api.autodesk.com/oss/v2/buckets/bucket-key/objects/folder%2Fsheet%201.pdf/signeds3upload",
            headers=self.json_headers,
            json={"uploadKey": "upload-key"},
        )

    def test_post_uploads_preserves_payload(self):
        files = [
            {
                "storageType": "OSS",
                "storageUrn": "urn:adsk.objects:os.object:bucket/sheet.pdf",
                "name": "sheet.pdf",
            }
        ]
        payload = {"id": "upload-id"}
        self.base.transport.post.return_value = self.response(201, payload)

        result = self.api.post_uploads("project-id", "version-set-id", files)

        self.assertEqual(result, payload)
        self.base.transport.post.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/uploads",
            headers=self.json_headers,
            json={"versionSetId": "version-set-id", "files": files},
        )


if __name__ == "__main__":
    unittest.main()
