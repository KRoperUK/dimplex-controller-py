"""AuthManager and structured auth-error coverage."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from unittest.mock import MagicMock

import aiohttp
import pytest

from dimplex_controller.auth import AuthManager, TokenBundle
from dimplex_controller.const import B2C_POLICY, REDIRECT_URI
from dimplex_controller.exceptions import (
    DimplexAuthInvalidCredentialsError,
    DimplexAuthInvalidGrantError,
    DimplexAuthParseError,
    DimplexAuthTransientError,
    classify_oauth_token_error,
    oauth_error_summary,
)

B2C_HOST = "gdhvb2c.b2clogin.com"
TOKEN_PATH = "/tfp/gdhvb2c.onmicrosoft.com/B2C_1A_DimplexControlSignupSignin/oauth2/v2.0/token"
AUTHORIZE_PATH = re.compile(r".*/oauth2/v2\.0/authorize.*")
SELF_ASSERTED_PATH = re.compile(r".*/SelfAsserted.*")
CONFIRMED_PATH = re.compile(r".*/CombinedSigninAndSignup/confirmed.*")

LOGIN_HTML = """
<html><script>
var SETTINGS = {"csrf":"csrf-token-value","transId":"StateProperties=abc123"};
</script></html>
"""

AUTHORIZE_URL = (
    "https://gdhvb2c.b2clogin.com/tfp/gdhvb2c.onmicrosoft.com/"
    "B2C_1A_DimplexControlSignupSignin/oauth2/v2.0/authorize"
)


def _token_response(
    aresponses,
    *,
    status: int = 200,
    body: str = '{"access_token": "new_access", "refresh_token": "new_refresh", "expires_in": 3600}',
) -> None:
    aresponses.add(
        B2C_HOST,
        TOKEN_PATH,
        "POST",
        aresponses.Response(
            status=status,
            headers={"Content-Type": "application/json"},
            body=body,
        ),
    )


# ---------------------------------------------------------------------------
# classify_oauth_token_error / summary
# ---------------------------------------------------------------------------


def test_classify_invalid_grant():
    err = classify_oauth_token_error(400, '{"error":"invalid_grant","error_description":"expired"}')
    assert isinstance(err, DimplexAuthInvalidGrantError)
    assert err.reauth_required is True
    assert err.transient is False
    assert err.code == "invalid_grant"
    assert err.status == 400
    assert err.details == "expired"


def test_classify_transient_5xx():
    err = classify_oauth_token_error(503, '{"error":"server_error"}')
    assert isinstance(err, DimplexAuthTransientError)
    assert err.transient is True
    assert err.reauth_required is False


def test_classify_rate_limit():
    err = classify_oauth_token_error(429, "slow down")
    assert isinstance(err, DimplexAuthTransientError)


def test_classify_non_json_client_error():
    err = classify_oauth_token_error(401, "nope")
    assert isinstance(err, DimplexAuthInvalidGrantError)
    assert err.reauth_required is True


def test_oauth_error_summary_no_secrets():
    summary = oauth_error_summary('{"error":"invalid_grant","error_description":"AADSTS70000"}')
    assert "invalid_grant" in summary
    assert "AADSTS70000" in summary
    assert oauth_error_summary("") == "empty body"
    # Non-JSON bodies are truncated for logs (no raw multi-KB dumps).
    assert oauth_error_summary("not-json-at-all") == "not-json-at-all"
    assert len(oauth_error_summary("x" * 250)) <= 200
    assert oauth_error_summary("{}") == "non-json body (2 bytes)"


# ---------------------------------------------------------------------------
# Token refresh / get_access_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_token_success(aresponses):
    """Test successful token refresh."""
    _token_response(aresponses)

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "old_refresh"})
        await auth.refresh_tokens()

        assert auth.export_tokens().access_token == "new_access"
        assert auth.export_tokens().refresh_token == "new_refresh"
        assert auth.is_authenticated


@pytest.mark.asyncio
async def test_refresh_token_invalid_grant(aresponses):
    """invalid_grant on refresh is reauth-required."""
    _token_response(aresponses, status=400, body='{"error": "invalid_grant"}')

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "bad_refresh"})
        with pytest.raises(DimplexAuthInvalidGrantError) as exc_info:
            await auth.refresh_tokens()
        assert exc_info.value.reauth_required is True
        assert exc_info.value.transient is False


@pytest.mark.asyncio
async def test_refresh_token_server_error_is_transient(aresponses):
    _token_response(aresponses, status=503, body='{"error":"temporarily_unavailable"}')

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "r"})
        with pytest.raises(DimplexAuthTransientError) as exc_info:
            await auth.refresh_tokens()
        assert exc_info.value.transient is True
        assert exc_info.value.reauth_required is False


@pytest.mark.asyncio
async def test_refresh_keeps_old_refresh_token_when_omitted(aresponses):
    _token_response(
        aresponses,
        body='{"access_token": "a2", "expires_in": 3600}',
    )
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "keep_me"})
        await auth.refresh_tokens()
        assert auth.export_tokens().refresh_token == "keep_me"
        assert auth.export_tokens().access_token == "a2"


@pytest.mark.asyncio
async def test_get_access_token_cached(aresponses):
    """Test getting cached access token without refresh."""
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "valid_refresh"})
        auth.apply_tokens({"access_token": "cached_token", "refresh_token": "valid_refresh", "expires_at": 9999999999})

        token = await auth.get_access_token()
        assert token == "cached_token"


@pytest.mark.asyncio
async def test_get_access_token_no_refresh_token():
    """Missing refresh token is reauth-required."""
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        with pytest.raises(DimplexAuthInvalidGrantError) as exc_info:
            await auth.get_access_token()
        assert exc_info.value.reauth_required is True


@pytest.mark.asyncio
async def test_get_access_token_expired_refreshes(aresponses):
    """Test getting access token when expired triggers refresh."""
    _token_response(
        aresponses,
        body='{"access_token": "refreshed_token", "refresh_token": "new_refresh", "expires_in": 3600}',
    )

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(
            session,
            {"access_token": "old_token", "refresh_token": "old_refresh", "expires_at": 1},
        )
        token = await auth.get_access_token()
        assert token == "refreshed_token"


@pytest.mark.asyncio
async def test_get_access_token_refresh_returns_no_access(aresponses):
    _token_response(aresponses, body='{"expires_in": 3600}')
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "r", "expires_at": 1})
        with pytest.raises(DimplexAuthInvalidGrantError) as exc_info:
            await auth.get_access_token()
        assert exc_info.value.code == "missing_access_token"


# ---------------------------------------------------------------------------
# is_authenticated / TokenBundle / listeners / persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_authenticated_true():
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "valid_refresh"})
        auth.apply_tokens({"access_token": "valid_token", "refresh_token": "valid_refresh", "expires_at": 9999999999})
        assert auth.is_authenticated is True


@pytest.mark.asyncio
async def test_is_authenticated_false_no_refresh():
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        assert auth.is_authenticated is False


@pytest.mark.asyncio
async def test_is_authenticated_false_expired():
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(
            session,
            {"access_token": "old_token", "refresh_token": "valid_refresh", "expires_at": 1},
        )
        assert auth.is_authenticated is False


@pytest.mark.asyncio
async def test_token_bundle_export_apply():
    """TokenBundle round-trips through export/apply without private field access."""
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(
            session,
            TokenBundle(access_token="a", refresh_token="r", expires_at=9999999999),
        )
        bundle = auth.export_tokens()
        assert bundle.access_token == "a"
        assert bundle.refresh_token == "r"
        assert bundle.as_dict()["access_token"] == "a"
        auth.apply_tokens({"access_token": "b", "refresh_token": "r2", "expires_at": 1})
        assert auth.export_tokens().access_token == "b"
        assert auth.export_tokens().refresh_token == "r2"


def test_token_bundle_from_empty_mapping():
    assert TokenBundle.from_mapping(None) == TokenBundle()
    assert TokenBundle.from_mapping({}) == TokenBundle()


@pytest.mark.asyncio
async def test_on_token_update_sync_and_async(aresponses):
    seen: list[TokenBundle] = []

    def sync_listener(bundle: TokenBundle) -> None:
        seen.append(bundle)

    async def async_listener(bundle: TokenBundle) -> None:
        seen.append(bundle)

    _token_response(aresponses)
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "r"}, on_token_update=sync_listener)
        await auth.refresh_tokens()
        assert len(seen) == 1
        assert seen[0].access_token == "new_access"

    _token_response(aresponses)
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "r"}, on_token_update=async_listener)
        await auth.refresh_tokens()
        assert len(seen) == 2


def test_save_and_load_tokens(tmp_path: Path):
    path = tmp_path / "tokens.json"
    assert AuthManager.load_tokens(str(path)) is None

    async def _save() -> None:
        async with aiohttp.ClientSession() as session:
            auth = AuthManager(
                session,
                TokenBundle(access_token="a", refresh_token="r", expires_at=123.0),
            )
            auth.save_tokens(str(path))

    asyncio.run(_save())
    loaded = AuthManager.load_tokens(str(path))
    assert loaded is not None
    assert loaded["access_token"] == "a"
    assert loaded["refresh_token"] == "r"

    # Corrupt file
    path.write_text("not-json", encoding="utf-8")
    assert AuthManager.load_tokens(str(path)) is None

    # Non-dict JSON
    path.write_text("[1,2]", encoding="utf-8")
    assert AuthManager.load_tokens(str(path)) is None


def test_get_login_url_contains_client_and_scope():
    async def _run() -> str:
        async with aiohttp.ClientSession() as session:
            return AuthManager(session, {}).get_login_url()

    url = asyncio.run(_run())
    assert "client_id=" in url
    assert "authorize" in url
    assert "response_type=code" in url


# ---------------------------------------------------------------------------
# exchange_code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exchange_code_success(aresponses):
    _token_response(aresponses)
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        await auth.exchange_code("auth-code-xyz")
        assert auth.export_tokens().access_token == "new_access"
        assert auth.is_authenticated


@pytest.mark.asyncio
async def test_exchange_code_invalid_grant(aresponses):
    _token_response(aresponses, status=400, body='{"error":"invalid_grant"}')
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        with pytest.raises(DimplexAuthInvalidGrantError):
            await auth.exchange_code("bad-code")


# ---------------------------------------------------------------------------
# B2C page parse + cookie header
# ---------------------------------------------------------------------------


def test_parse_b2c_login_page_extracts_fields():
    """CSRF/transId parsing from a minimal B2C HTML snippet."""
    fields = AuthManager._parse_b2c_login_page(LOGIN_HTML, AUTHORIZE_URL)
    assert fields["csrf"] == "csrf-token-value"
    assert "StateProperties=abc123" in fields["tx"]
    assert fields["post_url"].endswith("SelfAsserted?tx=StateProperties=abc123&p=B2C_1A_DimplexControlSignupSignin")
    assert fields["confirmed_url"].endswith("/api/CombinedSigninAndSignup/confirmed")
    assert fields["p"] == B2C_POLICY


def test_parse_b2c_login_page_missing_csrf():
    with pytest.raises(DimplexAuthParseError) as exc_info:
        AuthManager._parse_b2c_login_page("<html></html>", AUTHORIZE_URL)
    assert exc_info.value.code == "parse_error"


def test_parse_b2c_login_page_missing_trans_id():
    html = '<script>var SETTINGS = {"csrf":"only-csrf"};</script>'
    with pytest.raises(DimplexAuthParseError):
        AuthManager._parse_b2c_login_page(html, AUTHORIZE_URL)


def test_parse_b2c_login_page_fallback_base_url():
    """When authorize path is absent, build base from netloc + policy."""
    page_url = "https://gdhvb2c.b2clogin.com/some/other/path"
    fields = AuthManager._parse_b2c_login_page(LOGIN_HTML, page_url)
    assert B2C_POLICY in fields["post_url"]
    assert fields["post_url"].startswith("https://gdhvb2c.b2clogin.com/")


def test_build_cookie_header_unquoted():
    jar = MagicMock()
    c1 = MagicMock()
    c1.key = "x"
    c1.value = "a+b=c"
    c2 = MagicMock()
    c2.key = "y"
    c2.value = "plain"
    filtered = MagicMock()
    filtered.values.return_value = [c1, c2]
    jar.filter_cookies.return_value = filtered
    header = AuthManager._build_cookie_header(jar, "https://example.com/")
    assert header == "x=a+b=c; y=plain"
    jar.filter_cookies.assert_called_once()


# ---------------------------------------------------------------------------
# headless_login
# ---------------------------------------------------------------------------


def _add_login_page(aresponses, *, status: int = 200, html: str = LOGIN_HTML) -> None:
    aresponses.add(
        B2C_HOST,
        AUTHORIZE_PATH,
        "GET",
        aresponses.Response(status=status, text=html, headers={"Content-Type": "text/html"}),
    )


def _add_self_asserted(
    aresponses,
    *,
    status: int = 200,
    body: str = '{"status":"200"}',
    set_cookie: str | None = None,
) -> None:
    headers = {"Content-Type": "application/json"}
    if set_cookie:
        headers["Set-Cookie"] = set_cookie
    aresponses.add(
        B2C_HOST,
        SELF_ASSERTED_PATH,
        "POST",
        aresponses.Response(status=status, body=body, headers=headers),
    )


def _add_confirmed_redirect(aresponses, location: str) -> None:
    aresponses.add(
        B2C_HOST,
        CONFIRMED_PATH,
        "GET",
        aresponses.Response(status=302, headers={"Location": location}),
    )


@pytest.mark.asyncio
async def test_headless_login_happy_path(aresponses):
    """Full B2C path: login page → credentials → MSAL redirect → token exchange."""
    _add_login_page(aresponses)
    _add_self_asserted(aresponses, set_cookie="session=abc; Path=/")
    _add_confirmed_redirect(aresponses, f"{REDIRECT_URI}?code=authcode123")
    _token_response(aresponses)

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        await auth.headless_login("user@example.com", "secret")
        assert auth.export_tokens().access_token == "new_access"
        assert auth.is_authenticated


@pytest.mark.asyncio
async def test_headless_login_invalid_credentials(aresponses):
    _add_login_page(aresponses)
    _add_self_asserted(aresponses, body='{"status":"400"}')

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        with pytest.raises(DimplexAuthInvalidCredentialsError) as exc_info:
            await auth.headless_login("user@example.com", "wrong")
        assert exc_info.value.reauth_required is True
        assert exc_info.value.code == "invalid_credentials"


@pytest.mark.asyncio
async def test_headless_login_redirect_hop_exhaustion(aresponses):
    _add_login_page(aresponses)
    _add_self_asserted(aresponses)
    # Always redirect to another B2C hop — never the MSAL scheme.
    for _ in range(25):
        aresponses.add(
            B2C_HOST,
            re.compile(r".*"),
            "GET",
            aresponses.Response(
                status=302,
                headers={"Location": "https://gdhvb2c.b2clogin.com/tfp/loop"},
            ),
        )

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        with pytest.raises(DimplexAuthTransientError) as exc_info:
            await auth.headless_login("user@example.com", "secret")
        assert exc_info.value.code == "redirect_exhausted"


@pytest.mark.asyncio
async def test_headless_login_missing_code_on_msal_redirect(aresponses):
    _add_login_page(aresponses)
    _add_self_asserted(aresponses)
    _add_confirmed_redirect(aresponses, f"{REDIRECT_URI}?error=access_denied")

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        with pytest.raises(DimplexAuthParseError):
            await auth.headless_login("user@example.com", "secret")


@pytest.mark.asyncio
async def test_headless_login_code_embedded_in_200_html(aresponses):
    _add_login_page(aresponses)
    _add_self_asserted(aresponses)
    html_body = f'<html><a href="{REDIRECT_URI}?code=fromhtml">continue</a></html>'
    aresponses.add(
        B2C_HOST,
        CONFIRMED_PATH,
        "GET",
        aresponses.Response(status=200, text=html_body),
    )
    _token_response(aresponses)

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        await auth.headless_login("user@example.com", "secret")
        assert auth.export_tokens().access_token == "new_access"


@pytest.mark.asyncio
async def test_headless_login_page_http_error(aresponses):
    _add_login_page(aresponses, status=503, html="down")
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        with pytest.raises(DimplexAuthTransientError):
            await auth.headless_login("user@example.com", "secret")


@pytest.mark.asyncio
async def test_headless_login_bad_login_html(aresponses):
    _add_login_page(aresponses, html="<html>no settings</html>")
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        with pytest.raises(DimplexAuthParseError):
            await auth.headless_login("user@example.com", "secret")


@pytest.mark.asyncio
async def test_headless_login_relative_redirect(aresponses):
    _add_login_page(aresponses)
    _add_self_asserted(aresponses)
    # First hop: relative location, second hop: MSAL with code
    aresponses.add(
        B2C_HOST,
        CONFIRMED_PATH,
        "GET",
        aresponses.Response(status=302, headers={"Location": "/next-hop"}),
    )
    aresponses.add(
        B2C_HOST,
        "/next-hop",
        "GET",
        aresponses.Response(status=302, headers={"Location": f"{REDIRECT_URI}?code=relcode"}),
    )
    _token_response(aresponses)

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        await auth.headless_login("user@example.com", "secret")
        assert auth.export_tokens().access_token == "new_access"


@pytest.mark.asyncio
async def test_headless_login_redirect_without_location(aresponses):
    _add_login_page(aresponses)
    _add_self_asserted(aresponses)
    aresponses.add(
        B2C_HOST,
        CONFIRMED_PATH,
        "GET",
        aresponses.Response(status=302, headers={}),
    )
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        with pytest.raises(DimplexAuthParseError):
            await auth.headless_login("user@example.com", "secret")


@pytest.mark.asyncio
async def test_headless_login_credential_post_5xx(aresponses):
    _add_login_page(aresponses)
    _add_self_asserted(aresponses, status=502, body="bad gateway")
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        with pytest.raises(DimplexAuthTransientError):
            await auth.headless_login("user@example.com", "secret")


# ---------------------------------------------------------------------------
# logging hygiene: INFO must not include raw codes/tokens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exchange_code_logs_do_not_include_full_code(aresponses, caplog):
    _token_response(aresponses, status=400, body='{"error":"invalid_grant","error_description":"bad"}')
    with caplog.at_level(logging.INFO, logger="dimplex_controller.auth"):
        async with aiohttp.ClientSession() as session:
            auth = AuthManager(session, {})
            with pytest.raises(DimplexAuthInvalidGrantError):
                await auth.exchange_code("super-secret-auth-code-value")
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "super-secret-auth-code-value" not in joined
