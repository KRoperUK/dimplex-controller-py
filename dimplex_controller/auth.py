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

    async def headless_login(self, email, password) -> None:
        """Perform a headless login to obtain tokens."""
        # 1. Get the login page
        params = {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "response_mode": "query",
        }
        start_url = f"{AUTH_URL}/authorize?{urlencode(params)}"
        _LOGGER.debug(f"Fetching login page: {start_url}")

        async with self._session.get(start_url) as resp:
            html = await resp.text()
            final_url = str(resp.url)

        # 2. Extract SETTINGS and CSRF
        match = re.search(r"SETTINGS\s*=\s*({.*?});", html, re.DOTALL | re.MULTILINE)
        if not match:
            raise DimplexAuthError("Could not find SETTINGS in login page")

        try:
            settings = json.loads(match.group(1))
        except json.JSONDecodeError:
            raise DimplexAuthError("Failed to parse SETTINGS JSON from login page")

        csrf_token = settings.get("csrf")
        trans_id = settings.get("transId")

        if not csrf_token or not trans_id:
            raise DimplexAuthError("Missing csrf or transId in login page SETTINGS")

        # 3. Construct SelfAsserted URL
        if "/oauth2/v2.0/authorize" in final_url:
            base_url = final_url.split("/oauth2/v2.0/authorize")[0]
        else:
            base_url = "https://gdhvb2c.b2clogin.com/gdhvb2c.onmicrosoft.com/B2C_1A_DimplexControlSignupSignin"

        post_url = f"{base_url}/SelfAsserted"

        params = {
            "tx": trans_id,
            "p": "B2C_1A_DimplexControlSignupSignin",
        }

        post_url_with_params = f"{post_url}?{urlencode(params)}"

        # 4. Submit Credentials
        # Extract hidden fields from the form to ensure we aren't missing anything
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form", {"id": "localAccountForm"}) or soup.find("form")

        form_data = {}
        if form:
            for input_tag in form.find_all("input"):
                name = input_tag.get("name")
                value = input_tag.get("value", "")
                if name:
                    form_data[name] = value

        # Overwrite with credentials
        form_data.update(
            {
                "request_type": "RESPONSE",
                "email": email,
                "password": password,
            }
        )

        headers = {
            "X-CSRF-TOKEN": csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://gdhvb2c.b2clogin.com",
            "Referer": final_url,
        }

        _LOGGER.debug(f"Submitting credentials to {post_url_with_params}")
        # _LOGGER.debug(f"Form data: {form_data}") # Security risk to log password

        async with self._session.post(post_url_with_params, data=form_data, headers=headers) as resp:
            resp_text = await resp.text()
            _LOGGER.debug(f"Login response status: {resp.status}")

            try:
                resp_json = json.loads(resp_text)
                _LOGGER.debug(f"Login response JSON: {resp_json}")
            except json.JSONDecodeError:
                _LOGGER.debug(f"Login response Text: {resp_text}")
                raise DimplexAuthError(f"Login response was not valid JSON: {resp_text[:100]}")

            if resp_json.get("status") != "200":
                status = resp_json.get("status")
                message = resp_json.get("message") or resp_json.get("reason", "Unknown reason")
                raise DimplexAuthError(f"Login failed: {status} - {message}")

        # 5. Follow the 'Confirmed' step to get the actual code
        # After a successful SelfAsserted, we usually need to make a GET to
        # the 'CombinedSigninAndSignup' or similar endpoint to finalize the
        # flow and get the redirect to our app with the code.
        # Or, sometimes the SelfAsserted response sets a cookie and we just
        # need to hit the authorize endpoint again.

        # Let's try hitting the original authorize URL again (or the one we were redirected to).
        # Since cookies are in the session, it should now redirect us to the app with the code.

        _LOGGER.debug("Credentials accepted. Fetching authorize URL again to get code.")

        # We need to allow redirects to capture the final msauth:// url
        # aiohttp generic session checks redirects.
        # But since the scheme is custom (msal...), aiohttp might throw an error or stop.

        try:
            async with self._session.get(start_url, allow_redirects=True) as resp:
                # If we are here, it means we didn't crash on custom scheme yet,
                # or we are at a page that directs us.
                # Check history
                pass
        except aiohttp.ClientError:
            # This might happen if the redirect schema is not http/https
            # We can inspect the error or just capture it from the history if possible
            pass
        except Exception:
            # If it tries to redirect to msal..., it might fail if aiohttp doesn't support it.
            # We can disable redirects and follow manually to catch it.
            pass

        # Manual redirect following to catch custom scheme
        current_url = start_url
        code = None

        for _ in range(10):  # Max redirects
            async with self._session.get(current_url, allow_redirects=False) as resp:
                if resp.status in (302, 303, 301):
                    location = resp.headers.get("Location")
                    if not location:
                        break

                    if location.startswith(REDIRECT_URI) or "code=" in location:
                        # Success!
                        _LOGGER.debug(f"Found redirect with code: {location}")
                        # Extract code
                        parsed = urlparse(location)
                        query = parse_qs(parsed.query)
                        code = query.get("code", [""])[0]
                        break

                    current_url = location
                else:
                    break

        if not code:
            raise DimplexAuthError(
                "Failed to obtain auth code after successful login. Redirect URI might have changed."
            )

        _LOGGER.debug(f"Got code: {code[:10]}...")
        await self.exchange_code(code)

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
