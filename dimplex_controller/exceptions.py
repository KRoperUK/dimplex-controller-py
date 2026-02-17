"""Exceptions for Dimplex Controller."""


class DimplexError(Exception):
    """Base exception for Dimplex Controller."""


class DimplexAuthError(DimplexError):
    """Exception for authentication errors."""


class DimplexApiError(DimplexError):
    """Exception for API errors."""

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"API Error {status}: {message}")


class DimplexConnectionError(DimplexError):
    """Exception for connection errors."""
