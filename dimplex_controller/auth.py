import json
import logging
import os
import re
import time
from typing import Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp
from bs4 import BeautifulSoup

from .const import (
    AUTH_URL,
    B2C_POLICY,
    CLIENT_ID,
    HTTP_OK,
    REDIRECT_URI,
    SCOPE,
)
from .exceptions import DimplexAuthError

_LOGGER = logging.getLogger(__name__)


class AuthManager:
    """Manages authentication for Dimplex Control."""

    def __init__(self, session: aiohttp.ClientSession, token_data: Optional[Dict] = None):
        """Initialize the auth manager."""
        self._session = session
        self._access_token: Optional[str] = token_data.get("access_token") if token_data else None
        self._refresh_token: Optional[str] = token_data.get("refresh_token") if token_data else None
        self._expires_at: float = token_data.get("expires_at", 0) if token_data else 0

    @property
    def is_authenticated(self) -> bool:
        """Check if we have a valid access token."""
        return self._access_token is not None and time.time() < self._expires_at

    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if not self._refresh_token:
            raise DimplexAuthError("No refresh token available. User must authenticate first.")

        if self.is_authenticated:
            return self._access_token

        # Token expired or missing, try refresh
        await self.refresh_tokens()
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

        async with self._session.post(f"{AUTH_URL}/token", data=payload) as resp:
            if resp.status != HTTP_OK:
                text = await resp.text()
                _LOGGER.error("Failed to refresh token: %s", text)
                raise DimplexAuthError(f"Failed to refresh token: {resp.status} - {text}")

            data = await resp.json()
            self._update_tokens(data)

    def _update_tokens(self, data: Dict) -> None:
        """Update internal token state from API response."""
        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        expires_in = data.get("expires_in", 3600)
        self._expires_at = time.time() + expires_in - 60  # Buffer 60s

    def get_login_url(self) -> str:
        """Generate the login URL for the user to visit."""
        # Note: This is a simplified URL generation.
        # In a real app, we might need state, nonce, code_challenge (PKCE).
        # Based on logs, iOS app uses standard OAuth2.
        # Constructing a URL for manual copy-paste might be tricky if it strictly requires a custom scheme redirect.
        # But we can try the standard authorize endpoint.

        params = {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "response_mode": "query",
        }
        from urllib.parse import urlencode

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

        _LOGGER.info(f"Exchanging code for tokens at {AUTH_URL}/token")
        client_id = payload["client_id"]
        redirect_uri = payload["redirect_uri"]
        code_preview = code[:10]
        _LOGGER.info(f"Payload: client_id={client_id}, redirect_uri={redirect_uri}, " f"code={code_preview}...")

        async with self._session.post(f"{AUTH_URL}/token", data=payload) as resp:
            _LOGGER.info(f"Token exchange response status: {resp.status}")
            if resp.status != HTTP_OK:
                text = await resp.text()
                _LOGGER.error(f"Token exchange failed: {text}")
                raise DimplexAuthError(f"Failed to exchange code: {text}")

            data = await resp.json()
            self._update_tokens(data)

    @staticmethod
    def _build_cookie_header(cookie_jar, url: str) -> str:
        """Build an unquoted Cookie header from an aiohttp cookie jar.

        Python's http.cookies wraps values containing +, /, or = in
        double-quotes, but Azure AD B2C expects raw unquoted values.
        """
        filtered = cookie_jar.filter_cookies(url)
        return "; ".join(f"{m.key}={m.value}" for m in filtered.values())

    @staticmethod
    def _parse_b2c_login_page(html: str, page_url: str) -> dict:
        """Extract B2C form fields from the login page HTML.

        Returns a dict with csrf, tx, p, post_url, confirmed_url.
        Raises DimplexAuthError if required fields cannot be found.
        """
        csrf_match = re.search(r'"csrf"\s*:\s*"([^"]+)"', html)
        if not csrf_match:
            raise DimplexAuthError("Could not find CSRF token in B2C login page")
        csrf = csrf_match.group(1)

        tx_match = re.search(r'"transId"\s*:\s*"([^"]+)"', html)
        if not tx_match:
            raise DimplexAuthError("Could not find transId in B2C login page")
        tx = tx_match.group(1)

        # Build base URL by stripping the authorize endpoint.
        # The B2C login page URL contains /tfp/{tenant}/{policy}/oauth2/v2.0/authorize
        # and may redirect to /{tenant}/{policy}/oauth2/v2.0/authorize
        if "/oauth2/v2.0/authorize" in page_url:
            base_url = page_url.split("/oauth2/v2.0/authorize")[0]
        else:
            parsed = urlparse(page_url)
            base_url = (
                f"{parsed.scheme}://{parsed.netloc}"
                f"/gdhvb2c.onmicrosoft.com/{B2C_POLICY}"
            )

        return {
            "csrf": csrf,
            "tx": tx,
            "p": B2C_POLICY,
            "post_url": f"{base_url}/SelfAsserted?tx={tx}&p={B2C_POLICY}",
            "confirmed_url": (
                f"{base_url}/api/CombinedSigninAndSignup/confirmed"
            ),
        }
    async def headless_login(self, email: str, password: str) -> None:
        """Perform a headless login via Azure AD B2C to obtain tokens.

        Uses direct HTTP credential submission so users don't need to
        manually extract auth codes from browser network traffic.
        """
        jar = aiohttp.CookieJar(unsafe=True)
        start_url = self.get_login_url()

        async with aiohttp.ClientSession(cookie_jar=jar) as session:
            # Step 1: GET the auth URI, follow redirects to B2C login page
            _LOGGER.debug("Fetching B2C login page: %s", start_url)
            async with session.get(start_url, allow_redirects=True) as resp:
                login_html = await resp.text()
                page_url = str(resp.url)
                if resp.status != HTTP_OK:
                    raise DimplexAuthError(
                        f"B2C login page returned HTTP {resp.status}"
                    )

            # Step 2: Parse the login page for CSRF, transaction ID, policy
            fields = self._parse_b2c_login_page(login_html, page_url)
            _LOGGER.debug(
                "Parsed B2C login page: csrf=%s... tx=%s... p=%s",
                fields["csrf"][:16],
                fields["tx"][:40],
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
            _LOGGER.debug(
                "Submitting credentials to %s", fields["post_url"]
            )

            # Use DummyCookieJar so POST response cookies aren't
            # re-injected with quoted values on the next request.
            async with aiohttp.ClientSession(
                cookie_jar=aiohttp.DummyCookieJar(),
            ) as raw_session:
                async with raw_session.post(
                    fields["post_url"],
                    data=post_data,
                    headers=post_headers,
                    allow_redirects=False,
                ) as resp:
                    body = await resp.text()
                    if resp.status != HTTP_OK:
                        raise DimplexAuthError(
                            f"Credential submission returned HTTP {resp.status}"
                        )
                    try:
                        resp_data = json.loads(body)
                        if str(resp_data.get("status")) == "400":
                            raise DimplexAuthError("Invalid email or password")
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
                    cookie_header = "; ".join(
                        f"{n}={v}" for n, v in cookies.items()
                    )

                # Step 4: GET the confirmed endpoint and follow redirects
                confirmed_qs = (
                    f"rememberMe=false"
                    f"&csrf_token={fields['csrf']}"
                    f"&tx={fields['tx']}"
                    f"&p={fields['p']}"
                )
                next_url: str = fields["confirmed_url"] + "?" + confirmed_qs
                confirmed_headers = {"Cookie": cookie_header}

                for _ in range(20):  # max redirect hops
                    _LOGGER.debug("Following redirect: %s", next_url[:120])
                    async with raw_session.get(
                        next_url,
                        headers=confirmed_headers,
                        allow_redirects=False,
                    ) as resp:
                        resp_body = await resp.text()
                        if resp.status in (301, 302, 303, 307, 308):
                            location = resp.headers.get("Location", "")
                            if not location:
                                raise DimplexAuthError(
                                    "Redirect without Location header"
                                )
                            if location.startswith(REDIRECT_URI) and (
                                len(location) == len(REDIRECT_URI)
                                or location[len(REDIRECT_URI)] in ("?", "/")
                            ):
                                _LOGGER.debug(
                                    "Captured redirect with code: %s...",
                                    location[:120],
                                )
                                parsed = urlparse(location)
                                query = parse_qs(parsed.query)
                                code = query.get("code", [""])[0]
                                if not code:
                                    raise DimplexAuthError(
                                        "Redirect URL missing auth code"
                                    )
                                await self.exchange_code(code)
                                return
                            if not location.startswith("http"):
                                location = (
                                    f"{parsed_page.scheme}://{parsed_page.netloc}"
                                    + location
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
                            raise DimplexAuthError(
                                "Reached 200 response without finding redirect URL"
                            )
                        raise DimplexAuthError(
                            f"Unexpected HTTP {resp.status} during redirect chain"
                        )

            raise DimplexAuthError(
                "Exceeded maximum redirect hops without capturing auth code"
            )

    def save_tokens(self, file_path: str) -> None:
        """Save current tokens to a JSON file."""
        data = {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "expires_at": self._expires_at,
        }
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
        _LOGGER.info("Tokens saved to %s", file_path)

    @classmethod
    def load_tokens(cls, file_path: str) -> Optional[Dict]:
        """Load tokens from a JSON file."""
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            _LOGGER.error("Failed to load tokens from %s: %s", file_path, e)
            return None
