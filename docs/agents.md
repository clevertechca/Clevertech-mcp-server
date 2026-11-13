# CleverTech MCP — Agent Integration Guide

CleverTech is an **MCP-first** platform for Canadian government open data. This server exposes 41 tools for property, permits, zoning, census, public safety, telecom, microwave, business registry, location, and GPS ↔ DLS conversion.

## Install

**PyPI (recommended):**

```bash
uvx clevertech-mcp-server
```

**npm shim (Node.js environments):**

```bash
npx @clevertech/mcp-server
```

## Configuration

### Claude Code / Claude Desktop

```json
{
  "mcpServers": {
    "clevertech": {
      "command": "npx",
      "args": ["-y", "@clevertech/mcp-server"]
    }
  }
}
```

### Cursor / Cline

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

### With an API key

```bash
export CLEVERTECH_API_KEY=your_key_here
uvx clevertech-mcp-server
```

Get a key at https://clevertech.ca/keys

## Pricing

The **free tier** requires no API key: **Try the API. No card.** **50 calls / day**. Paid options (all CAD). Annual billing saves 20% versus monthly.

| Plan | Daily calls | Monthly | Annual |
|------|-------------|---------|--------|
| Free | 50 / day | $0 — Try the API. No card. | $0 — Try the API. No card. |
| Developer | 2,000 / day | $149 CAD/mo | $119 CAD/mo (billed $1,428/yr) |
| Team Pro | 10,000 / day | $499 CAD/mo | $399 CAD/mo (billed $4,788/yr) |
| Enterprise | Custom | Contact sales | Contact sales |
| Prepaid | n/a (never expire) | Starter 2,000 $29 CAD; Project 10,000 $99 CAD; Volume 50,000 $399 CAD | same (pay once) |

Daily allowances, prepaid bundles, and plan details: https://clevertech.ca/pricing

## Tool overview

| Tool | Use when… |
|------|-----------|
| `list_cities` | Discover which cities and APIs are available |
| `property_search` | Look up property by street address |
| `property_by_roll` | Look up property by roll number (faster) |
| `property_report` | Full report: assessment + permits + zoning + DLS |
| `property_nearby` | Properties near a GPS point (`limit` 1–100, `radius_m`) |
| `property_stats` | Aggregate property stats for a city |
| `property_batch` | Batch property lookup by roll numbers |
| `building_permit_search` | Search permits by address or contractor |
| `building_permit_recent` | Monitor newly issued permits |
| `building_permit_nearby` | Permits near a GPS point |
| `building_permit_get` | One permit by id |
| `building_permit_stats` | Aggregate permit stats for a city |
| `building_permit_batch` | Batch permit lookup by numbers |
| `zoning_lookup` | Zoning district at a GPS point or address |
| `zoning_codes` | List zoning codes for a city |
| `zoning_by_code` | Zoning districts by code (`?code=`) |
| `census_lookup_by_gps` | Census profile at a GPS point |
| `census_profile` | Census profile by DA or CSD-style id |
| `census_stats` | Aggregate census stats for a city |
| `census_lookup_by_dls` | Census profile by DLS (thin coverage) |
| `safety_nearby` | Safety incidents near a GPS point |
| `safety_search` | Search involved-person safety rows |
| `safety_stats` | Aggregate safety stats for a city |
| `safety_by_id` | One safety source row by id |
| `safety_summary` | National safety summary (times out cleanly today) |
| `telecom_towers_nearby` | ISED telecom towers near a GPS point |
| `telecom_towers_search` | Search ISED telecom towers |
| `telecom_stats` | National telecom-tower statistics |
| `microwave_nearby` | ISED microwave links near a GPS point |
| `microwave_search` | Search ISED microwave links |
| `microwave_stats` | National microwave-link statistics |
| `microwave_by_authorization` | One microwave authorization by number |
| `business_registry_search` | Search federal corporations |
| `business_registry_get` | One federal corporation by id |
| `business_registry_advanced` | Faceted federal corporation search |
| `business_registry_stats` | Aggregate federal corporation statistics |
| `location_resolve` | Resolve exactly one of address, GPS, or DLS (never send `q`) |
| `location_context` | Nearby datasets at a GPS point (may consume several API calls) |
| `reverse_geocode` | GPS coordinates to address and DLS |
| `dls_convert` | Single GPS ↔ DLS conversion |
| `dls_batch` | Batch GPS ↔ DLS (up to 100 coordinates) |

## Links

- [CleverTech](https://clevertech.ca)
- [Pricing](https://clevertech.ca/pricing)
- [API keys](https://clevertech.ca/keys)
- [llms.txt](../llms.txt) — machine-readable summary
