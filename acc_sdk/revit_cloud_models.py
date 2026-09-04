"""Autodesk Construction Cloud Revit Cloud Model operations."""

from urllib.parse import quote

from .base import AccBase


class AccRevitCloudModelsApi:
    """Retrieve published Revit Cloud Model link information."""

    API_ROOT = "https://developer.api.autodesk.com"

    def __init__(self, base: AccBase):
        self.base = base

    def get_linked_files(
        self,
        project_id: str,
        version_id: str,
        include_host: bool = False,
    ) -> dict:
        """Return one linked-file result page for a published RCM version.

        ``project_id`` is sent exactly as supplied, so a Data Management project
        ID retains its ``b.`` prefix. ``version_id`` is expected to be the full
        published version URN and is URL encoded for the path.
        """
        self._validate_request(project_id, version_id, include_host)
        url = self._linked_files_url(project_id, version_id)
        return self._request_linked_files_page(
            url, params={"includeHost": str(include_host).lower()}
        )

    @staticmethod
    def _validate_request(
        project_id: str, version_id: str, include_host: bool
    ) -> None:
        if not isinstance(project_id, str) or not project_id:
            raise ValueError("A project ID is required")
        if not isinstance(version_id, str) or not version_id:
            raise ValueError("A published version ID is required")
        if not isinstance(include_host, bool):
            raise ValueError("include_host must be a boolean")

    def _linked_files_url(self, project_id: str, version_id: str) -> str:
        encoded_project_id = quote(project_id, safe="")
        encoded_version_id = quote(version_id, safe="")
        return (
            f"{self.API_ROOT}/construction/rcm/v1/projects/"
            f"{encoded_project_id}/published-versions/{encoded_version_id}/"
            "linked-files"
        )

    def _request_linked_files_page(self, url: str, params: dict = None) -> dict:
        token = self.base.get_3leggedToken()
        if not isinstance(token, str) or not token:
            raise RuntimeError(
                "RCM linked-file retrieval requires a three-legged access token"
            )
        response = self.base.transport.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
        )
        response.raise_for_status()
        document = response.json()
        linked_files = (
            document.get("linkedFiles") if isinstance(document, dict) else None
        )
        if not isinstance(linked_files, dict):
            raise RuntimeError(
                "RCM did not return a linkedFiles response container"
            )
        return linked_files
