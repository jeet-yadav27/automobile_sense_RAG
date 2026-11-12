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

    with open("/root/postgres_password", encoding="utf-8") as f:
        pg_password = f.read().strip()

    with open("/root/redis_password", encoding="utf-8") as f:
        redis_password = f.read().strip()

    database_url = (
        "postgresql+psycopg2://rag_user:"
        + quote(pg_password, safe="")
        + "@10.0.0.4:5432/warranty_rag"
    )

    redis_url = (
        "redis://:"
        + quote(redis_password, safe="")
        + "@10.0.0.4:6379/0"
    )

    secrets_url = BASE_URL + f"/listSecrets?api-version={API_VERSION}"
    result = request_json(secrets_url, headers, "POST", {})

    existing = result.get("value", [])

    if not any(s.get("name") == "openai-api-key" for s in existing):
        raise RuntimeError("Existing OpenAI secret missing")

    secrets = [
        s for s in existing
        if s.get("name") not in ("database-url", "redis-url")
    ]

    secrets.extend([
        {"name": "database-url", "value": database_url},
        {"name": "redis-url", "value": redis_url},
    ])

    # Prepare a minimal PATCH payload.
    payload = {
        "properties": {
            "configuration": {
                "secrets": secrets
            }
        }
    }

    print("PATCH_PAYLOAD_PREPARED")
    print("SECRET_NAMES:", [s["name"] for s in secrets])

    # Disabled until PATCH semantics are validated.
    # request_json(
    #     BASE_URL + f"?api-version={API_VERSION}",
    #     headers,
    #     "PATCH",
    #     payload,
    # )

    print("NO_AZURE_CHANGES_MADE")

if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print("AZURE_API_ERROR", exc.code)
        raise SystemExit(1)
    except Exception as exc:
        print("ERROR", type(exc).__name__)
        raise SystemExit(1)
