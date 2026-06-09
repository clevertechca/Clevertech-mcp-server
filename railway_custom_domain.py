#!/usr/bin/env python3
"""Configure Railway mcp-server service via GraphQL API."""
import json, os, subprocess

# Token is read from env at runtime — never hardcoded
TOKEN = os.environ.get("RAIL", "") or os.environ.get("RAILWAY_API_TOKEN", "") or os.environ.get("RAILWAY_TOKEN", "")

def gql(query_obj):
    auth_header = "Authorization: Bearer " + TOKEN
    payload = json.dumps(query_obj)
    result = subprocess.run(
        ["curl", "-s", "-H", auth_header, "-H", "Content-Type: application/json",
         "https://backboard.railway.app/graphql/v2", "-d", payload],
        capture_output=True, text=True, timeout=15
    )
    return json.loads(result.stdout)

SVC = "26c3e668-c3f9-4b91-b9e1-9131a7e57e77"
ENV = "1b3ab761-7b65-43e7-931b-17b687f2783f"

# Step 1: Create custom domain
print("=== Creating custom domain mcp.clevertech.ca ===")
r = gql({"query": """
mutation {
  serviceDomainCreate(input: {
    serviceId: \"""" + SVC + """\",
    environmentId: \"""" + ENV + """\",
    domain: "mcp.clevertech.ca"
  }) { id domain status }
}"""})
print(json.dumps(r, indent=2))

# Step 2: Set environment variables
print("\n=== Setting env vars ===")
r2 = gql({"query": """
mutation {
  serviceInstanceUpdate(
    environmentId: \"""" + ENV + """\",
    serviceId: \"""" + SVC + """\",
    input: {
      variables: [
        { name: "CLEVERTECH_API_URL", value: "https://clevertech.ca" },
        { name: "TRANSPORT", value: "sse" },
        { name: "LOG_LEVEL", value: "INFO" },
        { name: "RATE_LIMIT_ANON_DAILY", value: "50" }
      ]
    }
  ) { id }
}"""})
print(json.dumps(r2, indent=2))
