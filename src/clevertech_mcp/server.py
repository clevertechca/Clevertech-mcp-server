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
from starlette.responses import HTMLResponse, JSONResponse
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
        if auth_header[:7].lower() == "bearer ":
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


LANDING_PAGE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CleverTech MCP Server</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html { font-size: 16px; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #0a1628; color: #c8d6e5; line-height: 1.6;
    min-height: 100vh; display: flex; flex-direction: column;
  }
  header {
    background: linear-gradient(135deg, #0d2137 0%, #0a1628 100%);
    border-bottom: 2px solid #0dc5b8; padding: 3rem 1.5rem 2rem; text-align: center;
  }
  header h1 { font-size: 2.4rem; font-weight: 700; color: #ffffff; margin-bottom: 0.4rem; }
  header .hero { font-size: 1.15rem; color: #0dc5b8; margin-bottom: 0.6rem; }
  header .desc {
    font-size: 0.95rem; color: #8ea4be; max-width: 620px; margin: 0 auto;
  }
  main { flex: 1; max-width: 800px; width: 100%; margin: 0 auto; padding: 2rem 1.25rem; }
  section { margin-bottom: 2.5rem; }
  section h2 {
    font-size: 1.35rem; color: #0dc5b8; border-bottom: 1px solid #1a3550;
    padding-bottom: 0.4rem; margin-bottom: 1rem;
  }
  .cmds {
    background: #0d2137; border: 1px solid #1a3550; border-radius: 8px;
    padding: 1.2rem 1.5rem;
  }
  .cmds code, .cmds pre {
    font-family: "SF Mono", Monaco, "Cascadia Code", "Consolas", monospace;
    font-size: 0.9rem; color: #ffffff;
  }
  .cmds pre { margin: 0.5rem 0 0; }
  .badge {
    display: inline-block; background: #0dc5b8; color: #0a1628; font-weight: 600;
    font-size: 0.78rem; padding: 0.15rem 0.6rem; border-radius: 4px; margin-left: 0.4rem;
  }
  .tools { columns: 2; column-gap: 2rem; }
  .tool { margin-bottom: 0.75rem; break-inside: avoid; }
  .tool strong { color: #e8f0f8; font-size: 0.92rem; }
  .tool em { color: #6c8aaa; font-size: 0.85rem; display: block; margin-top: 0.1rem; }
  .links a {
    display: inline-block; margin-right: 1.2rem; color: #0dc5b8; text-decoration: none;
    font-weight: 500;
  }
  .links a:hover { text-decoration: underline; }
  footer {
    text-align: center; padding: 1.5rem; font-size: 0.82rem; color: #4a6680;
    border-top: 1px solid #1a3550;
  }
  footer a { color: #0dc5b8; text-decoration: none; }
  @media (max-width: 600px) {
    header h1 { font-size: 1.7rem; }
    .tools { columns: 1; }
  }
</style>
</head>
<body>
<header>
  <h1>CleverTech MCP Server</h1>
  <p class="hero">Canadian Government Data APIs for AI Agents</p>
  <p class="desc">
    This is a Model Context Protocol (MCP) server that exposes Canadian government
    data — DLS Survey System conversion, property assessments, building permits,
    zoning, business registry, and geocoding — as tools for AI agents.
  </p>
</header>
<main>
  <section>
    <h2>Quickstart</h2>
    <div class="cmds">
      <p><code>mcp add clevertech</code> <span class="badge">50 free / day</span></p>
      <p style="margin-top:0.6rem;">Install the package directly:</p>
      <pre>pip install clevertech-mcp-server</pre>
      <pre style="margin-top:0.3rem;">npm install clevertech-mcp</pre>
    </div>
  </section>
  <section>
    <h2>Tools <span style="font-weight:400;font-size:0.85rem;color:#6c8aaa;">(11 tools)</span></h2>
    <div class="tools">
      <div class="tool"><strong>dls_convert</strong> <em>Convert between GPS and DLS coordinates</em></div>
      <div class="tool"><strong>dls_batch</strong> <em>Batch DLS coordinate conversion</em></div>
      <div class="tool"><strong>property_search</strong> <em>Search property assessments by city</em></div>
      <div class="tool"><strong>property_report</strong> <em>Detailed property report by roll number</em></div>
      <div class="tool"><strong>property_by_roll</strong> <em>Quick property lookup by roll number</em></div>
      <div class="tool"><strong>building_permit_search</strong> <em>Search building permits</em></div>
      <div class="tool"><strong>building_permit_recent</strong> <em>Recent building permits</em></div>
      <div class="tool"><strong>zoning_lookup</strong> <em>Lookup zoning by GPS coordinates</em></div>
      <div class="tool"><strong>business_registry_search</strong> <em>Search Canadian business registry</em></div>
      <div class="tool"><strong>reverse_geocode</strong> <em>Reverse geocode coordinates to addresses</em></div>
      <div class="tool"><strong>list_cities</strong> <em>List supported cities</em></div>
    </div>
  </section>
  <section>
    <h2>Links</h2>
    <div class="links">
      <a href="/health">Health Check</a>
      <a href="https://clevertech.ca">API Reference</a>
      <a href="https://github.com/harmssam/clevertech-mcp-server">GitHub</a>
    </div>
  </section>
</main>
<footer>
  CleverTech &mdash; Canadian Government Data APIs
  &middot; <a href="https://clevertech.ca">clevertech.ca</a>
</footer>
</body>
</html>
"""


async def root_endpoint(request):
    """Serve the landing page for https://mcp.clevertech.ca."""
    return HTMLResponse(LANDING_PAGE_HTML)


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
    parser.add_argument(
        "--api-key",
        default=None,
        help="CleverTech API key (overrides CLEVERTECH_API_KEY env var)",
    )
    args = parser.parse_args()

    config = load_config()
    config["host"] = args.host
    config["port"] = args.port

    # --api-key flag overrides env var for stdio mode
    if args.api_key:
        config["api_key"] = args.api_key

    mcp = create_server(config)

    if args.transport == "sse":
        # Register /health endpoint for Railway health checks
        sse_app = mcp.sse_app()
        if not any(
            getattr(r, "path", "") == "/health"
            for r in getattr(sse_app, "routes", [])
        ):
            sse_app.router.routes.insert(0, Route("/health", endpoint=health_endpoint))
        if not any(
            getattr(r, "path", "") == "/"
            for r in getattr(sse_app, "routes", [])
        ):
            sse_app.router.routes.insert(0, Route("/", endpoint=root_endpoint))

        # Wrap the SSE app with auth middleware to capture per-connection API keys
        sse_app.add_middleware(SSERequestAuthMiddleware)

        import uvicorn
        uvicorn.run(sse_app, host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
