"""Exceptions for Dimplex Controller."""

from __future__ import annotations

import json
from typing import Any


class DimplexError(Exception):
    """Base exception for Dimplex Controller."""


class DimplexAuthError(DimplexError):
    """Authentication or token lifecycle failure.

    Attributes:
        code: Stable machine-readable identifier (e.g. ``invalid_grant``).
        reauth_required: Caller should prompt for credentials / full login again.
        transient: Failure may succeed on retry (network, 5xx, rate limit).
        status: Optional HTTP status from the auth endpoint.
        details: Optional short server message (never a full token).
    """

    code: str = "auth_error"
    reauth_required: bool = False
    transient: bool = False

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        reauth_required: bool | None = None,
        transient: bool | None = None,
        status: int | None = None,
        details: str | None = None,
    ) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        if reauth_required is not None:
            self.reauth_required = reauth_required
        if transient is not None:
            self.transient = transient
        self.status = status
        self.details = details


class DimplexAuthInvalidGrantError(DimplexAuthError):
    """Refresh token or authorization code rejected; full re-login required."""

    code = "invalid_grant"
    reauth_required = True
    transient = False


class DimplexAuthInvalidCredentialsError(DimplexAuthError):
    """Email/password rejected by B2C."""

    code = "invalid_credentials"
    reauth_required = True
    transient = False


class DimplexAuthParseError(DimplexAuthError):
    """Could not parse B2C HTML or OAuth redirect payloads."""

    code = "parse_error"
    reauth_required = False
    transient = False


class DimplexAuthTransientError(DimplexAuthError):
    """Temporary auth infrastructure failure; retry may help."""

    code = "transient"
    reauth_required = False
    transient = True


class DimplexApiError(DimplexError):
    """Exception for API errors."""

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"API Error {status}: {message}")


class DimplexConnectionError(DimplexError):
    """Exception for connection errors."""


def classify_oauth_token_error(status: int, body: str) -> DimplexAuthError:
    """Map an OAuth token-endpoint failure to a structured :class:`DimplexAuthError`.

    Callers can use ``error.reauth_required`` vs ``error.transient`` to decide
    whether to open a reauth flow or retry later.
    """
    error_code, description = _parse_oauth_error_body(body)
    detail = description or _truncate(body, 200)

    if status >= 500 or status == 429:
        return DimplexAuthTransientError(
            f"Auth endpoint temporarily unavailable (HTTP {status})",
            status=status,
            details=detail,
        )

    if error_code in {"invalid_grant", "invalid_token", "expired_token"}:
        return DimplexAuthInvalidGrantError(
            f"Refresh/authorization grant rejected: {error_code}",
            status=status,
            details=detail,
        )

    if error_code in {"invalid_client", "unauthorized_client"}:
        return DimplexAuthInvalidGrantError(
            f"OAuth client rejected: {error_code}",
            status=status,
            details=detail,
        )

    if status in {400, 401, 403}:
        # Treat remaining client errors as needing a fresh login rather than a silent retry.
        return DimplexAuthInvalidGrantError(
            f"Token request failed (HTTP {status})",
            status=status,
            details=detail,
            code=error_code or "invalid_grant",
        )

    return DimplexAuthError(
        f"Token request failed (HTTP {status})",
        code=error_code or "auth_error",
        status=status,
        details=detail,
        reauth_required=False,
        transient=False,
    )


def _parse_oauth_error_body(body: str) -> tuple[str | None, str | None]:
    """Extract ``error`` / ``error_description`` from an OAuth error JSON body."""
    text = (body or "").strip()
    if not text:
        return None, None
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError:
        return None, _truncate(text, 200)
    if not isinstance(data, dict):
        return None, _truncate(text, 200)
    error = data.get("error")
    description = data.get("error_description") or data.get("error_codes")
    error_s = str(error) if error is not None else None
    if isinstance(description, list):
        description_s = ", ".join(str(x) for x in description)
    elif description is not None:
        description_s = str(description)
    else:
        description_s = None
    return error_s, _truncate(description_s, 200) if description_s else None


def oauth_error_summary(body: str) -> str:
    """Human-readable OAuth error summary safe for logs (no raw tokens)."""
    error_code, description = _parse_oauth_error_body(body)
    parts = [p for p in (error_code, description) if p]
    if parts:
        return " — ".join(parts)
    if not body:
        return "empty body"
    return f"non-json body ({len(body)} bytes)"


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    value = value.replace("\n", " ").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
