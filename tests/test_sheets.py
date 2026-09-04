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


class TestAccSheetsOperations(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.get_private_token.return_value = "private-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccSheetsApi(self.base)
        self.headers = {"Authorization": "Bearer private-token"}
        self.json_headers = {
            **self.headers,
            "Content-Type": "application/json",
        }

    def response(self, status_code=200, payload=None):
        response = MagicMock(status_code=status_code)
        response.json.return_value = payload
        return response

    def test_get_sheets_preserves_pagination_and_query(self):
        first = self.response(
            payload={
                "results": [{"id": "one"}],
                "pagination": {"next": "https://example.com/next"},
            }
        )
        second = self.response(
            payload={"results": [{"id": "two"}], "pagination": {}}
        )
        self.base.transport.get.side_effect = [first, second]

        result = self.api.get_sheets(
            "project-id",
            user_id="user-id",
            query_params={"limit": 50},
            follow_pagination=True,
        )

        self.assertEqual(result, [{"id": "one"}, {"id": "two"}])
        headers = {**self.headers, "x-user-id": "user-id"}
        self.base.transport.get.assert_any_call(
            f"{self.api.base_url}/projects/project-id/sheets",
            headers=headers,
            params={"limit": 50},
        )
        self.base.transport.get.assert_any_call(
            "https://example.com/next", headers=headers, params=None
        )

    def test_batch_get_sheets(self):
        self.base.transport.post.return_value = self.response(
            payload={"results": [{"id": "sheet-id"}]}
        )

        result = self.api.batch_get_sheets("project-id", ["sheet-id"])

        self.assertEqual(result, [{"id": "sheet-id"}])
        self.base.transport.post.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/sheets:batch-get",
            headers=self.json_headers,
            json={"ids": ["sheet-id"]},
        )

    def test_batch_get_sheets_rejects_more_than_200_ids(self):
        with self.assertRaisesRegex(ValueError, "maximum number.*200"):
            self.api.batch_get_sheets("project-id", ["sheet-id"] * 201)

        self.base.transport.post.assert_not_called()

    def test_batch_update_sheets(self):
        self.base.transport.post.return_value = self.response(
            payload={"results": [{"id": "sheet-id", "title": "Updated"}]}
        )

        result = self.api.batch_update_sheets(
            "project-id", ["sheet-id"], {"title": "Updated"}, user_id="user-id"
        )

        self.assertEqual(result[0]["title"], "Updated")
        self.base.transport.post.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/sheets:batch-update",
            headers={**self.json_headers, "x-user-id": "user-id"},
            json={"ids": ["sheet-id"], "updates": {"title": "Updated"}},
        )

    def test_batch_delete_sheets(self):
        self.base.transport.post.return_value = self.response()

        result = self.api.batch_delete_sheets("project-id", ["sheet-id"])

        self.assertIsNone(result)
        self.base.transport.post.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/sheets:batch-delete",
            headers=self.json_headers,
            json={"ids": ["sheet-id"]},
        )

    def test_batch_restore_sheets(self):
        self.base.transport.post.return_value = self.response()

        result = self.api.batch_restore_sheets("project-id", ["sheet-id"])

        self.assertIsNone(result)
        self.base.transport.post.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/sheets:batch-restore",
            headers=self.json_headers,
            json={"ids": ["sheet-id"]},
        )

    def test_export_sheets(self):
        payload = {"id": "export-id", "status": "pending"}
        self.base.transport.post.return_value = self.response(202, payload)
        options = {"outputFileName": "sheets.pdf"}

        result = self.api.export_sheets(
            "project-id", options, ["sheet-id"], user_id="user-id"
        )

        self.assertEqual(result, payload)
        self.base.transport.post.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/exports",
            json={"options": options, "sheets": ["sheet-id"]},
            headers={**self.json_headers, "x-user-id": "user-id"},
        )

    def test_export_sheets_rejects_more_than_1000_sheets(self):
        with self.assertRaisesRegex(ValueError, "maximum number.*1000"):
            self.api.export_sheets("project-id", {}, ["sheet-id"] * 1001)

        self.base.transport.post.assert_not_called()

    def test_get_export_status(self):
        payload = {"id": "export-id", "status": "complete"}
        self.base.transport.get.return_value = self.response(200, payload)

        result = self.api.get_export_status("project-id", "export-id")

        self.assertEqual(result, payload)
        self.base.transport.get.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/exports/export-id",
            headers=self.json_headers,
        )

    def test_get_collections_follows_pagination(self):
        first = self.response(
            payload={
                "results": [{"id": "one"}],
                "pagination": {"nextUrl": "https://example.com/next"},
            }
        )
        second = self.response(
            payload={"results": [{"id": "two"}], "pagination": {}}
        )
        self.base.transport.get.side_effect = [first, second]

        result = self.api.get_collections("project-id", follow_pagination=True)

        self.assertEqual(result, [{"id": "one"}, {"id": "two"}])
        self.base.transport.get.assert_any_call(
            f"{self.api.base_url}/projects/project-id/collections",
            headers=self.headers,
            params={},
        )
        self.base.transport.get.assert_any_call(
            "https://example.com/next", headers=self.headers
        )

    def test_get_collection(self):
        payload = {"id": "collection-id"}
        self.base.transport.get.return_value = self.response(200, payload)

        result = self.api.get_collection("project-id", "collection-id")

        self.assertEqual(result, payload)
        self.base.transport.get.assert_called_once_with(
            f"{self.api.base_url}/projects/project-id/collections/collection-id",
            headers=self.headers,
        )


if __name__ == "__main__":
    unittest.main()
