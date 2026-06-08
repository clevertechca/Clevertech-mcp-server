"""
Authentication helpers for the CleverTech MCP server.

Handles extraction of client IP, user API keys from request headers,
and resolution of the upstream API key.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import Request


# MCP tools receive a *context* object (starlette Request or similar).
# We use duck-typing to support both Starlette's Request and MCP's
# RequestContext / MiddlewareContext.


def _extract_client_ip(context) -> str:
    """Extract the client IP address from an MCP/starlette context.

    Prefers X-Forwarded-For (first entry) when present; falls back to
    ``context.request.client.host`` or ``"unknown"``.
    """
    # Starlette-style request
    request: Optional["Request"] = getattr(context, "request", None)
    if request is not None:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # X-Forwarded-For can contain a comma-separated list
            return forwarded.split(",")[0].strip()
        if request.client is not None:
            return request.client.host
    return "unknown"


def _get_user_api_key(context) -> Optional[str]:
    """Extract a user-supplied API key from the request context.

    Looks for an ``Authorization: Bearer <token>`` header.  Returns
    ``None`` if no key is present.
    """
    import os

    request = getattr(context, "request", None)
    if request is not None:
        auth_header: Optional[str] = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]  # strip "Bearer "
    return os.getenv("CLEVERTECH_API_KEY")


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
    """Return ``True`` when the user has supplied their own API key."""
    return user_api_key is not None
