"""Exception hierarchy with credential-safe HTTP diagnostics."""

from __future__ import annotations


class UfanetError(Exception):
    """Base error raised by this package."""


class AuthenticationError(UfanetError):
    """Authentication was rejected or the expected session was not established."""


class ParseError(UfanetError):
    """A service response did not match the observed response structure."""


class UnsupportedOperationError(UfanetError):
    """The available endpoint behavior is not known well enough to perform safely."""


class HTTPError(UfanetError):
    """Non-success HTTP response. URL query parameters are deliberately omitted."""

    def __init__(self, status: int, method: str, path: str, body: str = "") -> None:
        self.status = status
        self.method = method
        self.path = path.split("?", maxsplit=1)[0]
        self.body = body[:500]
        super().__init__(f"HTTP {status} for {method} {self.path}: {self.body}")
