"""Tests for request timeouts and 200-body decoding robustness."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest

from dimplex_controller.client import DEFAULT_TIMEOUT, DimplexControl, _coerce_timeout
from dimplex_controller.exceptions import DimplexConnectionError


def _authed(session: aiohttp.ClientSession, **kwargs) -> DimplexControl:
    client = DimplexControl(session, refresh_token="fake_refresh", **kwargs)
    client.auth._access_token = "fake_access"
    client.auth._expires_at = 9999999999
    return client


def test_coerce_timeout_variants():
    """A number becomes a total timeout; None disables; ClientTimeout passes through."""
    assert _coerce_timeout(None) is None

    coerced = _coerce_timeout(12.5)
    assert isinstance(coerced, aiohttp.ClientTimeout)
    assert coerced.total == 12.5

    explicit = aiohttp.ClientTimeout(total=1, connect=2)
    assert _coerce_timeout(explicit) is explicit


def test_default_timeout_applied_to_client_and_auth():
    """The default timeout flows to both the client and its auth manager."""
    session = object()  # not used for network here
    client = DimplexControl(session)  # type: ignore[arg-type]
    assert isinstance(client._timeout, aiohttp.ClientTimeout)
    assert client._timeout.total == DEFAULT_TIMEOUT
    assert client.auth._timeout is client._timeout


def test_timeout_none_disables_client_timeout():
    """Passing timeout=None leaves aiohttp defaults in charge (no override kwarg)."""
    session = object()
    client = DimplexControl(session, timeout=None)  # type: ignore[arg-type]
    assert client._timeout is None
    assert client.auth._timeout is None


@pytest.mark.asyncio
async def test_request_passes_timeout(monkeypatch):
    """_request forwards the configured timeout to session.request."""
    captured: dict[str, object] = {}

    class _FakeResp:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def text(self):
            return "{}"

    class _FakeSession:
        def request(self, method, url, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return _FakeResp()

    client = DimplexControl(_FakeSession(), refresh_token="r", timeout=7.0)  # type: ignore[arg-type]
    client.auth._access_token = "a"
    client.auth._expires_at = 9999999999

    result = await client._request("GET", "/whatever")
    assert result == {}
    assert isinstance(captured["timeout"], aiohttp.ClientTimeout)
    assert captured["timeout"].total == 7.0


@pytest.mark.asyncio
async def test_timeout_surfaces_as_connection_error(monkeypatch):
    """An asyncio.TimeoutError from the transport becomes DimplexConnectionError."""

    class _TimingOutSession:
        def request(self, method, url, **kwargs):
            raise asyncio.TimeoutError

    client = DimplexControl(_TimingOutSession(), refresh_token="r", max_retries=0)  # type: ignore[arg-type]
    client.auth._access_token = "a"
    client.auth._expires_at = 9999999999

    with pytest.raises(DimplexConnectionError):
        await client._request("GET", "/whatever")


@pytest.mark.asyncio
async def test_empty_200_body_returns_empty_dict(aresponses):
    """A 200 with an empty body (no Content-Length) decodes to {} rather than raising."""
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/SetEcoStart",
        "POST",
        aresponses.Response(status=200, body=""),
    )

    async with aiohttp.ClientSession() as session:
        client = _authed(session)
        # set_eco_start returns None but must not raise on an empty body.
        assert await client.set_eco_start("hub", ["a"], True) is None


@pytest.mark.asyncio
async def test_whitespace_200_body_returns_empty_dict(aresponses):
    """A 200 body of only whitespace is treated as empty."""
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/RemoteControl/SetOpenWindowDetection",
        "POST",
        aresponses.Response(status=200, body="   \n  "),
    )

    async with aiohttp.ClientSession() as session:
        client = _authed(session)
        assert await client.set_open_window_detection("hub", ["a"], True) is None


@pytest.mark.asyncio
async def test_malformed_200_json_wrapped(aresponses):
    """A non-empty 200 body that is not valid JSON is wrapped, not leaked raw."""
    aresponses.add(
        "mobileapi.gdhv-iot.com",
        "/api/Hubs/GetUserHubs",
        "GET",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body="<html>not json</html>",
        ),
    )

    async with aiohttp.ClientSession() as session:
        client = _authed(session, max_retries=0)
        with pytest.raises(DimplexConnectionError):
            await client.get_hubs()


@pytest.mark.asyncio
async def test_connection_error_retry_then_success(monkeypatch):
    """A connection error on a GET is retried and can then succeed."""
    slept: list[float] = []

    async def _fake_sleep(delay):
        slept.append(delay)

    monkeypatch.setattr("dimplex_controller.client.asyncio.sleep", _fake_sleep)

    class _FakeResp:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def text(self):
            return "[]"

    class _FlakySession:
        def __init__(self):
            self.calls = 0

        def request(self, method, url, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise aiohttp.ClientConnectionError("boom")
            return _FakeResp()

    session = _FlakySession()
    client = DimplexControl(session, refresh_token="r", max_retries=2)  # type: ignore[arg-type]
    client.auth._access_token = "a"
    client.auth._expires_at = 9999999999

    hubs = await client.get_hubs()
    assert hubs == []
    assert session.calls == 2
    assert len(slept) == 1  # one backoff between the two attempts


@pytest.mark.asyncio
async def test_post_not_retried_by_default(monkeypatch):
    """Non-idempotent POSTs are not retried unless explicitly opted in."""
    slept: list[float] = []

    async def _fake_sleep(delay):
        slept.append(delay)

    monkeypatch.setattr("dimplex_controller.client.asyncio.sleep", _fake_sleep)

    class _FailSession:
        def __init__(self):
            self.calls = 0

        def request(self, method, url, **kwargs):
            self.calls += 1
            raise aiohttp.ClientConnectionError("boom")

    session = _FailSession()
    client = DimplexControl(session, refresh_token="r", max_retries=3)  # type: ignore[arg-type]
    client.auth._access_token = "a"
    client.auth._expires_at = 9999999999

    with pytest.raises(DimplexConnectionError):
        await client.set_eco_start("hub", ["a"], True)
    assert session.calls == 1  # no retry for POST
    assert slept == []


@pytest.mark.asyncio
async def test_retry_non_idempotent_opt_in(monkeypatch):
    """retry_non_idempotent=True applies the retry policy to POSTs."""
    slept: list[float] = []

    async def _fake_sleep(delay):
        slept.append(delay)

    monkeypatch.setattr("dimplex_controller.client.asyncio.sleep", _fake_sleep)

    class _FailSession:
        def __init__(self):
            self.calls = 0

        def request(self, method, url, **kwargs):
            self.calls += 1
            raise aiohttp.ClientConnectionError("boom")

    session = _FailSession()
    client = DimplexControl(
        session,  # type: ignore[arg-type]
        refresh_token="r",
        max_retries=2,
        retry_non_idempotent=True,
    )
    client.auth._access_token = "a"
    client.auth._expires_at = 9999999999

    with pytest.raises(DimplexConnectionError):
        await client.set_eco_start("hub", ["a"], True)
    assert session.calls == 3  # 1 + 2 retries
    assert len(slept) == 2
