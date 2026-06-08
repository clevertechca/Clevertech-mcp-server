"""Tests for authentication helpers (auth.py).

Tests IP extraction, API key retrieval from headers, upstream key
resolution, and the is_authenticated check — all using duck-typed
mock request contexts.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

# Import the functions under test (prefixed with _ since they're internal)
from clevertech_mcp.auth import (
    _extract_client_ip,
    _get_user_api_key,
    get_upstream_key,
    is_authenticated,
)


# ---------------------------------------------------------------------------
# Helpers — build mock Starlette-style request contexts
# ---------------------------------------------------------------------------

def _make_context(
    *,
    client_host: str | None = "10.0.0.1",
    forwarded_for: str | None = None,
    authorization: str | None = None,
    has_request: bool = True,
):
    """Build a duck-typed request context suitable for testing auth helpers.

    Mocks ``context.request`` with ``.headers`` and ``.client.host``.
    """
    ctx = MagicMock()
    if has_request:
        request = MagicMock()
        request.headers = {}
        if forwarded_for is not None:
            request.headers["X-Forwarded-For"] = forwarded_for
        if authorization is not None:
            request.headers["Authorization"] = authorization

        request.client = MagicMock()
        request.client.host = client_host

        ctx.request = request
    return ctx


# ===================================================================
# _extract_client_ip
# ===================================================================

class TestExtractClientIp:
    """Tests for ``_extract_client_ip``."""

    def test_extract_client_ip_from_request(self):
        """Direct client IP from request.client.host."""
        ctx = _make_context(client_host="192.168.1.100")
        assert _extract_client_ip(ctx) == "192.168.1.100"

    def test_extract_client_ip_from_forwarded_for(self):
        """X-Forwarded-For header takes priority — first entry returned."""
        ctx = _make_context(
            client_host="10.0.0.1",
            forwarded_for="203.0.113.5, 10.0.0.2, 10.0.0.3",
        )
        assert _extract_client_ip(ctx) == "203.0.113.5"

    def test_extract_client_ip_forwarded_for_single(self):
        """Single IP in X-Forwarded-For."""
        ctx = _make_context(
            client_host="10.0.0.1",
            forwarded_for="198.51.100.42",
        )
        assert _extract_client_ip(ctx) == "198.51.100.42"

    def test_extract_client_ip_no_request(self):
        """Context without a request attribute returns 'unknown'."""
        ctx = _make_context(has_request=False)
        assert _extract_client_ip(ctx) == "unknown"

    def test_extract_client_ip_no_client(self):
        """Request without client host returns 'unknown'."""
        ctx = MagicMock()
        ctx.request = MagicMock()
        ctx.request.headers = {}
        ctx.request.client = None
        assert _extract_client_ip(ctx) == "unknown"


# ===================================================================
# _get_user_api_key
# ===================================================================

class TestGetUserApiKey:
    """Tests for ``_get_user_api_key``."""

    def test_get_user_api_key_from_header(self):
        """Bearer token extracted from Authorization header."""
        ctx = _make_context(authorization="Bearer sk-abc123xyz")
        assert _get_user_api_key(ctx) == "sk-abc123xyz"

    def test_get_user_api_key_missing(self):
        """No Authorization header returns env fallback or None."""
        # Clear env var during test
        with patch.dict(os.environ, {}, clear=True):
            ctx = _make_context()  # no Authorization header
            assert _get_user_api_key(ctx) is None

    def test_get_user_api_key_non_bearer(self):
        """Non-Bearer Authorization header is ignored, falls back to env."""
        with patch.dict(os.environ, {}, clear=True):
            ctx = _make_context(authorization="Basic dXNlcjpwYXNz")
            assert _get_user_api_key(ctx) is None

    def test_get_user_api_key_from_env_fallback(self):
        """When no Bearer header, falls back to CLEVERTECH_API_KEY env var."""
        with patch.dict(os.environ, {"CLEVERTECH_API_KEY": "env-key-123"}, clear=True):
            ctx = _make_context()  # no Authorization
            assert _get_user_api_key(ctx) == "env-key-123"

    def test_get_user_api_key_no_request(self):
        """Context without request attribute falls back to env."""
        with patch.dict(os.environ, {"CLEVERTECH_API_KEY": "fallback-key"}, clear=True):
            ctx = _make_context(has_request=False)
            assert _get_user_api_key(ctx) == "fallback-key"

    def test_get_user_api_key_empty_auth_header(self):
        """Empty Authorization header string — not Bearer, falls back."""
        with patch.dict(os.environ, {}, clear=True):
            ctx = _make_context(authorization="")
            assert _get_user_api_key(ctx) is None


# ===================================================================
# get_upstream_key
# ===================================================================

class TestGetUpstreamKey:
    """Tests for ``get_upstream_key``."""

    def test_get_upstream_key_with_user_key(self):
        """User key takes priority over server key."""
        assert get_upstream_key("user-key-1", "server-key-1") == "user-key-1"

    def test_get_upstream_key_anonymous(self):
        """No user key → fall back to server key."""
        assert get_upstream_key(None, "server-key-1") == "server-key-1"

    def test_get_upstream_key_neither(self):
        """Neither key set returns None."""
        assert get_upstream_key(None, None) is None

    def test_get_upstream_key_user_key_empty_string(self):
        """Empty string user key is falsy — falls back to server key."""
        assert get_upstream_key("", "server-key") == "server-key"


# ===================================================================
# is_authenticated
# ===================================================================

class TestIsAuthenticated:
    """Tests for ``is_authenticated``."""

    def test_is_authenticated_true(self):
        """User provided a key → authenticated."""
        assert is_authenticated("sk-abc") is True

    def test_is_authenticated_false_none(self):
        """No user key → not authenticated."""
        assert is_authenticated(None) is False

    def test_is_authenticated_false_empty(self):
        """Empty string key → not authenticated (falsy check)."""
        assert is_authenticated("") is False
