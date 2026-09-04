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


if __name__ == "__main__":
    unittest.main()
