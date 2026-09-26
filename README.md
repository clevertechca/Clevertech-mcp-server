# Clevertech MCP Server

<!-- mcp-name: ca.clevertech/clevertech-mcp-server -->

**Canadian government and municipal open data for AI agents.** Property assessments, building permits, zoning, business registry, DLS grid conversion, and more.

```bash
uvx clevertech-mcp-server
```

Requires a Clevertech API key (`CLEVERTECH_API_KEY`). Free tier: **50 API calls/day after sign-in** at [clevertech.ca/keys](https://clevertech.ca/keys).

[![PyPI version](https://badge.fury.io/py/clevertech-mcp-server.svg)](https://pypi.org/project/clevertech-mcp-server/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Quick Start

1. Create an API key: [https://clevertech.ca/keys](https://clevertech.ca/keys)
2. Set `CLEVERTECH_API_KEY` in your MCP client config (examples below)
3. Run `uvx clevertech-mcp-server`

Product overview: [https://clevertech.ca/agents](https://clevertech.ca/agents)

### Cursor / Claude / Copilot (MCP config)

```json
{
  "mcpServers": {
    "clevertech": {
      "command": "uvx",
      "args": ["clevertech-mcp-server"],
      "env": {
        "CLEVERTECH_API_KEY": "${env:CLEVERTECH_API_KEY}"
      }
    }
  }
}
```

Or paste your key directly as the `CLEVERTECH_API_KEY` string value.

### Direct CLI

```bash
export CLEVERTECH_API_KEY=your_key_here
uvx clevertech-mcp-server
```

---

## Available Tools

| Tool | Description |
|------|-------------|
| `dls_convert` | GPS ↔ Dominion Land Survey (DLS) for Western Canada |
| `dls_batch` | Batch GPS ↔ DLS (up to 100 coordinates) |
| `property_search` | Property assessment search by address |
| `property_report` | Consolidated property report |
| `property_by_roll` | Lookup by roll number |
| `building_permit_search` | Building permits by address, contractor, applicant, or number |
| `building_permit_recent` | Recently issued permits feed |
| `zoning_lookup` | Zoning by GPS or address |
| `business_registry_search` | Federal corporation search |
| `reverse_geocode` | GPS → address, city, neighborhood, province, DLS |
| `list_cities` | Cities, capabilities, and property counts |

Use `list_cities` for live coverage. Cities span Alberta, BC, Ontario, Quebec, Manitoba, Saskatchewan, Nova Scotia, Newfoundland, and more.

---

## Pricing (CAD)

Site is the source of truth: [clevertech.ca/agents](https://clevertech.ca/agents)

| Tier | What you get | Price |
|------|----------------|-------|
| **Free** | 50 API calls/day after sign-in | $0 |
| **Prepaid** | Pay-as-you-go prepaid credit | $29 |
| **Developer** | Higher limits for builders | $149 |
| **Team Pro** | Team / higher tier | $499 |

Get a key: [https://clevertech.ca/keys](https://clevertech.ca/keys)

---

## Features

- MCP stdio server for Cursor, Claude, Copilot, and other MCP clients
- Canadian municipal / government open-data tools for agents
- PyPI package: [`clevertech-mcp-server`](https://pypi.org/project/clevertech-mcp-server/)
- MIT licensed

---

## Development

```bash
git clone https://github.com/clevertechca/Clevertech-mcp-server.git
cd Clevertech-mcp-server
uv sync
export CLEVERTECH_API_KEY=your_key_here
uv run clevertech-mcp-server
```

```bash
uv run pytest
```

---

## Documentation

- [Clevertech for agents](https://clevertech.ca/agents)
- [API keys](https://clevertech.ca/keys)
- [MCP protocol](https://modelcontextprotocol.io)

---

## License

MIT © Clevertech — see [LICENSE](LICENSE) for details.
