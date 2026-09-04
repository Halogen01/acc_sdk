"""Autodesk Construction Cloud Revit Cloud Model operations."""

from urllib.parse import quote, urljoin, urlparse

from .base import AccBase


class AccRevitCloudModelsApi:
    """Retrieve published Revit Cloud Model link information."""

    API_ROOT = "https://developer.api.autodesk.com"
    DEFAULT_MAX_LINKED_FILE_PAGES = 100
    MAX_LINKED_FILE_PAGES = 100
    DEFAULT_MAX_LINKED_FILE_RESULTS = 10_000
    MAX_LINKED_FILE_RESULTS = 100_000

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

    def get_all_linked_files(
        self,
        project_id: str,
        version_id: str,
        include_host: bool = False,
        max_pages: int = DEFAULT_MAX_LINKED_FILE_PAGES,
        max_results: int = DEFAULT_MAX_LINKED_FILE_RESULTS,
    ) -> list[dict]:
        """Return linked-file results across bounded RCM pagination."""
        self._validate_request(project_id, version_id, include_host)
        self._validate_pagination_limits(max_pages, max_results)

        current_url = self._linked_files_url(project_id, version_id)
        page = self._request_linked_files_page(
            current_url, params={"includeHost": str(include_host).lower()}
        )
        results = []
        seen_urls = {current_url}
        page_number = 1

        while True:
            page_results = page.get("results")
            if page_results is None:
                page_results = []
            if not isinstance(page_results, list) or any(
                not isinstance(result, dict) for result in page_results
            ):
                raise RuntimeError("RCM linkedFiles results must be a list of objects")

            pagination = page.get("pagination")
            if pagination is not None and not isinstance(pagination, dict):
                raise RuntimeError("RCM linkedFiles pagination must be an object")
            pagination = pagination or {}
            total_results = pagination.get("totalResults")
            if total_results is not None and (
                isinstance(total_results, bool)
                or not isinstance(total_results, int)
                or total_results < 0
            ):
                raise RuntimeError(
                    "RCM linkedFiles totalResults must be a non-negative integer"
                )
            if total_results is not None and total_results > max_results:
                raise RuntimeError("RCM linked-file result count exceeds max_results")
            if len(results) + len(page_results) > max_results:
                raise RuntimeError("RCM linked-file result count exceeds max_results")
            results.extend(page_results)

            next_url = pagination.get("nextUrl")
            if next_url is None or next_url == "":
                return results
            if page_number >= max_pages:
                raise RuntimeError("RCM linked-file pagination exceeds max_pages")

            next_url = self._validate_next_url(
                current_url, next_url, project_id, version_id
            )
            if next_url in seen_urls:
                raise RuntimeError("RCM linked-file pagination contains a cycle")
            seen_urls.add(next_url)
            current_url = next_url
            page = self._request_linked_files_page(current_url)
            page_number += 1

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

    @classmethod
    def _validate_pagination_limits(
        cls, max_pages: int, max_results: int
    ) -> None:
        if (
            isinstance(max_pages, bool)
            or not isinstance(max_pages, int)
            or not 1 <= max_pages <= cls.MAX_LINKED_FILE_PAGES
        ):
            raise ValueError(
                f"max_pages must be an integer from 1 to {cls.MAX_LINKED_FILE_PAGES}"
            )
        if (
            isinstance(max_results, bool)
            or not isinstance(max_results, int)
            or not 0 <= max_results <= cls.MAX_LINKED_FILE_RESULTS
        ):
            raise ValueError(
                "max_results must be an integer from 0 to "
                f"{cls.MAX_LINKED_FILE_RESULTS}"
            )

    def _validate_next_url(
        self,
        current_url: str,
        next_url: str,
        project_id: str,
        version_id: str,
    ) -> str:
        if not isinstance(next_url, str) or not next_url:
            raise RuntimeError("RCM linkedFiles nextUrl must be a non-empty string")
        resolved_url = urljoin(current_url, next_url)
        parsed = urlparse(resolved_url)
        expected_path = urlparse(
            self._linked_files_url(project_id, version_id)
        ).path
        try:
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as error:
            raise RuntimeError(
                "RCM linkedFiles nextUrl must be a valid Autodesk URL"
            ) from error
        if (
            parsed.scheme != "https"
            or hostname != "developer.api.autodesk.com"
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != expected_path
            or bool(parsed.fragment)
        ):
            raise RuntimeError(
                "RCM linkedFiles nextUrl must remain on the Autodesk endpoint"
            )
        return resolved_url

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
