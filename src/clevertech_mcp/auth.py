"""
Authentication helpers for the CleverTech MCP server.

Handles extraction of client IP, user API keys from request headers,
and resolution of the upstream API key.

The module uses a ``contextvars.ContextVar`` so that SSE middleware can
bridge the initial connection's ``Authorization`` header into tool handler
scope.  In stdio mode (no HTTP request) the module falls back to the
``CLEVERTECH_API_KEY`` environment variable.
"""

import os
import contextvars
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    pass

# ContextVar bridge for SSE transport.
# Set by Starlette middleware on the initial SSE connection request.
# Read by _get_user_api_key() inside tool handlers.
_user_api_key_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "_user_api_key_var", default=None
)


def get_user_api_key_var() -> contextvars.ContextVar[Optional[str]]:
    """Return the ContextVar used by SSE middleware to store the connection's API key."""
    return _user_api_key_var


def _safe_getattr(obj, attr):
    """Like ``getattr`` but uses ``object.__getattribute__`` to bypass
    MagicMock auto-creation during testing.  Returns ``None`` when the
    attribute does not exist (instead of auto-creating a mock)."""
    try:
        return object.__getattribute__(obj, attr)
    except AttributeError:
        return None


def _extract_client_ip(context) -> str:
    """Extract the client IP address from an MCP/starlette context.

    Prefers X-Forwarded-For (first entry) when present; falls back to
    ``context.request.client.host`` or ``\"unknown\"``.
    """
    request = _safe_getattr(context, "request")
    if request is None:
        rc = _safe_getattr(context, "request_context")
        if rc is not None:
            request = _safe_getattr(rc, "request")

    if request is not None:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        client = _safe_getattr(request, "client")
        if client is not None:
            host = _safe_getattr(client, "host")
            if host is not None:
                return host
    return "unknown"


def _get_user_api_key(context) -> Optional[str]:
    """Extract a user-supplied API key from the request context.

    Resolution order (first wins):
      1. ContextVar bridge (set by SSE middleware at connection time)
      2. ``CLEVERTECH_API_KEY`` environment variable (stdio / ``--api-key`` flag)
      3. Duck-typed ``context.request`` (legacy / direct — works with both
         FastMCP Context and MagicMock-based test helpers)

    Returns ``None`` if no key is found.
    """
    # ── 1. ContextVar bridge (SSE middleware set this) ────────────────────
    # Highest priority — carries the per-connection user API key from the
    # SSE request's Authorization header.
    key = _user_api_key_var.get()
    if key:
        return key

    # ── 2. Environment variable (stdio / CLI / --api-key flag) ────────────
    # Server-wide key for stdio mode; also used as fallback in SSE mode
    # when no user key is provided.
    env_key = os.getenv("CLEVERTECH_API_KEY")
    if env_key:
        return env_key

    # ── 3. Direct request-context extraction ──────────────────────────────
    # Handles:
    #   - FastMCP Context (request_context.request) in SSE mode without
    #     middleware
    #   - Duck-typed test helpers (MagicMock with .request set explicitly)
    # Uses _safe_getattr to bypass MagicMock auto-creation.
    if context is not None:
        request = _safe_getattr(context, "request")
        if request is None:
            rc = _safe_getattr(context, "request_context")
            if rc is not None:
                request = _safe_getattr(rc, "request")
        if request is not None:
            auth_header = request.headers.get("Authorization", "")
            if auth_header and auth_header[:7].lower() == "bearer ":
                return auth_header[7:]

    return None


def get_upstream_key(
    user_api_key: Optional[str],
    server_api_key: Optional[str],
) -> Optional[str]:
    """Return the API key to use for upstream CleverTech API calls.

    Prefers the user-provided key (authenticated user) over the server-
    wide key (anonymous / default).  Returns ``None`` if neither is set.
    """
    if user_api_key:
        return user_api_key
    return server_api_key


def is_authenticated(user_api_key: Optional[str]) -> bool:
    """Check if a user API key was provided."""
    return bool(user_api_key)  # Empty string is not authenticated
