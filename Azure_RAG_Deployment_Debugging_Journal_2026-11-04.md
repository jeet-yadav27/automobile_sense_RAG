# Azure Enterprise RAG Deployment — Daily Engineering Journal

**Date:** 4 November 2026  
**Project:** S-Presso Automobile Manual Enterprise RAG  
**Local workspace:** `D:\warranty_RAG`  
**Azure region:** Central India  
**Resource group:** `rg-automobile-rag-dev`  
**Status at end of session:** Qdrant collection migrated and validated; PostgreSQL deployment not yet started.

> **Security:** This journal deliberately excludes account keys, OpenAI API keys, and signed Blob SAS tokens. Never commit those credentials to Git or paste them into issue trackers.

## 1. Session objectives

The larger goal is to deploy the existing local Enterprise RAG application to Azure and gain practical experience with Azure Container Apps, networking, storage, deployment, security, monitoring, and CI/CD.

Today's concrete goals were to establish connectivity to a private Qdrant service running in Azure Container Apps, migrate the existing S-Presso manual vectors from local Docker without paying to regenerate embeddings, and validate the restored collection.

### Application architecture

```text
                        [React + Vite frontend]
                                  |
                            [FastAPI API]
                             /    |     \
                            /     |      \
                  [PostgreSQL] [Redis] [Qdrant]
                    users,     cache,   manual vectors
                    chats      limits   + payloads
                                       |
                              spresso_manual_full
                                  2,412 points
```

**Current state:** Only the Qdrant portion is confirmed operational on Azure. The frontend, backend, PostgreSQL, and Redis still need deployment/integration verification. The local app previously used Docker Compose, FastAPI, React/Vite, PostgreSQL, Redis, Qdrant, hybrid retrieval, and CrossEncoder reranking.

## 2. Azure resources and configuration

| Resource | Identifier | Observed status |
|---|---|---|
| Resource group | `rg-automobile-rag-dev` | In use |
| Container Apps environment | `cae-automobile-rag-dev` | In use |
| Qdrant Container App | `ca-warranty-qdrant` | Healthy; private ingress |
| Temporary diagnostic Container App | `ca-qdrant-helper` | Created, healthy, used for tests; cleanup not yet confirmed |
| Storage account | `automobileragst2026` | Used for snapshot upload |
| Blob container | `qdrant-snapshots` | Existing private container |
| Azure Files environment storage registration | `qdrantstorage` | Registered but **not mounted** into Qdrant |
| Azure Files share | `qdrant-data` | Created earlier; not used for active Qdrant data |
| Container Registry | `automobileragacr2026.azurecr.io` | Exists; backend image push not yet verified |

**Qdrant ingress as observed:**

```json
{
  "external": false,
  "allowInsecure": false,
  "targetPort": 6333,
  "transport": "Auto",
  "fqdn": "ca-warranty-qdrant.internal.thankfulground-de43a748.centralindia.azurecontainerapps.io"
}
```

**Meaning:** `external: false` makes the ingress private to the relevant Container Apps network boundary. The app listens on Qdrant's HTTP API port 6333 behind Container Apps ingress. The HTTPS FQDN works from the helper app in the same environment. The short internal service name `http://ca-warranty-qdrant` also worked from the helper.

## 3. Timeline: challenges, debugging, fixes, and lessons

### Challenge A — Helper Container App creation failed due to CLI argument parsing

An initial attempt to create a Python helper with `--command python --args "-c" "import time; time.sleep(86400)"` failed:

```text
unrecognized arguments: -c import time; time.sleep(86400)
```

Subsequent `revision list` and `exec` commands returned `ResourceNotFound` because the helper had not been created.

**Resolution:** A simpler long-running helper using the `python:3.12-slim` image and a sleep command was successfully created. The first revision was initially `Activating`, then became:

```text
Name                       Health    Running
ca-qdrant-helper--tl6nq6h  Healthy   RunningAtMaxScale
```

A later `exec` session showed helper revision `ca-qdrant-helper--0000002`, indicating the helper had subsequently been revised. The reason for that revision change was not established in the provided logs.

**Lesson:** Check whether a resource was actually created before attempting to exec into it. `Activating` is not automatically a failure; inspect status and logs if it persists.

Useful commands:

```cmd
az containerapp revision list --name ca-qdrant-helper --resource-group rg-automobile-rag-dev --query "[].{Name:name,Health:properties.healthState,Running:properties.runningState}" --output table
az containerapp logs show --name ca-qdrant-helper --resource-group rg-automobile-rag-dev --type system --tail 30
az containerapp exec --name ca-qdrant-helper --resource-group rg-automobile-rag-dev --command /bin/sh
```

### Challenge B — Testing an internal Qdrant URL from the Windows host

An early test from Windows using the internal FQDN over HTTP returned HTTP 404. That alone did not establish whether Qdrant was broken: the request path, ingress routing, protocol, and client network location all needed verification.

**Resolution:** Exec into the helper **inside the same Container Apps environment** and test the Qdrant API:

```sh
python -c 'import urllib.request; u="https://ca-warranty-qdrant.internal.thankfulground-de43a748.centralindia.azurecontainerapps.io/collections"; print(urllib.request.urlopen(u,timeout=20).read().decode())'
```

Observed response:

```json
{"result":{"collections":[]},"status":"ok","time":4.1e-6}
```

The short service name also worked:

```sh
python -c 'import urllib.request; print(urllib.request.urlopen("http://ca-warranty-qdrant/collections",timeout=20).read().decode())'
```

**Lesson:** Internal service connectivity should be verified from a client with access to that internal environment. A working `/collections` API with an empty array means Qdrant is running but contains no collections.

### Challenge C — Collection missing in Azure

The API call to `/collections/spresso_manual_full` returned HTTP 404. Since `/collections` returned an empty array, this was a **missing collection**, not a network outage.

**Decision:** Migrate the existing local collection using a Qdrant snapshot instead of regenerating OpenAI embeddings.

### Challenge D — Local collection verification and snapshot creation

Local Qdrant was reachable at `http://127.0.0.1:6333`.

```cmd
curl http://127.0.0.1:6333/collections/spresso_manual_full
```

Verified local collection:

| Field | Value |
|---|---|
| Collection | `spresso_manual_full` |
| Status | `green` |
| Optimizer status | `ok` |
| Points | **2,412** |
| Dense vector size | **1,536** |
| Distance | **Cosine** |
| Segments | 6 |
| `indexed_vectors_count` | 0 (as reported by Qdrant; **not** the point count) |

Create snapshot:

```cmd
curl -X POST http://127.0.0.1:6333/collections/spresso_manual_full/snapshots
```

Returned snapshot metadata:

```json
{
  "result": {
    "name": "spresso_manual_full-4582086347273136-2026-11-04-16-41-07.snapshot",
    "creation_time": "2026-11-04T16:41:07",
    "size": 31541760,
    "checksum": "6ff6e4138e8520cf067af6c841c8262d05b145e4004d593e754d69a509166a7e"
  },
  "status": "ok"
}
```

Download to Windows:

```cmd
curl -L -o spresso_manual_full.snapshot "http://127.0.0.1:6333/collections/spresso_manual_full/snapshots/spresso_manual_full-4582086347273136-2026-11-04-16-41-07.snapshot"
dir spresso_manual_full.snapshot
```

Verified local file size: **31,541,760 bytes** (~30.08 MiB / 31.54 MB).

**Lesson:** A Qdrant collection snapshot preserves existing vectors and payloads, avoiding a full re-embedding run. Retain the original local Docker volume and snapshot until the cloud environment is durable and validated.

### Challenge E — Azure Files registered but not mounted

Commands:

```cmd
az containerapp show --name ca-warranty-qdrant --resource-group rg-automobile-rag-dev --query "{Volumes:properties.template.volumes,Mounts:properties.template.containers[].volumeMounts}" --output json
az containerapp env storage list --name cae-automobile-rag-dev --resource-group rg-automobile-rag-dev --output table
```

Observed:

```json
{"Mounts":[],"Volumes":null}
```

Environment storage list showed `qdrantstorage`.

**Root cause:** Environment-level storage registration is not the same as a volume mount in a Container App revision. Qdrant has **no mounted persistent volume**.

**Decision:** Do **not** mount SMB-backed Azure Files as Qdrant's live database directory. Qdrant's storage needs suitable filesystem semantics. For this temporary learning exercise, restore to ephemeral storage and retain the snapshot in Blob Storage; choose a supported durable storage solution before production use.

**Risk:** Qdrant data may disappear if the replica is replaced or rescheduled. A healthy revision is not proof of durable data.

### Challenge F — Azure Blob upload failed with Entra ID authentication

Initial command:

```cmd
az storage blob upload --account-name automobileragst2026 --container-name qdrant-snapshots --name spresso_manual_full.snapshot --file spresso_manual_full.snapshot --auth-mode login --overwrite true
```

Error:

```text
You do not have the required permissions needed to perform this operation.
```

**Root cause:** The signed-in principal lacked the required Blob data-plane permission (for example, `Storage Blob Data Contributor`) for that upload. Azure control-plane access and Blob data-plane access are separate.

**Temporary learning-project workaround:** Use a storage account key, if authorized and if shared-key authentication is enabled. The user successfully retrieved a key into a local CMD environment variable, without displaying it:

```cmd
for /f "delims=" %K in ('az storage account keys list --resource-group rg-automobile-rag-dev --account-name automobileragst2026 --query "[0].value" --output tsv') do @set "AZURE_STORAGE_KEY=%K"
if defined AZURE_STORAGE_KEY (echo Key configured) else (echo Key missing)
```

Create/confirm the private container:

```cmd
az storage container create --account-name automobileragst2026 --account-key "%AZURE_STORAGE_KEY%" --name qdrant-snapshots --public-access off
```

Returned `{"created": false}`, meaning the container **already existed** (not an error).

Upload:

```cmd
az storage blob upload --account-name automobileragst2026 --account-key "%AZURE_STORAGE_KEY%" --container-name qdrant-snapshots --name spresso_manual_full.snapshot --file spresso_manual_full.snapshot --overwrite true
```

Observed `100.0000%` upload success; response indicated `request_server_encrypted: true`.

**Production preference:** Use Microsoft Entra ID, least-privilege Blob data RBAC, and managed identities where applicable, rather than storage account keys.

### Challenge G — Generating and handling a signed Blob URL

Qdrant needed temporary read access to the private Blob snapshot. The chosen transfer method was a **short-lived, read-only SAS URL**.

Example command (choose a **future UTC expiry** when running):

```cmd
az storage blob generate-sas --account-name automobileragst2026 --account-key "%AZURE_STORAGE_KEY%" --container-name qdrant-snapshots --name spresso_manual_full.snapshot --permissions r --expiry 2026-11-05T12:00Z --https-only --full-uri --output tsv
```

**Important:** The example expiry above was appropriate for the session but will expire; update it if repeating the process. Do not paste a SAS URL into chat or logs. Treat it as a temporary credential.

### Challenge H — Windows CMD versus Python syntax

The user tried this at a **Windows CMD** prompt:

```cmd
print("Valid URL:", url.startswith("https://") and "sig=" in url)
```

CMD returned:

```text
Unable to initialize device PRN
```

**Root cause:** `print(...)` is Python syntax, not a Windows CMD command. CMD interprets `print` as a different Windows command.

**Lesson:** Watch the prompt:

| Prompt | Environment | Valid examples |
|---|---|---|
| `(.venv) D:\warranty_RAG>` | Windows CMD | `az ...`, `curl ...`, `dir ...` |
| `#` | Linux shell in helper container | `python`, `cat`, `exit` |
| `>>>` | Python REPL | `import json`, `print(...)` |
| `...` | Python REPL continuation | Finish statement, then blank Enter |

### Challenge I — Interactive paste, line wrapping, and `getpass`

In the helper's Python REPL:

```python
import getpass
url = getpass.getpass("Paste signed Blob URL: ")
print("Valid URL:", url.startswith("https://") and "sig=" in url)
```

Observed:

```text
Valid URL: True
```

**Meaning:** The user successfully pasted the SAS URL. `getpass()` intentionally hides pasted characters; an invisible input is not necessarily a failed paste.

The user also used CMD clipboard syntax:

```cmd
<nul set /p "=%SNAPSHOT_URL%" | clip
```

**Caution:** A SAS URL contains `&` and other shell-significant characters. Avoid echoing it unquoted or accidentally logging it. Copying or transferring secrets should be done carefully, preferably using a managed identity in a production design.

### Challenge J — Python REPL `SyntaxError` and `IndentationError`

A multiline `urllib.request.Request(...)` call was pasted in fragments. Python produced errors including:

```text
SyntaxError: invalid syntax
IndentationError: unexpected indent
SyntaxError: unmatched ')'
```

**Root cause:** Partial or malformed multiline input in the Python interactive prompt.

**Resolution:** Use single-line statements where possible, or write a complete `.py` file in the Linux shell. When using `try/except` in the REPL, press **Enter on a blank line** after the final `...` continuation line to execute the block.

### Challenge K — HTTP 301 during snapshot recovery

An initial recovery request returned:

```text
urllib.error.HTTPError: HTTP Error 301: Moved Permanently
```

**Likely root cause:** Calling the full internal FQDN with `http://` while ingress was configured with `allowInsecure: false` and HTTPS was required for that FQDN. The exact redirect headers were not captured, so this remains the most plausible explanation rather than a formally verified root cause.

**Resolution:** Use the internal HTTPS FQDN, or the working short service name from the same environment.

Example endpoint:

```python
endpoint = "https://ca-warranty-qdrant.internal.thankfulground-de43a748.centralindia.azurecontainerapps.io/collections/spresso_manual_full/snapshots/recover?wait=true"
```

Recovery request:

```python
import json
import urllib.request
import urllib.error
import getpass

url = getpass.getpass("Paste signed Blob URL: ").strip()
payload = json.dumps({"location": url, "priority": "snapshot"}).encode()
req = urllib.request.Request(
    endpoint,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="PUT"
)
try:
    response = urllib.request.urlopen(req, timeout=300)
    print(response.read().decode())
except urllib.error.HTTPError as e:
    print("HTTP status:", e.code, "Response:", e.read().decode())
```

**Note:** `timeout=300` is a network operation timeout setting, not a guaranteed maximum for all work. `wait=true` asks Qdrant to wait for the recovery operation to finish before responding.

### Challenge L — Recovery success and final validation

Recovery returned:

```json
{"result":true,"status":"ok","time":0.575844064}
```

Then the user queried the restored Azure collection:

```python
check_url = "http://ca-warranty-qdrant/collections/spresso_manual_full"
result = json.load(urllib.request.urlopen(check_url, timeout=30))
print("Status:", result["result"]["status"])
print("Points:", result["result"]["points_count"])
print("Vectors:", result["result"]["config"]["params"]["vectors"])
```

**Observed final result:**

```text
Status: green
Points: 2412
Vectors: {'size': 1536, 'distance': 'Cosine'}
```

**Outcome:** The Qdrant collection migration was **successful and verified**. This confirms collection health, point count, and dense-vector configuration. It does **not** yet prove the complete RAG chat application is deployed or that data will survive a Container App replacement.

## 4. Final migration workflow

```text
Local Qdrant (Docker, localhost:6333)
    |
    | POST /collections/spresso_manual_full/snapshots
    v
Qdrant snapshot (31,541,760 bytes)
    |
    | curl download to D:\warranty_RAG
    v
Windows file: spresso_manual_full.snapshot
    |
    | az storage blob upload (authorized account key)
    v
Private Azure Blob container: qdrant-snapshots
    |
    | short-lived read-only SAS URL
    v
Temporary Python helper inside Azure Container Apps
    |
    | PUT /collections/spresso_manual_full/snapshots/recover?wait=true
    v
Internal Azure Qdrant Container App
    |
    | GET /collections/spresso_manual_full
    v
Verified: green, 2,412 points, 1,536-dimensional cosine vectors
```

## 5. Key Azure concepts learned

**Azure Container Apps:** Hosts containerized workloads. A revision has its own lifecycle and health status. A Container Apps environment provides networking and other shared configuration.

**Internal ingress:** Enables service access inside the supported internal networking boundary. A private service should be tested from a client in the appropriate environment, not assumed reachable from a local laptop.

**FQDN versus service name:** The full internal FQDN was reachable over HTTPS from the helper; the short service name was reachable over HTTP within the environment. Respect the ingress protocol and redirects.

**Azure Storage data-plane RBAC:** Being signed in to Azure or able to manage a resource does not automatically grant permission to read/write its Blob data.

**Storage account keys:** Can provide broad data access where enabled; appropriate only as a controlled temporary workaround in this exercise. Avoid long-term distribution.

**SAS tokens:** Temporarily grant scoped access to a Blob. A read-only SAS is sufficient for a snapshot recovery operation that downloads a Blob. Keep it short-lived and private.

**Qdrant snapshots:** Portable collection backups that preserve existing embeddings and payloads. Restore them through Qdrant's recovery API, checking version compatibility as necessary.

**Environment storage versus mounted volume:** Registering `qdrantstorage` at the environment level did not mount anything into Qdrant (`Volumes: null`, `Mounts: []`).

**Ephemeral versus persistent storage:** The successful restore exists in the currently running Qdrant container but is **not yet durable** across replica replacement. A Blob snapshot is a recovery source, not a live database volume.

**REPL troubleshooting:** Windows CMD, Linux shell, and Python REPL use different syntax and prompts. A trailing `...` requires completion of the compound statement, often with a blank line.

## 6. Verified results versus open questions

| Item | Verified? | Evidence / caveat |
|---|---|---|
| Local collection healthy | Yes | `green`, 2,412 points |
| Local snapshot created | Yes | 31,541,760 bytes |
| Blob snapshot uploaded | Yes | Azure CLI 100% success |
| Internal Qdrant reachable | Yes | `/collections` returned `status: ok` |
| Snapshot recovery accepted | Yes | `result: true`, `status: ok` |
| Azure collection health | Yes | `green` |
| Azure point count | Yes | 2,412 |
| Vector configuration | Yes | 1,536 dimensions, Cosine |
| Qdrant durable storage | **No** | No mounted volumes |
| Backend ACR image published | Not confirmed | Earlier large-image push was interrupted |
| PostgreSQL deployed to Azure | Not confirmed / not yet started in this session | Next planned stage |
| Redis deployed to Azure | Not confirmed | Planned |
| React/FastAPI end-to-end working on Azure | No evidence yet | Requires deployment and testing |
| Helper deleted | Not confirmed | Remove after no longer needed |

## 7. Next steps — remaining deployment workstreams

1. **Secure Qdrant persistence:** Choose a Qdrant-supported durable storage strategy (for example, managed Qdrant or an appropriate VM/block-disk architecture); retain the Blob snapshot until this is resolved.
2. **Deploy PostgreSQL:** Check Central India SKU availability and current resources, estimate costs, choose network access, configure database credentials/TLS, and run Alembic migrations.
3. **Deploy Redis:** Choose a low-cost suitable option; set up connectivity, authentication, and rate-limiting configuration.
4. **Build/push FastAPI image:** Confirm dependencies (`fastembed`, `sentence-transformers`, etc.), optimize Docker image, complete ACR push, configure environment variables/secrets, and deploy Container App.
5. **Deploy React/Vite frontend:** Publish frontend image, configure ingress, Nginx/backend routing, CORS, authentication cookies, and HTTPS.
6. **End-to-end verification:** Test login, sessions, document retrieval, citations, chat persistence, concurrency, and failure handling.
7. **Operational readiness:** Add logs/metrics/alerts, cost monitoring, GitHub Actions CI/CD, deployment rollback, and optional Terraform infrastructure-as-code.

**Next planned commands (not yet run in the visible session):**

```cmd
az postgres flexible-server list-skus --location centralindia --output table
az postgres flexible-server list --resource-group rg-automobile-rag-dev --output table
```

**Cleanup when helper is no longer needed:**

```cmd
az containerapp delete --name ca-qdrant-helper --resource-group rg-automobile-rag-dev --yes
```

**Clear local CMD key after finishing Blob operations:**

```cmd
set "AZURE_STORAGE_KEY="
```

## 8. Interview-ready summary

> I migrated an existing RAG vector database from local Docker to Azure Container Apps. I configured and verified internal ingress, used a temporary in-environment diagnostic container to isolate networking issues, created a Qdrant collection snapshot, uploaded it to private Azure Blob Storage, and restored it using a short-lived read-only SAS URL and the Qdrant recovery API. I troubleshot Azure Blob RBAC authorization failures, HTTP-to-HTTPS redirection, and Python REPL issues. I validated the recovered collection as healthy with 2,412 points and 1,536-dimensional cosine vectors. I also identified that the Container App had no persistent volume mounted, so I retained the Blob backup and flagged durable Qdrant storage as a prerequisite for production readiness.

## 9. Troubleshooting cheat sheet

| Symptom | Likely interpretation | Next diagnostic action |
|---|---|---|
| `ResourceNotFound` for helper | Creation failed or wrong resource name | Check `az containerapp list` and revision list |
| Helper `Activating` | Startup in progress or stalled | Recheck revision status; inspect system logs |
| `/collections` returns `[]` | Qdrant running, no collections | Restore/reindex collection |
| Collection GET returns 404 | Collection missing | List collections first |
| Blob upload `required permissions` | Missing data-plane RBAC | Assign proper role or use authorized key temporarily |
| Blob container `created: false` | Already exists | Proceed to upload |
| `Unable to initialize device PRN` | Python `print()` entered in CMD | Switch to Python `>>>` prompt |
| `IndentationError` / `SyntaxError` | Broken REPL paste | Use one-line statements or script |
| `...` prompt persists | Python waiting for block completion | Press Enter on blank line |
| `HTTP 301` on recovery | Likely HTTP-to-HTTPS redirect | Use HTTPS FQDN; inspect redirect headers if needed |
| Recovery succeeds but data disappears later | Ephemeral container storage | Use durable Qdrant-supported storage and restore backup |

---

**Session milestone:** Local S-Presso Qdrant collection successfully migrated to Azure Qdrant and verified: **2,412 / 2,412 points, green status, 1,536-dimensional cosine vectors**.
