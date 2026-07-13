import aiohttp
import pytest

from dimplex_controller.auth import AuthManager
from dimplex_controller.exceptions import DimplexAuthError


@pytest.mark.asyncio
async def test_refresh_token_success(aresponses):
    """Test successful token refresh."""
    aresponses.add(
        "gdhvb2c.b2clogin.com",
        "/tfp/gdhvb2c.onmicrosoft.com/B2C_1A_DimplexControlSignupSignin/oauth2/v2.0/token",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"access_token": "new_access", "refresh_token": "new_refresh", "expires_in": 3600}',
        ),
    )

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "old_refresh"})
        await auth.refresh_tokens()

        assert auth._access_token == "new_access"
        assert auth._refresh_token == "new_refresh"
        assert auth.is_authenticated


@pytest.mark.asyncio
async def test_refresh_token_failure(aresponses):
    """Test token refresh failure."""
    aresponses.add(
        "gdhvb2c.b2clogin.com",
        "/tfp/gdhvb2c.onmicrosoft.com/B2C_1A_DimplexControlSignupSignin/oauth2/v2.0/token",
        "POST",
        aresponses.Response(
            status=400,
            body='{"error": "invalid_grant"}',
        ),
    )

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "bad_refresh"})
        with pytest.raises(DimplexAuthError):
            await auth.refresh_tokens()


@pytest.mark.asyncio
async def test_get_access_token_cached(aresponses):
    """Test getting cached access token without refresh."""
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "valid_refresh"})
        auth._access_token = "cached_token"
        auth._expires_at = 9999999999

        token = await auth.get_access_token()
        assert token == "cached_token"
        # No API call should be made


@pytest.mark.asyncio
async def test_get_access_token_no_refresh_token():
    """Test getting access token without refresh token raises error."""
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        with pytest.raises(DimplexAuthError):
            await auth.get_access_token()


@pytest.mark.asyncio
async def test_get_access_token_expired_refreshes(aresponses):
    """Test getting access token when expired triggers refresh."""
    aresponses.add(
        "gdhvb2c.b2clogin.com",
        "/tfp/gdhvb2c.onmicrosoft.com/B2C_1A_DimplexControlSignupSignin/oauth2/v2.0/token",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"access_token": "refreshed_token", "refresh_token": "new_refresh", "expires_in": 3600}',
        ),
    )

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "old_refresh"})
        auth._access_token = "old_token"
        auth._expires_at = 1  # Already expired

        token = await auth.get_access_token()
        assert token == "refreshed_token"


@pytest.mark.asyncio
async def test_is_authenticated_true():
    """Test is_authenticated returns True when ready."""
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "valid_refresh"})
        auth._access_token = "valid_token"
        auth._expires_at = 9999999999
        assert auth.is_authenticated is True


@pytest.mark.asyncio
async def test_is_authenticated_false_no_refresh():
    """Test is_authenticated returns False without refresh token."""
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        assert auth.is_authenticated is False


@pytest.mark.asyncio
async def test_is_authenticated_false_expired():
    """Test is_authenticated returns False when token expired."""
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {"refresh_token": "valid_refresh"})
        auth._access_token = "old_token"
        auth._expires_at = 1  # Expired
        assert auth.is_authenticated is False


@pytest.mark.asyncio
async def test_token_bundle_export_apply():
    """TokenBundle round-trips through export/apply without private field access."""
    from dimplex_controller.auth import TokenBundle

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(
            session,
            TokenBundle(access_token="a", refresh_token="r", expires_at=9999999999),
        )
        bundle = auth.export_tokens()
        assert bundle.access_token == "a"
        assert bundle.refresh_token == "r"
        auth.apply_tokens({"access_token": "b", "refresh_token": "r2", "expires_at": 1})
        assert auth.export_tokens().access_token == "b"
        assert auth.export_tokens().refresh_token == "r2"


@pytest.mark.asyncio
async def test_get_access_token_refreshes_when_expired(aresponses):
    """Expired access token triggers refresh via get_access_token."""
    aresponses.add(
        "gdhvb2c.b2clogin.com",
        "/tfp/gdhvb2c.onmicrosoft.com/B2C_1A_DimplexControlSignupSignin/oauth2/v2.0/token",
        "POST",
        aresponses.Response(
            status=200,
            headers={"Content-Type": "application/json"},
            body='{"access_token": "fresh", "refresh_token": "r2", "expires_in": 3600}',
        ),
    )
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(
            session,
            {"access_token": "stale", "refresh_token": "r", "expires_at": 1},
        )
        token = await auth.get_access_token()
        assert token == "fresh"
        assert auth.is_authenticated


@pytest.mark.asyncio
async def test_get_access_token_without_refresh_raises():
    """Missing refresh token is a hard auth error."""
    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session, {})
        with pytest.raises(DimplexAuthError):
            await auth.get_access_token()


def test_parse_b2c_login_page_extracts_fields():
    """CSRF/transId parsing from a minimal B2C HTML snippet."""
    html = """
    <html><script>
    var SETTINGS = {"csrf":"csrf-token-value","transId":"StateProperties=abc123"};
    </script></html>
    """
    page_url = (
        "https://gdhvb2c.b2clogin.com/tfp/gdhvb2c.onmicrosoft.com/"
        "B2C_1A_DimplexControlSignupSignin/oauth2/v2.0/authorize"
    )
    fields = AuthManager._parse_b2c_login_page(html, page_url)
    assert fields["csrf"] == "csrf-token-value"
    assert "StateProperties=abc123" in fields["tx"]
    assert fields["post_url"].endswith("SelfAsserted?tx=StateProperties=abc123&p=B2C_1A_DimplexControlSignupSignin")


def test_parse_b2c_login_page_missing_csrf():
    """Missing CSRF is a DimplexAuthError."""
    with pytest.raises(DimplexAuthError):
        AuthManager._parse_b2c_login_page("<html></html>", "https://example.com/oauth2/v2.0/authorize")
