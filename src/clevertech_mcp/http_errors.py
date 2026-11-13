"""Map upstream httpx failures to tool-facing error strings.

Tools return these strings instead of letting raw httpx exceptions bubble
to the agent. Unknown exception types are re-raised.
"""

import httpx

_DEFAULT_TIMEOUT = (
    "Error: the CleverTech API timed out before a response arrived. "
    "Try again with a smaller query, or retry later."
)


def tool_http_error(
    exc: BaseException,
    *,
    not_found: str,
    timeout: str | None = None,
) -> str:
    """Return a clear tool error for 404s and timeouts.

    Other HTTP status codes become a short ``HTTP {code}`` message.
    Any other exception type is re-raised.
    """
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return timeout or _DEFAULT_TIMEOUT
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        code = exc.response.status_code
        if code == 404:
            return not_found
        return f"Error: CleverTech API returned HTTP {code}."
    raise exc
