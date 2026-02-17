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
