import unittest
from unittest.mock import MagicMock
from acc_sdk.forms import AccFormsApi
from acc_sdk.base import AccBase
from acc_sdk.transport import HttpTransport


class TestAccFormsApi(unittest.TestCase):
    def setUp(self):
        # Create a mock AccBase instance
        self.mock_base = MagicMock(spec=AccBase)
        self.mock_base.get_3leggedToken.return_value = "mock_token"
        self.mock_transport = MagicMock(spec=HttpTransport)
        self.mock_base.transport = self.mock_transport

        # Create an instance of AccFormsApi with the mock base
        self.api = AccFormsApi(base=self.mock_base)

    def test_get_forms(self):
        # Set up the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"id": "form1", "name": "Form 1"},
                {"id": "form2", "name": "Form 2"},
            ],
            "pagination": {"nextUrl": None},
        }
        self.mock_transport.get.return_value = mock_response

        # Call the method
        result = self.api.get_forms(project_id="test_project_id")

        # Verify the result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "form1")
        self.assertEqual(result[1]["id"], "form2")

        # Verify the request was made correctly
        self.mock_transport.get.assert_called_once_with(
            f"{self.api.base_url}/projects/test_project_id/forms",
            headers=self.api._get_headers(),
            params={"offset": 0, "limit": 50},
        )

    def test_get_forms_with_pagination(self):
        # Set up the mock responses for pagination
        first_response = MagicMock()
        first_response.status_code = 200
        first_response.json.return_value = {
            "data": [{"id": "form1", "name": "Form 1"}],
            "pagination": {"nextUrl": "https://example.com/next-page"},
        }

        second_response = MagicMock()
        second_response.status_code = 200
        second_response.json.return_value = {
            "data": [{"id": "form2", "name": "Form 2"}],
            "pagination": {"nextUrl": None},
        }

        # Configure the mock to return different responses on consecutive calls
        self.mock_transport.get.side_effect = [first_response, second_response]

        # Call the method with pagination enabled
        result = self.api.get_forms(
            project_id="test_project_id", follow_pagination=True
        )

        # Verify the result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "form1")
        self.assertEqual(result[1]["id"], "form2")

        # Verify the requests were made correctly
        self.assertEqual(self.mock_transport.get.call_count, 2)
        self.mock_transport.get.assert_any_call(
            f"{self.api.base_url}/projects/test_project_id/forms",
            headers=self.api._get_headers(),
            params={"offset": 0, "limit": 50},
        )
        self.mock_transport.get.assert_any_call(
            "https://example.com/next-page",
            headers=self.api._get_headers(),
            params=None,
        )

    def test_get_templates(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"id": "template-id"}]}
        self.mock_transport.get.return_value = mock_response

        result = self.api.get_templates(project_id="b.test_project_id")

        self.assertEqual(result, [{"id": "template-id"}])
        self.mock_transport.get.assert_called_once_with(
            f"{self.api.base_url}/projects/test_project_id/form-templates",
            headers=self.api._get_headers(),
            params={"offset": 0, "limit": 50},
        )

    def test_post_form(self):
        # Set up the mock response
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "new_form_id", "name": "New Form"}
        self.mock_transport.post.return_value = mock_response

        # Define form data
        form_data = {"customValues": {"field1": "value1"}}

        # Call the method
        result = self.api.post_form(
            project_id="test_project_id", template_id="template_id", data=form_data
        )

        # Verify the result
        self.assertEqual(result["id"], "new_form_id")
        self.assertEqual(result["name"], "New Form")

        # Verify the request was made correctly
        self.mock_transport.post.assert_called_once_with(
            f"{self.api.base_url}/projects/test_project_id/form-templates/template_id/forms",
            headers=self.api._get_headers(),
            json=form_data,
        )

    def test_patch_form(self):
        # Set up the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "updated_form_id",
            "name": "Updated Form",
        }
        self.mock_transport.patch.return_value = mock_response

        # Define update data
        update_data = {"customValues": {"field1": "updated_value1"}}

        # Call the method
        result = self.api.patch_form(
            project_id="test_project_id",
            template_id="template_id",
            form_id="form_id",
            data=update_data,
        )

        # Verify the result
        self.assertEqual(result["id"], "updated_form_id")
        self.assertEqual(result["name"], "Updated Form")

        # Verify the request was made correctly
        self.mock_transport.patch.assert_called_once_with(
            f"{self.api.base_url}/projects/test_project_id/form-templates/template_id/forms/form_id",
            headers=self.api._get_headers(),
            json=update_data,
        )

    def test_put_form(self):
        # Set up the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "updated_form_id",
            "customValues": {"field1": "new_value1"},
        }
        self.mock_transport.put.return_value = mock_response

        # Define update data
        update_data = {"customValues": {"field1": "new_value1"}}

        # Call the method
        result = self.api.put_form(
            project_id="test_project_id", form_id="form_id", data=update_data
        )

        # Verify the result
        self.assertEqual(result["id"], "updated_form_id")
        self.assertEqual(result["customValues"]["field1"], "new_value1")

        # Verify the request was made correctly
        self.mock_transport.put.assert_called_once_with(
            f"{self.api.base_url}/projects/test_project_id/forms/form_id/values:batch-update",
            headers=self.api._get_headers(),
            json=update_data,
        )


if __name__ == "__main__":
    unittest.main()
