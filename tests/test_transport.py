from unittest.mock import MagicMock

import requests

from acc_sdk.transport import (
    DEFAULT_RETRY_METHODS,
    DEFAULT_RETRY_STATUSES,
    DEFAULT_TIMEOUT,
    HttpTransport,
)


def test_transport_uses_a_pooled_requests_session():
    transport = HttpTransport()

    assert isinstance(transport.session, requests.Session)
    assert "http://" in transport.session.adapters
    assert "https://" in transport.session.adapters

    transport.close()


def test_retry_policy_is_bounded_and_excludes_post_requests():
    session = MagicMock(spec=requests.Session)

    HttpTransport(session=session, max_retries=2, backoff_factor=0.25)

    assert session.mount.call_count == 2
    adapter = session.mount.call_args_list[1].args[1]
    retry = adapter.max_retries
    assert retry.total == 2
    assert retry.connect == 2
    assert retry.read == 2
    assert retry.status == 2
    assert retry.allowed_methods == DEFAULT_RETRY_METHODS
    assert "POST" not in retry.allowed_methods
    assert retry.status_forcelist == DEFAULT_RETRY_STATUSES
    assert retry.respect_retry_after_header is True
    assert retry.raise_on_status is False
    assert retry.backoff_factor == 0.25


def test_default_timeout_is_applied_to_every_request():
    session = MagicMock(spec=requests.Session)
    response = MagicMock()
    session.request.return_value = response
    transport = HttpTransport(session=session)

    result = transport.get("https://example.test/resource", headers={"Accept": "application/json"})

    assert result is response
    session.request.assert_called_once_with(
        method="GET",
        url="https://example.test/resource",
        headers={"Accept": "application/json"},
        timeout=DEFAULT_TIMEOUT,
    )


def test_explicit_timeout_overrides_the_default():
    session = MagicMock(spec=requests.Session)
    transport = HttpTransport(session=session)

    transport.post("https://example.test/token", timeout=(2.0, 10.0))

    session.request.assert_called_once_with(
        method="POST",
        url="https://example.test/token",
        timeout=(2.0, 10.0),
    )
