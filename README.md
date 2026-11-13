# Clevertech MCP Server

<!-- mcp-name: ca.clevertech/clevertech-mcp-server -->

**Canadian government and municipal open data for AI agents.** Census profiles, public safety, telecom and microwave licensing, business registry, location / DLS / geocoding, property assessments, zoning, and building permits — from a single MCP server.

```bash
uvx clevertech-mcp-server
```

Free tier: **Try the API. No card.** **50 calls / day** with no API key required. Optional `CLEVERTECH_API_KEY` for paid daily allowances. Keys: [clevertech.ca/keys](https://clevertech.ca/keys). Plans: [clevertech.ca/pricing](https://clevertech.ca/pricing).

[![PyPI version](https://badge.fury.io/py/clevertech-mcp-server.svg)](https://pypi.org/project/clevertech-mcp-server/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Quick Start

1. Run `uvx clevertech-mcp-server` (free tier works without a key)
2. Optional: create an API key at [https://clevertech.ca/keys](https://clevertech.ca/keys) and set `CLEVERTECH_API_KEY` for higher daily limits
3. Add the server to your MCP client config (examples below)

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

Or paste your key directly as the `CLEVERTECH_API_KEY` string value. Omit `env` entirely to use the free tier.

### Direct CLI

```bash
uvx clevertech-mcp-server
```

With a key:

```bash
export CLEVERTECH_API_KEY=your_key_here
uvx clevertech-mcp-server
```

---

## Available Tools (41)

Use `list_cities` for live coverage. Cities span Alberta, BC, Ontario, Quebec, Manitoba, Saskatchewan, Nova Scotia, Newfoundland, and more.

### Census

| Tool | Description |
|------|-------------|
| `census_lookup_by_gps` | Statistics Canada census profile at a GPS point (DA, population, age, income) |
| `census_profile` | Census profile by dissemination-area (DA) or CSD-style id |
| `census_stats` | Aggregate census stats for a city — profile count and years |
| `census_lookup_by_dls` | Census profile by DLS legal land description (thin coverage; clear miss message) |

### Safety

| Tool | Description |
|------|-------------|
| `safety_nearby` | Public-safety incidents near a GPS point |
| `safety_search` | Search involved-person safety rows by keyword |
| `safety_stats` | Aggregate safety stats for a city (counts by injury) |
| `safety_by_id` | One safety source row by id (colons URL-encoded) |
| `safety_summary` | National safety summary (`/api/v2/safety/summary`) |

### Telecom / microwave

| Tool | Description |
|------|-------------|
| `telecom_towers_nearby` | ISED telecom towers near a GPS point (default limit 1, `radius_km` default 5) |
| `telecom_towers_search` | Search ISED telecom towers by carrier / keyword |
| `telecom_stats` | National telecom-tower statistics |
| `microwave_nearby` | ISED microwave links near a GPS point (default radius 2 km) |
| `microwave_search` | Search ISED microwave links by licensee / keyword |
| `microwave_stats` | National microwave-link statistics |
| `microwave_by_authorization` | One microwave authorization by number |

### Business registry

| Tool | Description |
|------|-------------|
| `business_registry_search` | Federal corporation search by name, province, or city |
| `business_registry_get` | One federal corporation by id |
| `business_registry_advanced` | Faceted federal corporation search (`act`, `corporation_type`) |
| `business_registry_stats` | Aggregate federal corporation statistics |

### Location / DLS / geocoding

| Tool | Description |
|------|-------------|
| `location_resolve` | Resolve exactly one of address, GPS, or DLS via POST LocationRequest (never `q`) |
| `location_context` | Nearby datasets at a GPS point (may consume several API calls) |
| `reverse_geocode` | GPS → address, city, neighborhood, province, and DLS grid reference |
| `dls_convert` | GPS ↔ Dominion Land Survey (DLS) for Western Canada |
| `dls_batch` | Batch GPS ↔ DLS (up to 100 coordinates) |
| `list_cities` | Cities, capabilities, and property counts |

### Property

| Tool | Description |
|------|-------------|
| `property_search` | Property assessment search by address |
| `property_report` | Consolidated property report — assessment, permits, zoning, and DLS |
| `property_by_roll` | Lookup by roll number |
| `property_nearby` | Properties near a GPS point (`limit` 1–100, optional `radius_m`) |
| `property_stats` | Aggregate property assessment statistics for a city |
| `property_batch` | Batch property lookup by roll numbers |

### Zoning

| Tool | Description |
|------|-------------|
| `zoning_lookup` | Zoning district lookup by GPS coordinates or street address |
| `zoning_codes` | List zoning district codes for a city |
| `zoning_by_code` | Zoning districts by code (`?code=`; slashes work, e.g. CR20-C20/R20) |

### Permits

| Tool | Description |
|------|-------------|
| `building_permit_search` | Building permits by address, contractor, applicant, or number |
| `building_permit_recent` | Recently issued permits feed |
| `building_permit_nearby` | Building permits near a GPS point |
| `building_permit_get` | One building permit by id |
| `building_permit_stats` | Aggregate building-permit statistics for a city |
| `building_permit_batch` | Batch building-permit lookup by permit numbers |

---

## Pricing (CAD)

Source of truth: [clevertech.ca/pricing](https://clevertech.ca/pricing). Paid plans apply the same daily quotas to the REST API and the CleverTech MCP server (`uvx clevertech-mcp-server`). All prices are in CAD. Annual billing saves 20% versus monthly.

### Subscriptions

| Plan | Daily allowance | Price |
|------|-----------------|-------|
| **Free** | 50 calls / day | $0 — Try the API. No card. |
| **Developer** | 2,000 calls / day | $149/mo (billed $1,428/yr) |
| **Team Pro** | 10,000 calls / day | $499/mo (billed $4,788/yr) |
| **Enterprise** | Custom allowance | Contact sales |

**Free** (from the live pricing page): all 9 datasets, 100 results per query, 30 req/min, limited API key, web and MCP, DLS conversions (5 calls each), community support.

**Developer** — for builders and solo surveyors: everything in Free, 250 results per query, 120 req/min, CSV and JSON export, email support.

**Team Pro** — for firms and municipalities: everything in Developer, 500 results per query, 600 req/min, batch lookup (10K records), webhook alerts, up to 5 seats, priority support.

**Enterprise** — extra seats, SLA and invoicing, bulk extracts, custom allowance, dedicated support.

The [agents](https://clevertech.ca/agents) page matches these plan names and prices: Free $0 (50 queries / day, no API key required), Developer $149/mo, Team Pro $499/mo, Enterprise custom.

### Prepaid API calls

No subscription. Purchase once and use the calls whenever you need them. They never expire. Available to any signed-in account. Your daily allowance is used first; prepaid calls are used only after that allowance is exhausted.

| Bundle | Calls | Price |
|--------|-------|-------|
| **Starter** | 2,000 calls | $29 CAD |
| **Project** | 10,000 calls | $99 CAD |
| **Volume** | 50,000 calls | $399 CAD |

Daily allowance resets at midnight Mountain Time; unused daily calls do not roll over. DLS conversions cost 5 calls. Batch lookups cost 1 call + 0.1 per record.

Get a key: [https://clevertech.ca/keys](https://clevertech.ca/keys)

---

## Features

- MCP stdio server for Cursor, Claude, Copilot, and other MCP clients
- 41 tools across census, safety, telecom/microwave, business registry, location/DLS/geocoding, property, zoning, and permits
- PyPI package: [`clevertech-mcp-server`](https://pypi.org/project/clevertech-mcp-server/)
- MIT licensed

---

## Development

```bash
git clone https://github.com/clevertechca/Clevertech-mcp-server.git
cd Clevertech-mcp-server
uv sync
uvx clevertech-mcp-server
# or, from a checkout:
uv run clevertech-mcp-server
```

```bash
uv run pytest
```

---

## Documentation

- [Clevertech for agents](https://clevertech.ca/agents)
- [Pricing](https://clevertech.ca/pricing)
- [API keys](https://clevertech.ca/keys)
- [Agent integration guide](docs/agents.md)
- [llms.txt](llms.txt)
- [MCP protocol](https://modelcontextprotocol.io)

---

## License

MIT © Clevertech — see [LICENSE](LICENSE) for details.
