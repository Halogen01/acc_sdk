import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
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


class TestCreateFileResources(unittest.TestCase):
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

    def test_creates_acc_file_item_and_first_version(self):
        document = {
            "data": {"type": "items", "id": "item-id"},
            "included": [{"type": "versions", "id": "version-id"}],
        }
        response = self.response(document)

        result = self.api.create_file_item(
            "project-id",
            "folder-id",
            "model.rvt",
            "urn:adsk.objects:os.object:wip.dm.prod/model.rvt",
            user_id="user-id",
        )

        self.assertIs(result, document)
        response.raise_for_status.assert_called_once_with()
        self.base.transport.post.assert_called_once_with(
            "https://developer.api.autodesk.com/data/v1/projects/"
            "b.project-id/items",
            headers={
                "Authorization": "Bearer private-token",
                "Content-Type": "application/vnd.api+json",
                "x-user-id": "user-id",
            },
            json={
                "jsonapi": {"version": "1.0"},
                "data": {
                    "type": "items",
                    "attributes": {
                        "displayName": "model.rvt",
                        "extension": {
                            "type": "items:autodesk.bim360:File",
                            "version": "1.0",
                        },
                    },
                    "relationships": {
                        "tip": {
                            "data": {"type": "versions", "id": "1"}
                        },
                        "parent": {
                            "data": {"type": "folders", "id": "folder-id"}
                        },
                    },
                },
                "included": [
                    {
                        "type": "versions",
                        "id": "1",
                        "attributes": {
                            "name": "model.rvt",
                            "extension": {
                                "type": "versions:autodesk.bim360:File",
                                "version": "1.0",
                            },
                        },
                        "relationships": {
                            "storage": {
                                "data": {
                                    "type": "objects",
                                    "id": "urn:adsk.objects:os.object:"
                                    "wip.dm.prod/model.rvt",
                                }
                            }
                        },
                    }
                ],
            },
        )

    def test_file_item_allows_service_specific_extensions(self):
        self.response({"data": {"type": "items", "id": "item-id"}})

        self.api.create_file_item(
            "project-id",
            "folder-id",
            "model.dwg",
            "storage-urn",
            item_extension_type="items:autodesk.core:File",
            version_extension_type="versions:autodesk.core:File",
            extension_schema_version="2.0",
        )

        payload = self.base.transport.post.call_args.kwargs["json"]
        self.assertEqual(
            payload["data"]["attributes"]["extension"],
            {"type": "items:autodesk.core:File", "version": "2.0"},
        )
        self.assertEqual(
            payload["included"][0]["attributes"]["extension"],
            {"type": "versions:autodesk.core:File", "version": "2.0"},
        )

    def test_creates_acc_file_version_without_caller_version_number(self):
        document = {"data": {"type": "versions", "id": "version-id"}}
        response = self.response(document)

        result = self.api.create_file_version(
            "b.project-id",
            "item-id",
            "model.rvt",
            "urn:adsk.objects:os.object:wip.dm.prod/model.rvt",
        )

        self.assertIs(result, document)
        response.raise_for_status.assert_called_once_with()
        self.base.transport.post.assert_called_once_with(
            "https://developer.api.autodesk.com/data/v1/projects/"
            "b.project-id/versions",
            headers={
                "Authorization": "Bearer private-token",
                "Content-Type": "application/vnd.api+json",
            },
            json={
                "jsonapi": {"version": "1.0"},
                "data": {
                    "type": "versions",
                    "attributes": {
                        "name": "model.rvt",
                        "extension": {
                            "type": "versions:autodesk.bim360:File",
                            "version": "1.0",
                        },
                    },
                    "relationships": {
                        "item": {
                            "data": {"type": "items", "id": "item-id"}
                        },
                        "storage": {
                            "data": {
                                "type": "objects",
                                "id": "urn:adsk.objects:os.object:"
                                "wip.dm.prod/model.rvt",
                            }
                        },
                    },
                },
            },
        )

    def test_item_rejects_invalid_arguments_before_request(self):
        valid = ("project-id", "folder-id", "model.rvt", "storage-urn")
        invalid_calls = [
            (None, *valid[1:]),
            (valid[0], "", *valid[2:]),
            (*valid[:2], "bad/name.rvt", valid[3]),
            (*valid[:3], ""),
        ]

        for arguments in invalid_calls:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    self.api.create_file_item(*arguments)

        with self.assertRaises(ValueError):
            self.api.create_file_item(
                *valid, item_extension_type="versions:autodesk.core:File"
            )
        with self.assertRaises(ValueError):
            self.api.create_file_item(
                *valid, version_extension_type="items:autodesk.core:File"
            )
        with self.assertRaises(ValueError):
            self.api.create_file_item(*valid, extension_schema_version="")
        with self.assertRaises(ValueError):
            self.api.create_file_item(*valid, user_id="")

        self.base.get_private_token.assert_not_called()
        self.base.transport.post.assert_not_called()

    def test_version_rejects_invalid_arguments_before_request(self):
        invalid_calls = [
            ("project-id", "", "model.rvt", "storage-urn"),
            ("project-id", "item-id", "bad*.rvt", "storage-urn"),
            ("project-id", "item-id", "model.rvt", ""),
        ]

        for arguments in invalid_calls:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    self.api.create_file_version(*arguments)

        with self.assertRaises(ValueError):
            self.api.create_file_version(
                "project-id",
                "item-id",
                "model.rvt",
                "storage-urn",
                version_extension_type="items:autodesk.core:File",
            )

        self.base.get_private_token.assert_not_called()
        self.base.transport.post.assert_not_called()

    def test_rejects_item_or_version_response_without_resource_id(self):
        self.response({"data": {"type": "items"}})
        with self.assertRaisesRegex(RuntimeError, "item resource ID"):
            self.api.create_file_item(
                "project-id", "folder-id", "model.rvt", "storage-urn"
            )

        self.response({"data": {"type": "versions"}})
        with self.assertRaisesRegex(RuntimeError, "version resource ID"):
            self.api.create_file_version(
                "project-id", "item-id", "model.rvt", "storage-urn"
            )

        self.assertEqual(self.base.transport.post.call_count, 2)


class TestUploadFileWriteWorkflows(unittest.TestCase):
    STORAGE = {
        "type": "objects",
        "id": "urn:adsk.objects:os.object:wip.dm.prod/folder/model.rvt",
    }

    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccDataManagementApi(self.base)
        self.api.create_storage_location = MagicMock(return_value=self.STORAGE)
        self.api.upload_file_to_oss = MagicMock(
            return_value={"objectId": self.STORAGE["id"], "size": 4}
        )
        self.api.create_file_item = MagicMock(
            return_value={"data": {"type": "items", "id": "item-id"}}
        )
        self.api.create_file_version = MagicMock(
            return_value={
                "data": {"type": "versions", "id": "version-id"}
            }
        )

    def source_file(self, directory, name="model.rvt"):
        source = Path(directory) / name
        source.write_bytes(b"data")
        return source

    def test_uploads_new_item_in_storage_then_creates_item(self):
        with TemporaryDirectory() as directory:
            source = self.source_file(directory)

            result = self.api.upload_new_file_item(
                "project-id",
                "folder-id",
                source,
                user_id="user-id",
                part_size=123,
                max_bytes=100,
                minutes_expiration=10,
                use_acceleration=False,
                max_retries=1,
                max_url_refreshes=1,
            )

        self.assertEqual(
            result,
            {
                "storage": self.STORAGE,
                "upload": {"objectId": self.STORAGE["id"], "size": 4},
                "item": {"data": {"type": "items", "id": "item-id"}},
            },
        )
        self.api.create_storage_location.assert_called_once_with(
            "b.project-id", "folder-id", "model.rvt", user_id="user-id"
        )
        self.api.upload_file_to_oss.assert_called_once_with(
            "wip.dm.prod",
            "folder/model.rvt",
            source,
            part_size=123,
            max_bytes=100,
            minutes_expiration=10,
            use_acceleration=False,
            max_retries=1,
            max_url_refreshes=1,
        )
        self.api.create_file_item.assert_called_once_with(
            "b.project-id",
            "folder-id",
            "model.rvt",
            self.STORAGE["id"],
            user_id="user-id",
            item_extension_type="items:autodesk.bim360:File",
            version_extension_type="versions:autodesk.bim360:File",
            extension_schema_version="1.0",
        )

    def test_uploads_new_version_to_item_storage(self):
        with TemporaryDirectory() as directory:
            source = self.source_file(directory, "local-name.rvt")

            result = self.api.upload_new_file_version(
                "b.project-id",
                "item-id",
                source,
                file_name="published-name.rvt",
                version_extension_type="versions:autodesk.core:File",
                extension_schema_version="2.0",
            )

        self.assertEqual(result["version"]["data"]["id"], "version-id")
        self.api.create_storage_location.assert_called_once_with(
            "b.project-id",
            "item-id",
            "published-name.rvt",
            target_type="items",
            user_id=None,
        )
        self.api.upload_file_to_oss.assert_called_once_with(
            "wip.dm.prod",
            "folder/model.rvt",
            source,
            part_size=self.api.DEFAULT_UPLOAD_PART_SIZE,
            max_bytes=None,
            minutes_expiration=None,
            use_acceleration=None,
            max_retries=2,
            max_url_refreshes=2,
        )
        self.api.create_file_version.assert_called_once_with(
            "b.project-id",
            "item-id",
            "published-name.rvt",
            self.STORAGE["id"],
            user_id=None,
            version_extension_type="versions:autodesk.core:File",
            extension_schema_version="2.0",
        )

    def test_upload_failure_stops_before_item_creation(self):
        self.api.upload_file_to_oss.side_effect = RuntimeError("upload failed")
        with TemporaryDirectory() as directory:
            source = self.source_file(directory)

            with self.assertRaisesRegex(RuntimeError, "upload failed"):
                self.api.upload_new_file_item(
                    "project-id", "folder-id", source
                )

        self.api.create_storage_location.assert_called_once()
        self.api.create_file_item.assert_not_called()

    def test_invalid_inputs_never_create_remote_storage(self):
        with TemporaryDirectory() as directory:
            source = self.source_file(directory)
            missing = Path(directory) / "missing.rvt"
            invalid_calls = [
                {"source_path": missing},
                {"source_path": source, "max_bytes": 1},
                {"source_path": source, "part_size": 0},
                {"source_path": source, "minutes_expiration": 61},
                {"source_path": source, "file_name": "bad/name.rvt"},
                {"source_path": source, "user_id": ""},
                {
                    "source_path": source,
                    "item_extension_type": "versions:autodesk.core:File",
                },
            ]

            for arguments in invalid_calls:
                with self.subTest(arguments=arguments):
                    with self.assertRaises(ValueError):
                        self.api.upload_new_file_item(
                            "project-id", "folder-id", **arguments
                        )

        self.api.create_storage_location.assert_not_called()
        self.api.upload_file_to_oss.assert_not_called()
        self.api.create_file_item.assert_not_called()


if __name__ == "__main__":
    unittest.main()
