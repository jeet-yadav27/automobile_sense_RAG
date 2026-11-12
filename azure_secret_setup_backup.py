#!/usr/bin/env python3

import json
import urllib.request
import urllib.error

SUBSCRIPTION = "c6c77d45-019a-40d7-a5cf-ba6a5f7c816b"
RESOURCE_GROUP = "rg-automobile-rag-dev"
APP_NAME = "warranty-rag-backend"

metadata_url = (
    "http://169.254.169.254/metadata/identity/oauth2/token"
    "?api-version=2018-02-01"
    "&resource=https%3A%2F%2Fmanagement.azure.com%2F"
)

resource_url = (
    f"https://management.azure.com/subscriptions/{SUBSCRIPTION}"
    f"/resourceGroups/{RESOURCE_GROUP}"
    f"/providers/Microsoft.App/containerApps/{APP_NAME}"
    "?api-version=2024-03-01"
)

def request_json(url, token=None, data=None, method=None):
    headers = {"Metadata": "true"} if token is None else {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    request = urllib.request.Request(
        url,
        headers=headers,
        data=json.dumps(data).encode() if data is not None else None,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

def main():
    token = request_json(metadata_url)["access_token"]

    with open("/root/postgres_password", encoding="utf-8") as file:
        password = file.read().strip()

    database_url = (
        f"postgresql+psycopg2://rag_user:{password}"
        "@10.0.0.4:5432/warranty_rag"
    )

    # Fetch the complete current Container App resource.
    app = request_json(resource_url, token)

    # Preserve existing secrets by name without copying redacted values.
    config = app["properties"]["configuration"]
    secrets = config.get("secrets") or []

    if any(s["name"] == "database-url" for s in secrets):
        print("DATABASE_SECRET_ALREADY_EXISTS")
        return

    secrets.append({"name": "database-url", "value": database_url})

    # Update only the secrets configuration.
    request_json(
        resource_url,
        token,
        {"properties": {"configuration": {"secrets": secrets}}},
        "PATCH",
    )
    print("DATABASE_SECRET_REQUEST_ACCEPTED")

if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print("AZURE_API_ERROR", exc.code)
        print("Request rejected; response body withheld because it may contain sensitive information.")
    except Exception as exc:
    	print("SETUP_FAILED", type(exc).__name__)
