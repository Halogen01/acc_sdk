import unittest
from unittest.mock import MagicMock

from acc_sdk.base import AccBase
from acc_sdk.data_management import AccDataManagementApi
from acc_sdk.transport import HttpTransport


class TestCreateStorageLocation(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.get_private_token.return_value = "private-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccDataManagementApi(self.base)

    def response(self, payload):
        response = MagicMock()
        response.json.return_value = payload
        self.base.transport.post.return_value = response
        return response

    def test_creates_folder_storage_with_normalized_project_id(self):
        response = self.response(
            {
                "jsonapi": {"version": "1.0"},
                "data": {
                    "type": "objects",
                    "id": "urn:adsk.objects:os.object:wip.dm.prod/model.rvt",
                },
            }
        )

        result = self.api.create_storage_location(
            "project-id",
            "urn:adsk.wipprod:fs.folder:co.folder-id",
            "model.rvt",
        )

        self.assertEqual(result["type"], "objects")
        response.raise_for_status.assert_called_once_with()
        self.base.transport.post.assert_called_once_with(
            "https://developer.api.autodesk.com/data/v1/projects/"
            "b.project-id/storage",
            headers={
                "Authorization": "Bearer private-token",
                "Content-Type": "application/vnd.api+json",
            },
            json={
                "jsonapi": {"version": "1.0"},
                "data": {
                    "type": "objects",
                    "attributes": {"name": "model.rvt"},
                    "relationships": {
                        "target": {
                            "data": {
                                "type": "folders",
                                "id": "urn:adsk.wipprod:fs.folder:co.folder-id",
                            }
                        }
                    },
                },
            },
        )

    def test_supports_item_target_and_user_context(self):
        self.response(
            {
                "data": {
                    "type": "objects",
                    "id": "urn:adsk.objects:os.object:wip.dm.prod/model.rvt",
                }
            }
        )

        self.api.create_storage_location(
            "b.project-id",
            "urn:adsk.wipprod:dm.lineage:item-id",
            "model.rvt",
            target_type="items",
            user_id="user-id",
        )

        call = self.base.transport.post.call_args
        self.assertEqual(call.kwargs["headers"]["x-user-id"], "user-id")
        target = call.kwargs["json"]["data"]["relationships"]["target"]
        self.assertEqual(target["data"]["type"], "items")

    def test_rejects_invalid_arguments_before_authentication_or_request(self):
        invalid_calls = [
            (None, "folder-id", "model.rvt", "folders", None),
            ("project-id", "", "model.rvt", "folders", None),
            ("project-id", "folder-id", "", "folders", None),
            ("project-id", "folder-id", "bad/name.rvt", "folders", None),
            ("project-id", "folder-id", "model.rvt", "projects", None),
            ("project-id", "folder-id", "model.rvt", "folders", ""),
        ]

        for arguments in invalid_calls:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    self.api.create_storage_location(*arguments)

        self.base.get_private_token.assert_not_called()
        self.base.transport.post.assert_not_called()

    def test_rejects_overlong_file_name(self):
        with self.assertRaisesRegex(ValueError, "cannot exceed 255"):
            self.api.create_storage_location(
                "project-id", "folder-id", "a" * 256
            )

    def test_rejects_response_without_storage_id(self):
        self.response({"jsonapi": {"version": "1.0"}, "data": {}})

        with self.assertRaisesRegex(RuntimeError, "storage resource ID"):
            self.api.create_storage_location(
                "project-id", "folder-id", "model.rvt"
            )

    def test_does_not_retry_post_at_api_layer(self):
        self.response(
            {
                "data": {
                    "type": "objects",
                    "id": "urn:adsk.objects:os.object:wip.dm.prod/model.rvt",
                }
            }
        )

        self.api.create_storage_location(
            "project-id", "folder-id", "model.rvt"
        )

        self.base.transport.post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
