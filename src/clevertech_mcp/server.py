"""
CleverTech MCP Server — main entry point.
"""

import os
import argparse
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
<title>CleverTech MCP Server — Canadian Government Data APIs</title>
<meta name="description" content="A Model Context Protocol (MCP) server that gives AI agents access to Canadian property assessments, building permits, zoning data, business registry, DLS conversion, and geocoding across 13+ cities.">
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
    font-size: 0.92rem; color: #8ea4be; max-width: 640px; margin: 0 auto;
  }
  header .tags { margin-top: 1rem; }
  header .tags span {
    display: inline-block; background: rgba(13,197,184,0.12); color: #0dc5b8;
    font-size: 0.78rem; padding: 0.25rem 0.7rem; border-radius: 20px;
    margin: 0 0.3rem 0.4rem; border: 1px solid rgba(13,197,184,0.25);
  }
  main { flex: 1; max-width: 880px; width: 100%; margin: 0 auto; padding: 2rem 1.25rem; }
  section { margin-bottom: 2.5rem; }
  section h2 {
    font-size: 1.35rem; color: #0dc5b8; border-bottom: 1px solid #1a3550;
    padding-bottom: 0.4rem; margin-bottom: 1rem;
  }
  section h3 {
    font-size: 1.05rem; color: #e8f0f8; margin: 1.2rem 0 0.5rem;
  }
  .card {
    background: #0f1f33; border: 1px solid #1a3550; border-radius: 8px;
    padding: 1.2rem 1.5rem; margin-bottom: 1rem;
  }
  .card code, .card pre, .card p code {
    font-family: "SF Mono", Monaco, "Cascadia Code", "Consolas", monospace;
    font-size: 0.88rem; color: #ffffff;
  }
  .card pre {
    background: #0a1628; border: 1px solid #1a3550; border-radius: 6px;
    padding: 0.8rem 1rem; margin: 0.5rem 0 0; overflow-x: auto;
    font-size: 0.82rem; line-height: 1.45;
  }
  .card .badge {
    display: inline-block; background: #0dc5b8; color: #0a1628; font-weight: 600;
    font-size: 0.78rem; padding: 0.15rem 0.6rem; border-radius: 4px; margin-left: 0.4rem;
  }
  .card .badge-green { background: #22c55e; color: #0a1628; }
  .card .badge-yellow { background: #eab308; color: #0a1628; }

  /* Tools grid */
  .tools { display: grid; gap: 0.75rem; }
  .tool-card {
    background: #0f1f33; border: 1px solid #1a3550; border-radius: 8px;
    padding: 1rem 1.25rem;
  }
  .tool-card .tool-name {
    color: #0dc5b8; font-weight: 600; font-size: 0.95rem; font-family: "SF Mono", Monaco, monospace;
  }
  .tool-card .tool-desc { color: #8ea4be; font-size: 0.85rem; margin-top: 0.15rem; }
  .tool-card .tool-params { margin-top: 0.4rem; }
  .tool-card .tool-params code {
    font-size: 0.8rem; color: #e8f0f8; font-family: "SF Mono", Monaco, monospace;
  }
  .tool-card .tool-params span { color: #6c8aaa; font-size: 0.8rem; }

  /* Use case cards */
  .usecases { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
  .usecase-card {
    background: #0f1f33; border: 1px solid #1a3550; border-radius: 8px;
    padding: 1rem 1.15rem;
  }
  .usecase-card .uc-icon { font-size: 1.3rem; }
  .usecase-card .uc-title { font-size: 0.9rem; font-weight: 600; color: #e8f0f8; }
  .usecase-card .uc-desc { font-size: 0.82rem; color: #8ea4be; margin-top: 0.2rem; }

  /* City chips */
  .cities { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.5rem; }
  .city-chip {
    background: rgba(13,197,184,0.08); border: 1px solid rgba(13,197,184,0.2);
    color: #c8d6e5; font-size: 0.8rem; padding: 0.2rem 0.65rem; border-radius: 4px;
  }

  .links { display: flex; flex-wrap: wrap; gap: 1rem; }
  .links a {
    color: #0dc5b8; text-decoration: none; font-weight: 500; font-size: 0.9rem;
  }
  .links a:hover { text-decoration: underline; }

  footer {
    text-align: center; padding: 1.5rem; font-size: 0.82rem; color: #4a6680;
    border-top: 1px solid #1a3550;
  }
  footer a { color: #0dc5b8; text-decoration: none; }

  .alert {
    background: rgba(234,179,8,0.08); border: 1px solid rgba(234,179,8,0.25);
    border-radius: 6px; padding: 0.6rem 1rem; font-size: 0.82rem; color: #eab308;
    margin-top: 0.8rem;
  }

  @media (max-width: 640px) {
    header h1 { font-size: 1.7rem; }
    .usecases { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<header>
  <h1>CleverTech MCP Server</h1>
  <p class="hero">Canadian Government Data APIs for AI Agents</p>
  <p class="desc">
    A <strong>Model Context Protocol (MCP)</strong> server that gives AI assistants
    (Claude, VS Code Copilot, Cursor, etc.) direct access to Canadian property
    assessments, building permits, zoning data, federal business registry,
    Dominion Land Survey (DLS) conversion, and geocoding &mdash; across 13+ cities.
  </p>
  <div class="tags">
    <span>#canada</span>
    <span>#open-data</span>
    <span>#government</span>
    <span>#property</span>
    <span>#zoning</span>
    <span>#DLS</span>
  </div>
</header>
<main>

  <!-- ── WHY / USE CASES ──────────────────────────────────── -->
  <section>
    <h2>What Can AI Agents Do With This?</h2>
    <div class="usecases">
      <div class="usecase-card">
        <div class="uc-icon">🏠</div>
        <div class="uc-title">Property Research</div>
        <div class="uc-desc">
          "What's the assessed value of 123 Main St in Calgary?" &mdash; returns
          property data, year built, lot size, and DLS coordinates.
        </div>
      </div>
      <div class="usecase-card">
        <div class="uc-icon">🏗️</div>
        <div class="uc-title">Construction Monitoring</div>
        <div class="uc-desc">
          "Show me recent building permits in Toronto" &mdash; gets recently issued
          permits with type, value, and status.
        </div>
      </div>
      <div class="usecase-card">
        <div class="uc-icon">📍</div>
        <div class="uc-title">Zoning Lookup</div>
        <div class="uc-desc">
          "What's the zoning at (51.045, -114.072) in Calgary?" &mdash; returns
          zone code, description, and land use category.
        </div>
      </div>
      <div class="usecase-card">
        <div class="uc-icon">🏢</div>
        <div class="uc-title">Business Intelligence</div>
        <div class="uc-desc">
          "Find active tech corporations in Vancouver" &mdash; searches the federal
          registry by name, province, city, and status.
        </div>
      </div>
      <div class="usecase-card">
        <div class="uc-icon">🧭</div>
        <div class="uc-title">DLS Coordinate Conversion</div>
        <div class="uc-desc">
          "Convert NW-16-24-1-W5 to GPS coordinates" &mdash; bi-directional
          conversion for the Western Canada grid system.
        </div>
      </div>
      <div class="usecase-card">
        <div class="uc-icon">📍</div>
        <div class="uc-title">Reverse Geocoding</div>
        <div class="uc-desc">
          "What address is at (43.653, -79.383)?" &mdash; resolves coordinates
          to address, city, province, postal code, and DLS.
        </div>
      </div>
    </div>
  </section>

  <!-- ── AVAILABLE TOOLS ──────────────────────────────────── -->
  <section>
    <h2>Available Tools <span style="font-weight:400;font-size:0.85rem;color:#6c8aaa;">(11 tools)</span></h2>
    <div class="tools">
      <div class="tool-card">
        <div class="tool-name">dls_convert</div>
        <div class="tool-desc">Convert between GPS coordinates and Dominion Land Survey (DLS) grid system used in Western Canada. Supports both GPS→DLS and DLS→GPS directions.</div>
        <div class="tool-params">
          <code>direction</code> <span>string (required) — "gps_to_dls" or "dls_to_gps"</span><br>
          <code>lat</code> <span>float — required for gps_to_dls</span><br>
          <code>lon</code> <span>float — required for gps_to_dls</span><br>
          <code>dls_string</code> <span>string — required for dls_to_gps</span><br>
          <code>province</code> <span>string (optional) — AB, SK, MB</span>
        </div>
      </div>

      <div class="tool-card">
        <div class="tool-name">dls_batch</div>
        <div class="tool-desc">Convert multiple coordinates in a single request. Up to 100 items per batch.</div>
        <div class="tool-params">
          <code>direction</code> <span>string (required) — "gps_to_dls" or "dls_to_gps"</span><br>
          <code>items</code> <span>array of objects (required) — lat/lon or dls_string items</span><br>
          <code>province</code> <span>string (optional)</span>
        </div>
      </div>

      <div class="tool-card">
        <div class="tool-name">property_search</div>
        <div class="tool-desc">Search property assessments by address across 13+ Canadian cities. Returns assessed value, lot size, year built, and DLS coordinates.</div>
        <div class="tool-params">
          <code>city</code> <span>string (required) — city slug</span><br>
          <code>address</code> <span>string (required) — partial address match</span><br>
          <code>limit</code> <span>int (optional, default 10, max 200)</span><br>
          <code>offset</code> <span>int (optional)</span>
        </div>
      </div>

      <div class="tool-card">
        <div class="tool-name">property_report</div>
        <div class="tool-desc">Get a consolidated property report combining assessment data, building permits, zoning, and DLS coordinates in a single response.</div>
        <div class="tool-params">
          <code>city</code> <span>string (required)</span><br>
          <code>roll_number</code> <span>string (required)</span>
        </div>
      </div>

      <div class="tool-card">
        <div class="tool-name">property_by_roll</div>
        <div class="tool-desc">Get a single property assessment record by its roll number. Faster than property_search when you already have the roll number.</div>
        <div class="tool-params">
          <code>city</code> <span>string (required)</span><br>
          <code>roll_number</code> <span>string (required)</span>
        </div>
      </div>

      <div class="tool-card">
        <div class="tool-name">building_permit_search</div>
        <div class="tool-desc">Search building permits by address, contractor, applicant, or permit number. Returns permit type, value, status, and dates.</div>
        <div class="tool-params">
          <code>city</code> <span>string (required)</span><br>
          <code>q</code> <span>string (required) — search query</span><br>
          <code>permit_type</code> <span>string (optional) — e.g. Building, Demolition, Electrical</span><br>
          <code>limit</code> <span>int (optional, default 20, max 200)</span>
        </div>
      </div>

      <div class="tool-card">
        <div class="tool-name">building_permit_recent</div>
        <div class="tool-desc">Get the most recently issued building permits for a city. Useful for monitoring new construction activity.</div>
        <div class="tool-params">
          <code>city</code> <span>string (required)</span><br>
          <code>limit</code> <span>int (optional, default 20, max 100)</span>
        </div>
      </div>

      <div class="tool-card">
        <div class="tool-name">zoning_lookup</div>
        <div class="tool-desc">Look up zoning district information for a GPS point or address. Returns zone code, description, district name, and land use.</div>
        <div class="tool-params">
          <code>city</code> <span>string (required)</span><br>
          <code>lat</code> <span>float — (alternative to address)</span><br>
          <code>lon</code> <span>float — (alternative to address)</span><br>
          <code>address</code> <span>string — (alternative to lat/lon)</span>
        </div>
      </div>

      <div class="tool-card">
        <div class="tool-name">business_registry_search</div>
        <div class="tool-desc">Search the Canadian federal corporations registry by name, province, city, status, or industry act.</div>
        <div class="tool-params">
          <code>q</code> <span>string (required) — corporation name or keyword</span><br>
          <code>province</code> <span>string (optional) — e.g. AB, BC, ON, QC</span><br>
          <code>city</code> <span>string (optional)</span><br>
          <code>status</code> <span>string (optional) — Active, Dissolved</span><br>
          <code>limit</code> <span>int (optional, default 25, max 100)</span>
        </div>
      </div>

      <div class="tool-card">
        <div class="tool-name">reverse_geocode</div>
        <div class="tool-desc">Convert GPS coordinates to a human-readable address, city, neighborhood, province, postal code, and DLS grid reference.</div>
        <div class="tool-params">
          <code>lat</code> <span>float (required)</span><br>
          <code>lon</code> <span>float (required)</span>
        </div>
      </div>

      <div class="tool-card">
        <div class="tool-name">list_cities</div>
        <div class="tool-desc">List all available cities with their slugs, API capabilities, and property counts. Use this to discover which cities are available and what services each supports.</div>
        <div class="tool-params">
          <em style="color:#6c8aaa;font-size:0.82rem;">No parameters required</em>
        </div>
      </div>
    </div>
  </section>

  <!-- ── QUICK START ──────────────────────────────────────── -->
  <section>
    <h2>Quick Start</h2>

    <div class="alert" style="background:#2d1f1f;border:1px solid #8b3a3a;color:#e0b0b0;padding:0.75rem 1rem;border-radius:6px;margin-bottom:1.5rem;font-size:0.85rem;">
      ⚠️ <strong>Remote SSE endpoint decommissioned.</strong> The hosted SSE endpoint at
      <code>mcp.clevertech.ca</code> has been shut down as of June 2026.
      Use local stdio transport instead — it's faster, more reliable, and works
      with every MCP client. No install required with <code>uvx</code> or <code>npx</code>.
    </div>

    <h3>Claude Desktop</h3>
    <div class="card">
      <p>Add to your <code>~/.claude/claude_desktop_config.json</code>:</p>
      <pre>{
  "mcpServers": {
    "clevertech": {
      "command": "uvx",
      "args": ["clevertech-mcp-server"]
    }
  }
}</pre>
      <p style="color:#8ea4be;font-size:0.82rem;margin-top:0.4rem;">
        With API key: add <code>"CLEVERTECH_API_KEY": "your-key"</code> to <code>env</code> field.
      </p>
    </div>

    <h3>Cursor / Cline</h3>
    <div class="card">
      <p>Add to your MCP configuration:</p>
      <pre>{
  "mcpServers": {
    "clevertech": {
      "command": "uvx",
      "args": ["clevertech-mcp-server"]
    }
  }
}</pre>
    </div>

    <h3>VS Code / GitHub Copilot</h3>
    <div class="card">
      <p>Configure via <code>.vscode/mcp.json</code>:</p>
      <pre>{
  "servers": {
    "clevertech": {
      "command": "uvx",
      "args": ["clevertech-mcp-server"]
    }
  }
}</pre>
    </div>

    <h3>Direct CLI (npm / uv)</h3>
    <div class="card">
      <pre># npm (Node.js)
npx @clevertech/mcp-server

# uv / PyPI
uvx clevertech-mcp-server</pre>
    </div>

    <h3>From Source</h3>
    <div class="card">
      <pre>git clone https://github.com/harmssam/clevertech-mcp-server.git
cd clevertech-mcp-server
uv sync
uv run clevertech-mcp-server</pre>
    </div>
  </section>

  <!-- ── AUTHENTICATION ───────────────────────────────────── -->
  <section>
    <h2>Authentication &amp; Rate Limits</h2>
    <div class="card">
      <p>
        <span class="badge">50 requests/day</span>
        Free tier — no API key required. Rate limited by source IP.
      </p>
      <p style="margin-top:0.6rem;">
        <span class="badge badge-green">Unlimited</span>
        Two ways to authenticate with a CleverTech API key:
      </p>
      <p style="margin-top:0.5rem;font-size:0.85rem;">
        <strong>Option 1 — Device login (no terminal password):</strong>
      </p>
      <pre style="margin-top:0.3rem;">npx @clevertech/mcp-server --login</pre>
      <p style="font-size:0.82rem;color:#8ea4be;margin-top:0.2rem;">
        Opens a browser → sign in with Google → API key saved automatically to
        <code>~/.clevertech/config.json</code> (RFC 8628 device flow).
      </p>
      <p style="margin-top:0.6rem;font-size:0.85rem;">
        <strong>Option 2 — Environment variable:</strong>
      </p>
      <pre style="margin-top:0.3rem;">export CLEVERTECH_API_KEY=your_key_here
uvx clevertech-mcp-server</pre>
      <p style="margin-top:0.75rem;font-size:0.85rem;">
        🔑 Get your API key at
        <a href="https://clevertech.ca" style="color:#0dc5b8;">clevertech.ca</a>
        (sign up for free). Authenticated users get burst rate limits of
        60 requests/minute vs 10/minute for anonymous.
      </p>
    </div>
  </section>

  <!-- ── SUPPORTED CITIES ─────────────────────────────────── -->
  <section>
    <h2>Supported Cities</h2>
    <div class="card">
      <p>Data available across 13+ Canadian municipalities:</p>
      <div class="cities">
        <span class="city-chip">Calgary</span>
        <span class="city-chip">Edmonton</span>
        <span class="city-chip">Toronto</span>
        <span class="city-chip">Vancouver</span>
        <span class="city-chip">Montreal</span>
        <span class="city-chip">Ottawa</span>
        <span class="city-chip">Winnipeg</span>
        <span class="city-chip">Hamilton</span>
        <span class="city-chip">Victoria</span>
        <span class="city-chip">Quebec City</span>
        <span class="city-chip">Halifax</span>
        <span class="city-chip">London</span>
        <span class="city-chip">Kitchener</span>
        <span class="city-chip">Mississauga</span>
        <span class="city-chip">Regina</span>
        <span class="city-chip">Saskatoon</span>
        <span class="city-chip">St. John's</span>
      </div>
      <p style="margin-top:0.6rem;font-size:0.82rem;color:#6c8aaa;">
        Use the <code>list_cities</code> tool to see capabilities per city.
        <code>property</code>, <code>building</code>, <code>zoning</code>
        coverage varies by city.
      </p>
    </div>
  </section>

  <!-- ── SECURITY ─────────────────────────────────────────── -->
  <section>
    <h2>Security &amp; Privacy</h2>
    <div class="card" style="font-size:0.85rem;">
      <p>🔒 <strong>Transport:</strong> All connections to the CleverTech API use HTTPS. The MCP server runs locally on your machine via stdio.</p>
      <p style="margin-top:0.4rem;">🔑 <strong>Authentication:</strong> API keys are set via <code>CLEVERTECH_API_KEY</code> environment variable. Keys are never exposed in URLs, logs, or error messages.</p>
      <p style="margin-top:0.4rem;">🌐 <strong>Data Sources:</strong> All data comes from official Canadian government open-data portals. No proprietary or user-generated data is stored server-side.</p>
      <p style="margin-top:0.4rem;">📊 <strong>Privacy:</strong> This server accesses only publicly available government datasets. No personal information is collected. Rate limiting uses anonymous source-IP tracking which is not persisted to disk.</p>
    </div>
  </section>

  <!-- ── LINKS ────────────────────────────────────────────── -->
  <section>
    <h2>Links</h2>
    <div class="links">
      <a href="https://clevertech.ca">clevertech.ca</a>
      <a href="https://github.com/harmssam/clevertech-mcp-server">GitHub</a>
      <a href="https://clevertech.ca/docs">API Docs</a>
      <a href="https://pypi.org/project/clevertech-mcp-server/">PyPI</a>
      <a href="https://www.npmjs.com/package/@clevertech/mcp-server">npm</a>
    </div>
  </section>

</main>
<footer>
  CleverTech &mdash; Canadian Government Data APIs
  &middot; <a href="https://clevertech.ca">clevertech.ca</a>
  &middot; MIT License
</footer>
</body>
</html>"""


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
    parser.add_argument(
        "--login",
        action="store_true",
        default=False,
        help="Authenticate via device authorization flow and save API key",
    )
    args = parser.parse_args()

    config = load_config()
    config["host"] = args.host
    config["port"] = args.port

    # Resolve API key priority: --api-key > CLEVERTECH_API_KEY > saved config
    if not args.api_key:
        api_key = os.getenv("CLEVERTECH_API_KEY")
        if not api_key:
            from clevertech_mcp.login import load_saved_api_key
            api_key = load_saved_api_key()
            if api_key:
                os.environ["CLEVERTECH_API_KEY"] = api_key
                config["api_key"] = api_key

    # --api-key flag overrides env var for stdio mode
    if args.api_key:
        config["api_key"] = args.api_key
        os.environ["CLEVERTECH_API_KEY"] = args.api_key

    # --login runs the device authorization flow, then starts the server
    # (skipped if --api-key was already provided, which takes priority)
    if args.login and not args.api_key:
        from clevertech_mcp.login import device_login
        api_key = device_login(config.get("api_url", "https://clevertech.ca"))
        config["api_key"] = api_key
        os.environ["CLEVERTECH_API_KEY"] = api_key

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
