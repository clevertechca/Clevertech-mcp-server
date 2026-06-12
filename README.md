# CleverTech MCP Server

**Canadian government data for AI agents.** Property assessments, building permits, zoning, business registry, DLS grid conversion — 50 free queries/day, no signup.

```bash
uvx clevertech-mcp-server
```

[![PyPI version](https://badge.fury.io/py/clevertech-mcp-server.svg)](https://pypi.org/project/clevertech-mcp-server/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Quick Start

### Claude Code

Add to your `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "clevertech": {
      "command": "uvx",
      "args": ["clevertech-mcp-server"]
    }
  }
}
```

### Cursor / Cline

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "clevertech": {
      "command": "uvx",
      "args": ["clevertech-mcp-server"]
    }
  }
}
```

### GitHub Copilot

```json
{
  "mcpServers": {
    "clevertech": {
      "command": "uvx",
      "args": ["clevertech-mcp-server"]
    }
  }
}
```

### Direct CLI

```bash
uvx clevertech-mcp-server
```

---

## Available Tools (12)

| Tool | Description |
|------|-------------|
| `dls_convert` | GPS ↔ Dominion Land Survey (DLS) coordinate conversion for Western Canada |
| `dls_batch` | Batch GPS ↔ DLS conversion — up to 100 coordinates at once |
| `property_search` | Property assessment search by address across 13+ Canadian cities |
| `property_report` | Consolidated property report — assessment, permits, zoning, and DLS in one call |
| `property_by_roll` | Direct property lookup by roll number — faster than address search |
| `building_permit_search` | Building permit search by address, contractor, applicant, or permit number |
| `building_permit_recent` | Recently issued building permits feed — monitor new construction activity |
| `zoning_lookup` | Zoning district lookup by GPS coordinates or street address |
| `business_registry_search` | Federal corporation search — find Canadian businesses by name, province, or city |
| `reverse_geocode` | GPS → address, city, neighborhood, province, and DLS grid reference |
| `list_cities` | Discover available cities, their API capabilities, and property counts |

### What Agents Can Do

- **Ask**: *"What's 1532 14 Ave SW in Calgary worth?"* — Gets assessed value, land value, building value, year built, lot size, and DLS coordinates.
- **Ask**: *"Show me recent building permits in Vancouver"* — Returns the latest construction permits with type, value, status, and issue dates.
- **Ask**: *"What zone is this GPS point in?"* — Looks up zoning district, land use, and boundary info.
- **Ask**: *"Convert these 50 GPS points to DLS"* — Batch converts in a single API call.
- **Ask**: *"Is Shopify still an active corporation?"* — Searches the federal business registry.

---

## Cities Supported

**20 cities** across Canada — and growing:

| Province | Cities |
|----------|--------|
| Alberta | Calgary, Edmonton, High River |
| British Columbia | Vancouver, Victoria |
| Ontario | Toronto, Ottawa, Hamilton, Kitchener, London, Mississauga, Markham, Vaughan |
| Quebec | Montreal, Quebec City |
| Manitoba | Winnipeg |
| Saskatchewan | Saskatoon, Regina |
| Nova Scotia | Halifax |
| Newfoundland | St. John's |

Use `list_cities` to see live availability, API capabilities per city, and property counts.

---

## Pricing

No signup required to start. Free tier gives you 50 queries/day out of the box.

| Tier | Queries/Day | Price | API Key |
|------|-------------|-------|---------|
| **Free** | 50 | $0 | Not required |
| **Developer** | 200 | Free | [Sign up →](https://clevertech.ca/keys) |
| **Pro** | 2,000 | $10/mo | [Sign up →](https://clevertech.ca/keys) |
| **Enterprise** | 10,000 | $40/mo | [Sign up →](https://clevertech.ca/keys) |

[Get your API key →](https://clevertech.ca/keys)

### Using an API Key

Set the ``CLEVERTECH_API_KEY`` environment variable (recommended):

```bash
export CLEVERTECH_API_KEY=your_key_here
uvx clevertech-mcp-server
```

Or pass it as a CLI flag:

```bash
uvx clevertech-mcp-server --api-key YOUR_KEY
```

To get a new key, use device login:

```bash
uvx clevertech-mcp-server --login
```

This opens a browser for Google sign-in, then prints your API key with
instructions for setting the environment variable (RFC 8628 device flow).
The key is **not** saved to disk — you configure it in your MCP client.

---

## Features

- **No signup required** — 50 free queries/day out of the box
- **12 MCP tools** covering property, permits, zoning, business registry, and DLS
- **Batch DLS conversion** — convert up to 100 coordinates in one call
- **Consolidated property reports** — assessment + permits + zoning + DLS in a single response
- **stdio transport** — works with Claude Code, Cursor, Cline, GitHub Copilot, and any MCP-compatible agent
- **Clean text output** — formatted for easy LLM parsing and reformatting
- **20 Canadian cities** — urban and rural coverage with regular additions
- **MIT licensed** — use it anywhere, no restrictions

---

## Development

```bash
# Clone and set up
git clone https://github.com/clevertechca/Clevertech-mcp-server.git
cd Clevertech-mcp-server
uv sync

# Run locally (stdio transport)
uv run clevertech-mcp-server

# Run with --login to get an API key
uv run clevertech-mcp-server --login

# Run with SSE transport (for HTTP-based agents)
uv run clevertech-mcp-server --transport sse --port 8000
```

### Run Tests

```bash
uv run pytest
```

### Project Structure

```
src/clevertech_mcp/
├── tools/
│   ├── property.py    # property_search, property_report, property_by_roll
│   ├── building.py    # building_permit_search, building_permit_recent
│   ├── zoning.py      # zoning_lookup
│   ├── dls.py         # dls_convert, dls_batch
│   ├── business.py    # business_registry_search
│   ├── geo.py         # reverse_geocode
│   └── meta.py        # list_cities
├── server.py          # FastMCP server entry point
├── client.py          # HTTP client for CleverTech API
├── auth.py            # API key authentication
├── rate_limit.py      # Rate limiting
└── config.py          # Configuration management
```

---

## Documentation

- [Tool Reference](docs/tools.md)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [CleverTech API Keys](https://clevertech.ca/keys)

---

## License

MIT © 2026 CleverTech — see [LICENSE](LICENSE) for details.
