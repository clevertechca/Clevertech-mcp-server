"""
CleverTech MCP Server — main entry point.
"""

import os
import sys
import argparse
import json
import contextvars
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from clevertech_mcp.config import load_config
from clevertech_mcp.client import CleverTechClient
from clevertech_mcp.rate_limit import LocalRateLimiter
from clevertech_mcp.auth import get_user_api_key_var
from clevertech_mcp.tools import register_all_tools

# Re-export the ContextVar so middleware can write to it.
_user_api_key_var = get_user_api_key_var()


class SSERequestAuthMiddleware(BaseHTTPMiddleware):
    """Capture ``Authorization: Bearer`` from the initial SSE connection request
    and store it in a ``ContextVar`` so tool handlers can read it."""

    async def dispatch(self, request, call_next):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = _user_api_key_var.set(auth_header[7:])
            try:
                return await call_next(request)
            finally:
                _user_api_key_var.reset(token)
        else:
            return await call_next(request)


async def health_endpoint(request):
    """Health check endpoint for Railway deployment."""
    return JSONResponse({"status": "ok", "service": "clevertech-mcp"})


def create_server(config: dict) -> FastMCP:
    """Build and return a fully-configured FastMCP server instance."""
    mcp = FastMCP("clevertech-mcp")

    client = CleverTechClient(
        base_url=config["api_url"],
        api_key=config.get("api_key"),
    )

    rate_limiter = LocalRateLimiter(
        daily_limit=config.get("rate_limit_anon_daily", 50),
        burst_per_minute=config.get("rate_limit_anon_burst", 10),
    )

    register_all_tools(mcp, client, config, rate_limiter)
    return mcp


def main():
    """CLI entry point for the CleverTech MCP server."""
    parser = argparse.ArgumentParser(
        description="CleverTech MCP Server — Canadian government data APIs"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=os.getenv("TRANSPORT", "stdio"),
        help="Transport mode (default: %(default)s)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host to bind when using SSE transport (default: %(default)s)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8001")),
        help="Port to bind when using SSE transport (default: %(default)s)",
    )
    args = parser.parse_args()

    config = load_config()
    config["host"] = args.host
    config["port"] = args.port

    mcp = create_server(config)

    if args.transport == "sse":
        # Register /health endpoint for Railway health checks
        sse_app = mcp.sse_app()
        if not any(
            getattr(r, "path", "") == "/health"
            for r in getattr(sse_app, "routes", [])
        ):
            sse_app.router.routes.insert(0, Route("/health", endpoint=health_endpoint))

        # Wrap the SSE app with auth middleware to capture per-connection API keys
        sse_app.add_middleware(SSERequestAuthMiddleware)

        import uvicorn
        uvicorn.run(sse_app, host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
