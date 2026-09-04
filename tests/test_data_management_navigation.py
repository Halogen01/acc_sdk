import unittest
from unittest.mock import MagicMock

from acc_sdk.base import AccBase
from acc_sdk.data_management import AccDataManagementApi
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


if __name__ == "__main__":
    unittest.main()
