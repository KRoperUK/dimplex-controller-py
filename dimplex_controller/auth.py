from __future__ import annotations

import inspect
import json
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp

from .const import (
    AUTH_URL,
    B2C_POLICY,
    CLIENT_ID,
    HTTP_OK,
    REDIRECT_URI,
    SCOPE,
)
from .exceptions import (
    DimplexAuthError,
    DimplexAuthInvalidCredentialsError,
    DimplexAuthInvalidGrantError,
    DimplexAuthParseError,
    DimplexAuthTransientError,
    classify_oauth_token_error,
    oauth_error_summary,
)

_LOGGER = logging.getLogger(__name__)

TokenListener = Callable[["TokenBundle"], Awaitable[None] | None]

# Max redirect hops while capturing the MSAL auth-code redirect.
_MAX_REDIRECT_HOPS = 20


@dataclass(frozen=True, slots=True)
class TokenBundle:
    """Public, serialisable snapshot of auth tokens."""

    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        """Return a plain dict suitable for JSON / config-entry storage."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> TokenBundle:
        """Build a bundle from a dict-like token store."""
        if not data:
            return cls()
        return cls(
            access_token=data.get("access_token"),
            refresh_token=data.get("refresh_token"),
            expires_at=float(data.get("expires_at") or 0),
        )


class AuthManager:
    """Manages authentication for Dimplex Control."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token_data: dict[str, Any] | TokenBundle | None = None,
        *,
        on_token_update: TokenListener | None = None,
    ):
        """Initialize the auth manager."""
        self._session = session
        self._on_token_update = on_token_update
        bundle = token_data if isinstance(token_data, TokenBundle) else TokenBundle.from_mapping(token_data)
        self._access_token: str | None = bundle.access_token
        self._refresh_token: str | None = bundle.refresh_token
        self._expires_at: float = bundle.expires_at

    @property
    def is_authenticated(self) -> bool:
        """Check if we have a valid access token."""
        return self._access_token is not None and time.time() < self._expires_at

    def export_tokens(self) -> TokenBundle:
        """Return the current token snapshot (safe for persistence)."""
        return TokenBundle(
            access_token=self._access_token,
            refresh_token=self._refresh_token,
            expires_at=self._expires_at,
        )

    def apply_tokens(self, bundle: TokenBundle | dict[str, Any]) -> None:
        """Replace in-memory tokens from a :class:`TokenBundle` or dict."""
        if not isinstance(bundle, TokenBundle):
            bundle = TokenBundle.from_mapping(bundle)
        self._access_token = bundle.access_token
        self._refresh_token = bundle.refresh_token
        self._expires_at = bundle.expires_at

    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if not self._refresh_token:
            raise DimplexAuthInvalidGrantError(
                "No refresh token available. User must authenticate first.",
                code="missing_refresh_token",
            )

        if self.is_authenticated:
            assert self._access_token is not None
            return self._access_token

        # Token expired or missing, try refresh
        await self.refresh_tokens()
        if not self._access_token:
            raise DimplexAuthInvalidGrantError(
                "Token refresh succeeded but no access token was returned.",
                code="missing_access_token",
            )
        return self._access_token

    async def refresh_tokens(self) -> None:
        """Refresh the access token using the refresh token."""
        _LOGGER.debug("Refreshing access token")
        payload = {
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "scope": SCOPE,
            "client_info": "1",
        }

        try:
            async with self._session.post(f"{AUTH_URL}/token", data=payload) as resp:
                if resp.status != HTTP_OK:
                    text = await resp.text()
                    _LOGGER.error(
                        "Failed to refresh token: HTTP %s (%s)",
                        resp.status,
                        _safe_error_summary(text),
                    )
                    raise classify_oauth_token_error(resp.status, text)

                data = await resp.json()
                await self._update_tokens(data)
        except DimplexAuthError:
            raise
        except aiohttp.ClientError as exc:
            raise DimplexAuthTransientError(
                f"Network error while refreshing token: {type(exc).__name__}",
                details=str(exc)[:200],
            ) from exc

    async def _update_tokens(self, data: dict[str, Any]) -> None:
        """Update internal token state from API response."""
        self._access_token = data.get("access_token")
        # Some refresh responses omit a new refresh token — keep the old one.
        if data.get("refresh_token"):
            self._refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in", 3600)
        self._expires_at = time.time() + float(expires_in) - 60  # Buffer 60s
        if self._on_token_update is not None:
            result = self._on_token_update(self.export_tokens())
            if inspect.isawaitable(result):
                await result

    def save_tokens(self, file_path: str) -> None:
        """Save current tokens to a JSON file."""
        data = self.export_tokens().as_dict()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        _LOGGER.info("Tokens saved to %s", file_path)

    @classmethod
    def load_tokens(cls, file_path: str) -> dict[str, Any] | None:
        """Load tokens from a JSON file."""
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            return None
        except Exception as e:
            _LOGGER.error("Failed to load tokens from %s: %s", file_path, type(e).__name__)
            return None

    def get_login_url(self) -> str:
        """Generate the login URL for the user to visit."""
        params = {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "response_mode": "query",
        }
        return f"{AUTH_URL}/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str) -> None:
        """Exchange authorization code for tokens."""
        payload = {
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
        }

        _LOGGER.debug("Exchanging authorization code for tokens")
        try:
            async with self._session.post(f"{AUTH_URL}/token", data=payload) as resp:
                if resp.status != HTTP_OK:
                    text = await resp.text()
                    _LOGGER.error(
                        "Token exchange failed: HTTP %s (%s)",
                        resp.status,
                        _safe_error_summary(text),
                    )
                    raise classify_oauth_token_error(resp.status, text)

                data = await resp.json()
                await self._update_tokens(data)
        except DimplexAuthError:
            raise
        except aiohttp.ClientError as exc:
            raise DimplexAuthTransientError(
                f"Network error while exchanging code: {type(exc).__name__}",
                details=str(exc)[:200],
            ) from exc

    @staticmethod
    def _build_cookie_header(cookie_jar: Any, url: str) -> str:
        """Build an unquoted Cookie header from an aiohttp cookie jar.

        Python's http.cookies wraps values containing +, /, or = in
        double-quotes, but Azure AD B2C expects raw unquoted values.
        """
        filtered = cookie_jar.filter_cookies(url)
        return "; ".join(f"{m.key}={m.value}" for m in filtered.values())

    @staticmethod
    def _parse_b2c_login_page(html: str, page_url: str) -> dict[str, str]:
        """Extract B2C form fields from the login page HTML.

        Returns a dict with csrf, tx, p, post_url, confirmed_url.
        Raises DimplexAuthParseError if required fields cannot be found.
        """
        csrf_match = re.search(r'"csrf"\s*:\s*"([^"]+)"', html)
        if not csrf_match:
            raise DimplexAuthParseError("Could not find CSRF token in B2C login page")
        csrf = csrf_match.group(1)

        tx_match = re.search(r'"transId"\s*:\s*"([^"]+)"', html)
        if not tx_match:
            raise DimplexAuthParseError("Could not find transId in B2C login page")
        tx = tx_match.group(1)

        # Build base URL by stripping the authorize endpoint.
        # The B2C login page URL contains /tfp/{tenant}/{policy}/oauth2/v2.0/authorize
        # and may redirect to /{tenant}/{policy}/oauth2/v2.0/authorize
        if "/oauth2/v2.0/authorize" in page_url:
            base_url = page_url.split("/oauth2/v2.0/authorize")[0]
        else:
            parsed = urlparse(page_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}/gdhvb2c.onmicrosoft.com/{B2C_POLICY}"

        return {
            "csrf": csrf,
            "tx": tx,
            "p": B2C_POLICY,
            "post_url": f"{base_url}/SelfAsserted?tx={tx}&p={B2C_POLICY}",
            "confirmed_url": f"{base_url}/api/CombinedSigninAndSignup/confirmed",
        }

    async def headless_login(self, email: str, password: str) -> None:
        """Perform a headless login via Azure AD B2C to obtain tokens.

        Uses direct HTTP credential submission so users don't need to
        manually extract auth codes from browser network traffic.
        """
        jar = aiohttp.CookieJar(unsafe=True)
        start_url = self.get_login_url()

        try:
            async with aiohttp.ClientSession(cookie_jar=jar) as session:
                # Step 1: GET the auth URI, follow redirects to B2C login page
                _LOGGER.debug("Fetching B2C login page")
                try:
                    async with session.get(start_url, allow_redirects=True) as resp:
                        login_html = await resp.text()
                        page_url = str(resp.url)
                        if resp.status != HTTP_OK:
                            if resp.status >= 500:
                                raise DimplexAuthTransientError(
                                    f"B2C login page returned HTTP {resp.status}",
                                    status=resp.status,
                                )
                            raise DimplexAuthError(
                                f"B2C login page returned HTTP {resp.status}",
                                status=resp.status,
                                reauth_required=False,
                            )
                except aiohttp.ClientError as exc:
                    raise DimplexAuthTransientError(
                        f"Network error fetching B2C login page: {type(exc).__name__}",
                        details=str(exc)[:200],
                    ) from exc

                # Step 2: Parse the login page for CSRF, transaction ID, policy
                fields = self._parse_b2c_login_page(login_html, page_url)
                _LOGGER.debug(
                    "Parsed B2C login page (csrf_len=%s tx_len=%s p=%s)",
                    len(fields["csrf"]),
                    len(fields["tx"]),
                    fields["p"],
                )

                # Step 3: POST credentials to SelfAsserted endpoint
                post_data = {
                    "request_type": "RESPONSE",
                    "email": email,
                    "password": password,
                }
                parsed_page = urlparse(page_url)
                origin = f"{parsed_page.scheme}://{parsed_page.netloc}"
                post_headers = {
                    "X-CSRF-TOKEN": fields["csrf"],
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": page_url,
                    "Origin": origin,
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                }

                # Build an unquoted Cookie header — aiohttp wraps values
                # containing +/= in double-quotes, but B2C requires raw values.
                cookie_header = self._build_cookie_header(jar, fields["post_url"])
                post_headers["Cookie"] = cookie_header
                _LOGGER.debug("Submitting credentials to SelfAsserted endpoint")

                # Use DummyCookieJar so POST response cookies aren't
                # re-injected with quoted values on the next request.
                async with aiohttp.ClientSession(
                    cookie_jar=aiohttp.DummyCookieJar(),
                ) as raw_session:
                    try:
                        async with raw_session.post(
                            fields["post_url"],
                            data=post_data,
                            headers=post_headers,
                            allow_redirects=False,
                        ) as resp:
                            body = await resp.text()
                            if resp.status != HTTP_OK:
                                if resp.status >= 500:
                                    raise DimplexAuthTransientError(
                                        f"Credential submission returned HTTP {resp.status}",
                                        status=resp.status,
                                    )
                                raise DimplexAuthError(
                                    f"Credential submission returned HTTP {resp.status}",
                                    status=resp.status,
                                )
                            try:
                                resp_data = json.loads(body)
                                if str(resp_data.get("status")) == "400":
                                    raise DimplexAuthInvalidCredentialsError("Invalid email or password")
                            except json.JSONDecodeError:
                                pass

                            # Merge POST response cookies into the cookie header
                            cookies: dict[str, str] = {}
                            for part in cookie_header.split("; "):
                                if "=" in part:
                                    n, v = part.split("=", 1)
                                    cookies[n] = v
                            for raw_sc in resp.headers.getall("Set-Cookie", []):
                                sc_pair = raw_sc.split(";", 1)[0]
                                if "=" in sc_pair:
                                    n, v = sc_pair.split("=", 1)
                                    cookies[n] = v
                            cookie_header = "; ".join(f"{n}={v}" for n, v in cookies.items())
                    except DimplexAuthError:
                        raise
                    except aiohttp.ClientError as exc:
                        raise DimplexAuthTransientError(
                            f"Network error submitting credentials: {type(exc).__name__}",
                            details=str(exc)[:200],
                        ) from exc

                    # Step 4: GET the confirmed endpoint and follow redirects
                    confirmed_qs = f"rememberMe=false&csrf_token={fields['csrf']}&tx={fields['tx']}&p={fields['p']}"
                    next_url: str = fields["confirmed_url"] + "?" + confirmed_qs
                    confirmed_headers = {"Cookie": cookie_header}

                    for _ in range(_MAX_REDIRECT_HOPS):
                        _LOGGER.debug("Following B2C redirect hop")
                        try:
                            async with raw_session.get(
                                next_url,
                                headers=confirmed_headers,
                                allow_redirects=False,
                            ) as resp:
                                resp_body = await resp.text()
                                if resp.status in (301, 302, 303, 307, 308):
                                    location = resp.headers.get("Location", "")
                                    if not location:
                                        raise DimplexAuthParseError("Redirect without Location header")
                                    if location.startswith(REDIRECT_URI) and (
                                        len(location) == len(REDIRECT_URI) or location[len(REDIRECT_URI)] in ("?", "/")
                                    ):
                                        parsed = urlparse(location)
                                        query = parse_qs(parsed.query)
                                        code = query.get("code", [""])[0]
                                        if not code:
                                            raise DimplexAuthParseError("Redirect URL missing auth code")
                                        await self.exchange_code(code)
                                        return
                                    if not location.startswith("http"):
                                        location = (
                                            f"{parsed_page.scheme}://{parsed_page.netloc}" + location
                                            if location.startswith("/")
                                            else location
                                        )
                                    next_url = location
                                    continue
                                if resp.status == HTTP_OK:
                                    redirect_match = re.search(
                                        rf"({re.escape(REDIRECT_URI)}\?[^\s\"'<]+)",
                                        resp_body,
                                    )
                                    if redirect_match:
                                        parsed = urlparse(redirect_match.group(1))
                                        query = parse_qs(parsed.query)
                                        code = query.get("code", [""])[0]
                                        if code:
                                            await self.exchange_code(code)
                                            return
                                    raise DimplexAuthParseError("Reached 200 response without finding redirect URL")
                                if resp.status >= 500:
                                    raise DimplexAuthTransientError(
                                        f"Unexpected HTTP {resp.status} during redirect chain",
                                        status=resp.status,
                                    )
                                raise DimplexAuthError(
                                    f"Unexpected HTTP {resp.status} during redirect chain",
                                    status=resp.status,
                                )
                        except DimplexAuthError:
                            raise
                        except aiohttp.ClientError as exc:
                            raise DimplexAuthTransientError(
                                f"Network error during redirect chain: {type(exc).__name__}",
                                details=str(exc)[:200],
                            ) from exc

                    raise DimplexAuthTransientError(
                        "Exceeded maximum redirect hops without capturing auth code",
                        code="redirect_exhausted",
                    )
        except DimplexAuthError:
            raise


def _safe_error_summary(body: str) -> str:
    """Summarise an OAuth error body without echoing secrets."""
    return oauth_error_summary(body)
