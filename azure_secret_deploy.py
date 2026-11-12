#!/usr/bin/env python3
import json
import urllib.request
import urllib.error

BASE = "https://management.azure.com"
RESOURCE = "/subscriptions/c6c77d45-019a-40d7-a5cf-ba6a5f7c816b/resourceGroups/rg-automobile-rag-dev/providers/Microsoft.App/containerApps/warranty-rag-backend"
API = "2024-03-01"

metadata = "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01" + chr(38) + "resource=https%3A%2F%2Fmanagement.azure.com%2F"
token_request = urllib.request.Request(metadata, headers={"Metadata": "true"})
with urllib.request.urlopen(token_request, timeout=20) as response:
    token = json.load(response)["access_token"]

with open("/root/postgres_password", encoding="utf-8") as f:
    password = f.read().strip()

connection = "postgresql+psycopg2://rag_user:" + password + "@10.0.0.4:5432/warranty_rag"
url = BASE + RESOURCE + "?api-version=" + API
headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

try:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        app = json.load(response)
        # Retrieve existing secret values securely.
    secrets_url = BASE + RESOURCE + "/listSecrets?api-version=" + API
    req = urllib.request.Request(
        secrets_url, data=b"{}",
        headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        existing = json.load(response).get("value", [])

    secrets = [s for s in existing if s["name"] != "database-url"]
    secrets.append({"name": "database-url", "value": connection})

    # Prepare the updated configuration without applying it.
    app["properties"]["configuration"]["secrets"] = secrets
    print("DATABASE_SECRET_PAYLOAD_READY")
except urllib.error.HTTPError as exc:
    print("AZURE_API_ERROR", exc.code)
