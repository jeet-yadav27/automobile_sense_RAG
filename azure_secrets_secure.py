#!/usr/bin/env python3

#!/usr/bin/env python3

import json
import urllib.request
import urllib.error
from urllib.parse import quote

SUBSCRIPTION = "c6c77d45-019a-40d7-a5cf-ba6a5f7c816b"
RESOURCE_GROUP = "rg-automobile-rag-dev"
APP_NAME = "warranty-rag-backend"
API_VERSION = "2024-03-01"

BASE_URL = (
    f"https://management.azure.com/subscriptions/{SUBSCRIPTION}"
    f"/resourceGroups/{RESOURCE_GROUP}"
    f"/providers/Microsoft.App/containerApps/{APP_NAME}"
)

def request_json(url, headers, method="GET", payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, headers=headers, data=data, method=method
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)

def main():
    # Obtain Azure token from VM managed identity.
    token_url = (
        "http://169.254.169.254/metadata/identity/oauth2/token"
        "?api-version=2018-02-01"
        "&resource=https%3A%2F%2Fmanagement.azure.com%2F"
    )
    token_req = urllib.request.Request(
        token_url, headers={"Metadata": "true"}
    )
    with urllib.request.urlopen(token_req, timeout=20) as response:
        token = json.load(response)["access_token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Read passwords only on the VM.
    with open("/root/postgres_password", encoding="utf-8") as f:
        pg_password = f.read().strip()

    with open("/root/redis_password", encoding="utf-8") as f:
        redis_password = f.read().strip()

    database_url = (
        "postgresql+psycopg://rag_user:"
        + quote(pg_password, safe="")
        + "@10.0.0.4:5432/warranty_rag"
    )

    redis_url = (
        "redis://:"
        + quote(redis_password, safe="")
        + "@10.0.0.4:6379/0"
    )

    resource_url = BASE_URL + f"?api-version={API_VERSION}"
    secrets_url = BASE_URL + f"/listSecrets?api-version={API_VERSION}"

    # Retrieve existing app configuration and secrets.
    app = request_json(resource_url, headers)
    result = request_json(secrets_url, headers, "POST", {})
    existing = result.get("value", [])

    existing_names = {s["name"] for s in existing}
    if "openai-api-key" not in existing_names:
        raise RuntimeError("Existing OpenAI secret not found; stopping")

    # Preserve all existing secrets.
    secrets = [
        s for s in existing
        if s["name"] not in ("database-url", "redis-url")
    ]

    secrets.extend([
        {"name": "database-url", "value": database_url},
        {"name": "redis-url", "value": redis_url},
    ])

    # Keep existing Container App settings.
    app["properties"]["configuration"]["secrets"] = secrets

    # Remove read-only metadata.
    for field in ("id", "type", "systemData", "etag"):
        app.pop(field, None)

    for field in (
        "provisioningState",
        "runningStatus",
        "latestRevisionName",
        "latestReadyRevisionName",
        "outboundIpAddresses",
        "eventStreamEndpoint",
        "customDomainVerificationId",
    ):
        app["properties"].pop(field, None)

    # Submit the update.

        # Verify that the resource still matches our intended target.
    if app.get("name") != APP_NAME:
        raise RuntimeError("Unexpected Container App; update cancelled")

    # Confirm existing secrets before any write.
    names = {s["name"] for s in secrets}
    required = {"openai-api-key", "database-url", "redis-url"}

    if not required.issubset(names):
        raise RuntimeError("Required secrets missing; update cancelled")

    request_json(resource_url, headers, "PUT", app)
    print("AZURE_UPDATE_REQUEST_ACCEPTED")

    print("PRE_UPDATE_VALIDATION_PASSED")
    print("SECRET_NAMES:", sorted(names))
    print("NO_AZURE_CHANGES_MADE")
    print("Secret update is ready for validation; no changes submitted")

    print("AZURE_UPDATE_REQUEST_COMPLETED")

if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print("AZURE_API_ERROR", exc.code)
        try:
            error=json.loads(exc.read().decode("utf-8")).get("error", {})
            print("ERROR_CODE:", error.get("code", "Unknown"))
            print("ERROR_MESSAGE:", error.get("message", "Unavailable")[:500])
        except Exception:
            print("ERROR_DETAILS_UNAVAILABLE")
        raise SystemExit(1)
    except Exception as exc:
        print("ERROR", type(exc).__name__)
        raise SystemExit(1)
