import unittest
from unittest.mock import MagicMock, patch

import requests

from acc_sdk.acc import Acc
from acc_sdk.base import AccBase
from acc_sdk.revit_cloud_models import AccRevitCloudModelsApi
from acc_sdk.transport import HttpTransport


class TestRevitCloudModelLinkedFiles(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.get_3leggedToken.return_value = "three-legged-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccRevitCloudModelsApi(self.base)

    def response(self, payload):
        response = MagicMock()
        response.json.return_value = payload
        self.base.transport.get.return_value = response
        return response

    def test_gets_linked_files_with_encoded_version_and_excludes_host(self):
        linked_files = {
            "pagination": {
                "limit": 20,
                "offset": 0,
                "nextUrl": None,
                "nextOffset": None,
                "totalResults": 1,
            },
            "results": [
                {
                    "modelName": "Structure.rvt",
                    "signedUrl": "https://example.s3.amazonaws.com/linked",
                    "itemId": "item-id",
                    "versionId": "version-id",
                    "publishStatus": "published",
                }
            ],
        }
        response = self.response({"linkedFiles": linked_files})

        result = self.api.get_linked_files(
            "b.project-id",
            "urn:adsk.wipprod:fs.file:vf.file-id?version=2",
        )

        self.assertIs(result, linked_files)
        response.raise_for_status.assert_called_once_with()
        self.base.transport.get.assert_called_once_with(
            "https://developer.api.autodesk.com/construction/rcm/v1/projects/"
            "b.project-id/published-versions/"
            "urn%3Aadsk.wipprod%3Afs.file%3Avf.file-id%3Fversion%3D2/"
            "linked-files",
            headers={"Authorization": "Bearer three-legged-token"},
            params={"includeHost": "false"},
        )

    def test_can_include_host_file_explicitly(self):
        self.response({"linkedFiles": {"results": []}})

        self.api.get_linked_files("b.project-id", "version-id", include_host=True)

        self.assertEqual(
            self.base.transport.get.call_args.kwargs["params"],
            {"includeHost": "true"},
        )

    def test_rejects_invalid_input_before_token_lookup_or_request(self):
        invalid_calls = [
            (None, "version-id", False),
            ("b.project-id", "", False),
            ("b.project-id", "version-id", "false"),
        ]

        for arguments in invalid_calls:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    self.api.get_linked_files(*arguments)

        self.base.get_3leggedToken.assert_not_called()
        self.base.transport.get.assert_not_called()

    def test_requires_three_legged_token(self):
        self.base.get_3leggedToken.return_value = None

        with self.assertRaisesRegex(RuntimeError, "three-legged"):
            self.api.get_linked_files("b.project-id", "version-id")

        self.base.transport.get.assert_not_called()

    def test_preserves_http_error(self):
        response = MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError("forbidden")
        self.base.transport.get.return_value = response

        with self.assertRaises(requests.HTTPError):
            self.api.get_linked_files("b.project-id", "version-id")

    def test_rejects_malformed_success_response(self):
        self.response({"results": []})

        with self.assertRaisesRegex(RuntimeError, "linkedFiles"):
            self.api.get_linked_files("b.project-id", "version-id")

    def test_acc_exposes_additive_revit_cloud_models_service(self):
        auth_client = MagicMock()
        base = MagicMock(spec=AccBase)
        base.user_info = {"uid": "user-id"}
        with patch("acc_sdk.acc.AccBase", return_value=base):
            acc = Acc(auth_client=auth_client, account_id="account-id")

        self.assertIsInstance(acc.revit_cloud_models, AccRevitCloudModelsApi)
        self.assertIs(acc.revit_cloud_models.base, base)


class TestRevitCloudModelLinkedFilePagination(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock(spec=AccBase)
        self.base.get_3leggedToken.return_value = "three-legged-token"
        self.base.transport = MagicMock(spec=HttpTransport)
        self.api = AccRevitCloudModelsApi(self.base)
        self.initial_url = (
            "https://developer.api.autodesk.com/construction/rcm/v1/projects/"
            "b.project-id/published-versions/version-id/linked-files"
        )

    @staticmethod
    def response(results, pagination=None):
        response = MagicMock()
        response.json.return_value = {
            "linkedFiles": {"results": results, "pagination": pagination}
        }
        return response

    def test_follows_relative_next_url_and_combines_results(self):
        second_url = f"{self.initial_url}?limit=2&offset=2&includeHost=false"
        self.base.transport.get.side_effect = [
            self.response(
                [{"modelName": "A.rvt"}, {"modelName": "B.rvt"}],
                {
                    "totalResults": 3,
                    "nextUrl": (
                        "/construction/rcm/v1/projects/b.project-id/"
                        "published-versions/version-id/linked-files?"
                        "limit=2&offset=2&includeHost=false"
                    ),
                },
            ),
            self.response(
                [{"modelName": "C.rvt"}],
                {"totalResults": 3, "nextUrl": None},
            ),
        ]

        result = self.api.get_all_linked_files(
            "b.project-id", "version-id", max_pages=2, max_results=3
        )

        self.assertEqual(
            [linked_file["modelName"] for linked_file in result],
            ["A.rvt", "B.rvt", "C.rvt"],
        )
        self.base.transport.get.assert_any_call(
            self.initial_url,
            headers={"Authorization": "Bearer three-legged-token"},
            params={"includeHost": "false"},
        )
        self.base.transport.get.assert_any_call(
            second_url,
            headers={"Authorization": "Bearer three-legged-token"},
            params={},
        )

    def test_stops_when_server_total_exceeds_result_cap(self):
        self.base.transport.get.return_value = self.response(
            [{"modelName": "A.rvt"}],
            {"totalResults": 11, "nextUrl": f"{self.initial_url}?offset=1"},
        )

        with self.assertRaisesRegex(RuntimeError, "exceeds max_results"):
            self.api.get_all_linked_files(
                "b.project-id", "version-id", max_results=10
            )

        self.base.transport.get.assert_called_once()

    def test_stops_before_page_beyond_page_cap(self):
        self.base.transport.get.return_value = self.response(
            [], {"totalResults": 2, "nextUrl": f"{self.initial_url}?offset=1"}
        )

        with self.assertRaisesRegex(RuntimeError, "exceeds max_pages"):
            self.api.get_all_linked_files(
                "b.project-id", "version-id", max_pages=1
            )

        self.base.transport.get.assert_called_once()

    def test_rejects_cross_origin_or_wrong_path_next_url(self):
        invalid_urls = (
            "https://example.com/steal-token",
            "https://developer.api.autodesk.com/other/service?offset=2",
            f"{self.initial_url}#unexpected-fragment",
        )
        for next_url in invalid_urls:
            with self.subTest(next_url=next_url):
                self.base.transport.get.reset_mock()
                self.base.transport.get.return_value = self.response(
                    [], {"totalResults": 1, "nextUrl": next_url}
                )
                with self.assertRaisesRegex(RuntimeError, "Autodesk endpoint"):
                    self.api.get_all_linked_files(
                        "b.project-id", "version-id", max_pages=2
                    )
                self.base.transport.get.assert_called_once()

    def test_rejects_pagination_cycle(self):
        cycled_url = f"{self.initial_url}?offset=1"
        self.base.transport.get.side_effect = [
            self.response([], {"nextUrl": cycled_url}),
            self.response([], {"nextUrl": cycled_url}),
        ]

        with self.assertRaisesRegex(RuntimeError, "contains a cycle"):
            self.api.get_all_linked_files(
                "b.project-id", "version-id", max_pages=3
            )

        self.assertEqual(self.base.transport.get.call_count, 2)

    def test_rejects_invalid_limits_before_token_lookup(self):
        invalid_limits = ((0, 10), (101, 10), (1, -1), (1, 100_001))
        for max_pages, max_results in invalid_limits:
            with self.subTest(max_pages=max_pages, max_results=max_results):
                with self.assertRaises(ValueError):
                    self.api.get_all_linked_files(
                        "b.project-id",
                        "version-id",
                        max_pages=max_pages,
                        max_results=max_results,
                    )

        self.base.get_3leggedToken.assert_not_called()
        self.base.transport.get.assert_not_called()

    def test_rejects_malformed_page_collections(self):
        malformed_pages = (
            {"results": {}, "pagination": None},
            {"results": [], "pagination": []},
            {"results": [], "pagination": {"totalResults": True}},
        )
        for linked_files in malformed_pages:
            with self.subTest(linked_files=linked_files):
                response = MagicMock()
                response.json.return_value = {"linkedFiles": linked_files}
                self.base.transport.get.return_value = response
                with self.assertRaises(RuntimeError):
                    self.api.get_all_linked_files(
                        "b.project-id", "version-id"
                    )


if __name__ == "__main__":
    unittest.main()
