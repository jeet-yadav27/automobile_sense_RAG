#!/usr/bin/env python3

#!/usr/bin/env python3
import json
import urllib.request
import urllib.error

SUBSCRIPTION = "c6c77d45-019a-40d7-a5cf-ba6a5f7c816b"
RESOURCE_GROUP = "rg-automobile-rag-dev"
APP_NAME = "warranty-rag-backend"
API_VERSION = "2024-03-01"

base = (
    f"https://management.azure.com/subscriptions/{SUBSCRIPTION}"
    f"/resourceGroups/{RESOURCE_GROUP}"
    f"/providers/Microsoft.App/containerApps/{APP_NAME}"
)

metadata_url = (
    "http://169.254.169.254/metadata/identity/oauth2/token"
    "?api-version=2018-02-01"
    + chr(38)
    + "resource=https%3A%2F%2Fmanagement.azure.com%2F"
)

def main():
    token_request = urllib.request.Request(
        metadata_url, headers={"Metadata": "true"}
    )
    with urllib.request.urlopen(token_request, timeout=20) as response:
        token = json.load(response)["access_token"]

    with open("/root/postgres_password", encoding="utf-8") as file:
        password = file.read().strip()

    database_url = (
        f"postgresql+psycopg2://rag_user:{password}"
        "@10.0.0.4:5432/warranty_rag"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Read the existing resource and actual secret values.
    resource_url = base + f"?api-version={API_VERSION}"
    secrets_url = base + f"/listSecrets?api-version={API_VERSION}"

    request = urllib.request.Request(
        resource_url, headers=headers
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        app = json.load(response)

    request = urllib.request.Request(
        secrets_url, headers=headers, data=b"{}", method="POST"
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        existing_secrets = json.load(response).get("value", [])

    secrets = [
        secret for secret in existing_secrets
        if secret["name"] != "database-url"
    ]
    secrets.append({
        "name": "database-url",
        "value": database_url,
    })

    # Preserve the existing Container App configuration.
    app["properties"]["configuration"]["secrets"] = secrets

    # Remove read-only fields.
    for field in ("id", "type", "systemData"):
        app.pop(field, None)

    app["properties"].pop("provisioningState", None)

    # Do not submit the full-resource update until validated.
    # print("DATABASE_SECRET_PAYLOAD_READY")
    # print("AZURE_UPDATE_NOT_EXECUTED")

        # Submit the updated configuration to Azure.
    # Preserve existing secrets, including openai-api-key.
    update_request = urllib.request.Request(
        resource_url,
        headers=headers,
        data=json.dumps(app).encode("utf-8"),
        method="PUT",
    )

    if False:
        with urllib.request.urlopen(update_request, timeout=120) as response:
            print("AZURE_UPDATE_HTTP_STATUS", response.status)

if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print("AZURE_API_ERROR", exc.code)
    except Exception as exc:
        print("ERROR", type(exc).__name__)
