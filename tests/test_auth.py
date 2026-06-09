"""Tests for authentication helpers (auth.py).

Tests IP extraction, API key retrieval from headers, upstream key
resolution, and the is_authenticated check — all using duck-typed
mock request contexts.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import the functions under test (prefixed with _ since they're internal)
from clevertech_mcp.auth import (
    _extract_client_ip,
    _get_user_api_key,
    get_upstream_key,
    is_authenticated,
)

from tests.conftest import MockMCP, register_and_get_tool


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
    else:
        # Explicitly set request to None so MagicMock doesn't auto-create it
        ctx.request = None
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
        with patch.dict(os.environ, {}, clear=True):
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


# ===================================================================
# ContextVar integration
# ===================================================================

class TestContextVarBridge:
    """Tests for the ContextVar bridge (SSE middleware path)."""

    def test_contextvar_takes_priority_over_env(self):
        """ContextVar value returned even when env var is set."""
        from clevertech_mcp.auth import _user_api_key_var as var
        with patch.dict(os.environ, {"CLEVERTECH_API_KEY": "server-key"}, clear=True):
            token = var.set("ctk_user_key")
            try:
                # ctx=None means no request context — only ContextVar + env
                assert _get_user_api_key(None) == "ctk_user_key"
            finally:
                var.reset(token)

    def test_contextvar_cleared_falls_back_to_env(self):
        """After ContextVar reset, falls back to env var."""
        from clevertech_mcp.auth import _user_api_key_var as var
        with patch.dict(os.environ, {"CLEVERTECH_API_KEY": "server-key"}, clear=True):
            token = var.set("ctk_temp")
            var.reset(token)
            assert _get_user_api_key(None) == "server-key"

    def test_contextvar_no_key_nor_env(self):
        """Neither ContextVar nor env set returns None."""
        from clevertech_mcp.auth import _user_api_key_var as var
        with patch.dict(os.environ, {}, clear=True):
            # Ensure ContextVar is clean
            try:
                var.get()
            except ValueError:
                pass  # Not set
            var.set(None)  # Reset to default
            assert _get_user_api_key(None) is None


# ===================================================================
# Integration — auth → client → rate limiter
# ===================================================================

class TestAuthClientIntegration:
    """End-to-end: tool handler wiring through auth, client, and rate limiter.

    Uses a real-ish tool registration via conftest to simulate the full
    chain from ``_get_user_api_key`` → ``get_upstream_key`` →
    ``client.get/post(api_key=...)`` → ``rate_limiter.check_or_raise``.
    """

    @pytest.mark.asyncio
    async def test_tool_with_user_key_sends_user_key(self, mock_client, mock_config):
        """Authenticated user: client receives their API key."""
        from clevertech_mcp.auth import _user_api_key_var as var
        from clevertech_mcp.tools.meta import register_meta_tools

        tool = register_and_get_tool(
            register_meta_tools, mock_client, mock_config, "list_cities"
        )

        # Set user API key via ContextVar (simulating SSE middleware)
        user_key = "ctk_user_test_123"
        token = var.set(user_key)
        try:
            with patch.dict(os.environ, {"CLEVERTECH_API_KEY": "server-key"}, clear=True):
                mock_client.get = AsyncMock(return_value={"cities": []})
                await tool()
        finally:
            var.reset(token)

        # Verify client received the user API key
        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs.get("api_key") == user_key

    @pytest.mark.asyncio
    async def test_tool_without_key_sends_server_key(self, mock_client, mock_config):
        """Anonymous user: client receives the server API key from config."""
        from clevertech_mcp.tools.meta import register_meta_tools

        # Config with a server API key
        cfg = {**mock_config, "api_key": "ctk_server_456"}

        tool = register_and_get_tool(
            register_meta_tools, mock_client, cfg, "list_cities"
        )

        with patch.dict(os.environ, {}, clear=True):
            mock_client.get = AsyncMock(return_value={"cities": []})
            await tool()

        # Verify client received the server key (no user key set)
        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs.get("api_key") == "ctk_server_456"

    @pytest.mark.asyncio
    async def test_anonymous_rate_limit_enforced(self):
        """Anonymous user hitting rate limit gets ValueError."""
        from clevertech_mcp.auth import _user_api_key_var as var
        from clevertech_mcp.rate_limit import LocalRateLimiter
        from unittest.mock import AsyncMock

        # Create a rate limiter with daily limit = 1
        limiter = LocalRateLimiter(daily_limit=1, burst_per_minute=10)

        # Mock client and config
        client = MagicMock()
        client.get = AsyncMock(return_value={"cities": []})
        cfg = {"api_key": "server-key"}

        mcp = MockMCP()
        from clevertech_mcp.tools.meta import register_meta_tools
        register_meta_tools(mcp, client, cfg, limiter)
        tool = mcp.tools["list_cities"]

        # First call works
        with patch.dict(os.environ, {}, clear=True):
            result = await tool()
            assert result is not None

        # Second call should fail (daily limit = 1)
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Daily rate limit"):
                await tool()

    @pytest.mark.asyncio
    async def test_authenticated_user_skips_rate_limit(self):
        """Authenticated user bypasses local rate limiter entirely."""
        from clevertech_mcp.auth import _user_api_key_var as var
        from clevertech_mcp.rate_limit import LocalRateLimiter
        from unittest.mock import AsyncMock

        # Create a rate limiter with daily limit = 1
        limiter = LocalRateLimiter(daily_limit=1, burst_per_minute=10)

        client = MagicMock()
        client.get = AsyncMock(return_value={"cities": []})
        cfg = {"api_key": "server-key"}

        mcp = MockMCP()
        from clevertech_mcp.tools.meta import register_meta_tools
        register_meta_tools(mcp, client, cfg, limiter)
        tool = mcp.tools["list_cities"]

        # Set user API key
        token = var.set("ctk_user_paid")
        try:
            with patch.dict(os.environ, {}, clear=True):
                # First call
                await tool()
                # Second call — should work because user is authenticated
                await tool()
                # Third call — still works
                await tool()
        finally:
            var.reset(token)

        # All 3 calls succeeded because rate limiter was bypassed
        assert client.get.call_count == 3
