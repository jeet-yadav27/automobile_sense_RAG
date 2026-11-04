import json
import os
import urllib.request
import urllib.error

QDRANT_URL = (
    "https://ca-warranty-qdrant.internal."
    "thankfulground-de43a748.centralindia.azurecontainerapps.io"
)

snapshot_url = os.environ["SNAPSHOT_URL"]

endpoint = (
    f"{QDRANT_URL}/collections/"
    "spresso_manual_full/snapshots/recover?wait=true"
)

payload = json.dumps({
    "location": snapshot_url,
    "priority": "snapshot"
}).encode("utf-8")

request = urllib.request.Request(
    endpoint,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="PUT"
)

try:
    with urllib.request.urlopen(request, timeout=300) as response:
        print(response.read().decode())
except urllib.error.HTTPError as error:
    print("HTTP status:", error.code)
    print(error.read().decode())
except Exception as error:
    print("Restore failed:", type(error).__name__)
