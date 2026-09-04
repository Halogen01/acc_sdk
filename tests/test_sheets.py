import unittest
from unittest.mock import MagicMock

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


if __name__ == "__main__":
    unittest.main()
