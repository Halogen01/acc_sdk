"""Shared HTTP transport primitives for Autodesk API clients."""

from collections.abc import Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_TIMEOUT = (5.0, 30.0)
DEFAULT_RETRY_STATUSES = (429, 502, 503, 504)
DEFAULT_RETRY_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class HttpTransport:
    """Pooled requests transport with bounded waits and safe read retries."""

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        retry_statuses: Iterable[int] = DEFAULT_RETRY_STATUSES,
    ):
        self.session = session if session is not None else requests.Session()
        self.timeout = timeout

        retry = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            status=max_retries,
            allowed_methods=DEFAULT_RETRY_METHODS,
            status_forcelist=tuple(retry_statuses),
            backoff_factor=backoff_factor,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def request(self, method: str, url: str, **kwargs):
        """Send one request, applying the default timeout when none is supplied."""
        kwargs.setdefault("timeout", self.timeout)
        return self.session.request(method=method, url=url, **kwargs)

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def close(self):
        self.session.close()

