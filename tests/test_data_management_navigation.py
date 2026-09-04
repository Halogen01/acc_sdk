import unittest
from copy import deepcopy
from unittest.mock import MagicMock

from acc_sdk.base import AccBase
from acc_sdk.data_management import AccDataManagementApi
from acc_sdk.regions import ApsRegion
from acc_sdk.transport import HttpTransport


class TestDataManagementHubProjectNavigation(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.get_private_token.return_value = "private-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccDataManagementApi(self.base)
        self.headers = {"Authorization": "Bearer private-token"}

    def response(self, payload, status_code=200):
        response = MagicMock(status_code=status_code)
        response.json.return_value = payload
        return response

    def test_get_hubs_uses_valid_authorization_header_and_filters(self):
        self.base.transport.get.return_value = self.response(
            {"data": [{"id": "b.hub-id"}]}
        )

        result = self.api.get_hubs(
            user_id="user-id", filter_name=["Account"], filter_id=["b.hub-id"]
        )

        self.assertEqual(result, [{"id": "b.hub-id"}])
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/project/v1/hubs",
            headers={**self.headers, "x-user-id": "user-id"},
            params={"filter[id]": ["b.hub-id"], "filter[name]": ["Account"]},
        )

    def test_get_hub_normalizes_id_before_building_url(self):
        payload = {"id": "b.hub-id"}
        self.base.transport.get.return_value = self.response({"data": payload})

        result = self.api.get_hub("hub-id")

        self.assertEqual(result, payload)
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/project/v1/hubs/b.hub-id",
            headers=self.headers,
        )

    def test_get_projects_follows_relative_pagination_link(self):
        first = self.response(
            {
                "data": [{"id": "b.project-one"}],
                "links": {
                    "next": {
                        "href": "/project/v1/hubs/b.hub-id/projects?page[number]=2"
                    }
                },
            }
        )
        second = self.response({"data": [{"id": "b.project-two"}], "links": {}})
        self.base.transport.get.side_effect = [first, second]

        result = self.api.get_projects(
            "hub-id", follow_pagination=True, query_params={"page[number]": 1}
        )

        self.assertEqual(
            result, [{"id": "b.project-one"}, {"id": "b.project-two"}]
        )
        self.base.transport.get.assert_any_call(
            "https://developer.api.autodesk.com/project/v1/hubs/b.hub-id/projects",
            headers=self.headers,
            params={"page[number]": 1},
        )
        self.base.transport.get.assert_any_call(
            "https://developer.api.autodesk.com/project/v1/hubs/b.hub-id/projects?page[number]=2",
            headers=self.headers,
            params={},
        )

    def test_get_project_uses_normalized_path(self):
        payload = {"id": "b.project-id"}
        self.base.transport.get.return_value = self.response({"data": payload})

        result = self.api.get_project("hub-id", "project-id")

        self.assertEqual(result, payload)
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/project/v1/hubs/b.hub-id/projects/b.project-id",
            headers=self.headers,
        )

    def test_get_hub_from_project_uses_normalized_path(self):
        payload = {"id": "b.hub-id"}
        self.base.transport.get.return_value = self.response({"data": payload})

        result = self.api.get_hub_from_project("hub-id", "project-id")

        self.assertEqual(result, payload)
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/project/v1/hubs/b.hub-id/projects/b.project-id/hub",
            headers=self.headers,
        )

    def test_get_hub_region_prefers_explicit_us_metadata(self):
        hub = {"id": "b.hub-id", "attributes": {"region": "US"}}

        self.assertIs(self.api.get_hub_region(hub), ApsRegion.US)

    def test_get_hub_region_supports_current_non_us_metadata(self):
        for value, expected in (
            ("AUS", ApsRegion.AUS),
            ("emea", ApsRegion.EMEA),
            ("GBR", ApsRegion.GBR),
        ):
            with self.subTest(value=value):
                hub = {"attributes": {"region": value}}
                self.assertIs(self.api.get_hub_region(hub), expected)

    def test_get_hub_region_defaults_missing_metadata_to_us_without_mutation(self):
        hub = {"id": "b.hub-id", "attributes": {"name": "US Account"}}
        original = deepcopy(hub)

        result = self.api.get_hub_region(hub)

        self.assertIs(result, ApsRegion.US)
        self.assertEqual(hub, original)

    def test_get_hub_region_accepts_an_explicit_fallback(self):
        self.assertIs(
            self.api.get_hub_region({}, default=ApsRegion.CAN), ApsRegion.CAN
        )

    def test_get_hub_region_rejects_invalid_payloads_or_region(self):
        invalid_hubs = (
            None,
            [],
            {"attributes": []},
            {"attributes": {"region": "APAC"}},
        )
        for hub in invalid_hubs:
            with self.subTest(hub=hub):
                with self.assertRaises(ValueError):
                    self.api.get_hub_region(hub)


class TestDataManagementFolderNavigation(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.get_private_token.return_value = "private-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccDataManagementApi(self.base)
        self.headers = {"Authorization": "Bearer private-token"}

    def response(self, payload, status_code=200):
        response = MagicMock(status_code=status_code)
        response.json.return_value = payload
        return response

    def test_get_project_top_folders_uses_filters_and_normalized_path(self):
        self.base.transport.get.return_value = self.response(
            {"data": [{"id": "folder-id"}]}
        )

        result = self.api.get_project_top_folders(
            "hub-id",
            "project-id",
            excludeDeleted=True,
            projectFilesOnly=True,
        )

        self.assertEqual(result, [{"id": "folder-id"}])
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/project/v1/hubs/b.hub-id/projects/b.project-id/topFolders",
            headers=self.headers,
            params={"excludeDeleted": True, "projectFilesOnly": True},
        )

    def test_get_folder_details_normalizes_project_and_preserves_headers(self):
        payload = {"id": "folder-id"}
        self.base.transport.get.return_value = self.response({"data": payload})

        result = self.api.get_folder_details(
            "project-id",
            "folder-id",
            if_modified_since="Thu, 04 Sep 2026 00:00:00 GMT",
            user_id="user-id",
        )

        self.assertEqual(result, payload)
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/data/v1/projects/b.project-id/folders/folder-id",
            headers={
                **self.headers,
                "x-user-id": "user-id",
                "If-Modified-Since": "Thu, 04 Sep 2026 00:00:00 GMT",
            },
        )

    def test_get_folder_contents_uses_valid_path_and_query_parameters(self):
        self.base.transport.get.return_value = self.response(
            {"data": [{"type": "items", "id": "item-id"}]}
        )

        result = self.api.get_folder_contents(
            "project-id",
            "folder-id",
            filter_type="items",
            page_number=2,
            page_limit=50,
            include_hidden=True,
        )

        self.assertEqual(result, [{"type": "items", "id": "item-id"}])
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/data/v1/projects/b.project-id/folders/folder-id/contents",
            headers={
                **self.headers,
                "Content-Type": "application/json",
            },
            params={
                "filter[type]": "items",
                "page[number]": 2,
                "page[limit]": 50,
                "includeHidden": "true",
            },
        )


class TestDataManagementItemVersionNavigation(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.get_private_token.return_value = "private-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccDataManagementApi(self.base)
        self.headers = {"Authorization": "Bearer private-token"}

    def response(self, payload, status_code=200):
        response = MagicMock(status_code=status_code)
        response.json.return_value = payload
        return response

    def test_get_item_encodes_urn_and_preserves_facade_shape(self):
        metadata = {"id": "item-id", "type": "items"}
        version = {"id": "version-id", "type": "versions"}
        self.base.transport.get.return_value = self.response(
            {"data": metadata, "included": [version]}
        )

        result = self.api.get_item(
            "project-id",
            "urn:adsk.wipprod:dm.lineage:item-id",
            include_path_in_project=True,
        )

        self.assertEqual(
            result, {"metadata": metadata, "most_recent_version": version}
        )
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/data/v1/projects/b.project-id/items/urn%3Aadsk.wipprod%3Adm.lineage%3Aitem-id",
            headers=self.headers,
            params={"includePathInProject": True},
        )

    def test_get_tip_version_normalizes_project_and_encodes_item(self):
        payload = {"id": "version-id"}
        self.base.transport.get.return_value = self.response({"data": payload})

        result = self.api.get_tip_version(
            "project-id", "urn:adsk.wipprod:dm.lineage:item-id"
        )

        self.assertEqual(result, payload)
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/data/v1/projects/b.project-id/items/urn%3Aadsk.wipprod%3Adm.lineage%3Aitem-id/tip",
            headers=self.headers,
        )

    def test_get_item_versions_follows_relative_pagination(self):
        first = self.response(
            {
                "data": [{"id": "version-one"}],
                "links": {
                    "next": {
                        "href": "/data/v1/projects/b.project-id/items/item-id/versions?page[number]=2"
                    }
                },
            }
        )
        second = self.response({"data": [{"id": "version-two"}], "links": {}})
        self.base.transport.get.side_effect = [first, second]

        result = self.api.get_item_versions(
            "project-id", "item-id", filters={"versionNumber": 1}
        )

        self.assertEqual(result, [{"id": "version-one"}, {"id": "version-two"}])
        self.base.transport.get.assert_any_call(
            "https://developer.api.autodesk.com/data/v1/projects/b.project-id/items/item-id/versions",
            headers=self.headers,
            params={"filter[versionNumber]": 1},
        )
        self.base.transport.get.assert_any_call(
            "https://developer.api.autodesk.com/data/v1/projects/b.project-id/items/item-id/versions?page[number]=2",
            headers=self.headers,
            params={},
        )

    def test_get_version_returns_data_and_encodes_version_urn(self):
        payload = {"id": "version-id", "type": "versions"}
        self.base.transport.get.return_value = self.response({"data": payload})

        result = self.api.get_version(
            "project-id", "urn:adsk.wipprod:fs.file:file-id?version=2"
        )

        self.assertEqual(result, payload)
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/data/v1/projects/b.project-id/versions/urn%3Aadsk.wipprod%3Afs.file%3Afile-id%3Fversion%3D2",
            headers=self.headers,
        )


if __name__ == "__main__":
    unittest.main()
