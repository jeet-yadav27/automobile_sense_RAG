# S-Presso Enterprise RAG — Azure Deployment Runbook and Lessons Learned

**Project:** Maruti Suzuki S-Presso Owner's Manual RAG  
**Documentation date:** 12 November 2026  
**Status:** End-to-end deployed chatbot confirmed working by user  
**Scope:** Records steps and observations established during troubleshooting; clearly marks unverified design details and future work.

## 1. Objective and functionality

Deploy a React + FastAPI RAG application for answering questions from the S-Presso owner's manual with page citations, user authentication, persistent conversations, hybrid Qdrant retrieval, cross-encoder reranking, and an OpenAI LLM.

**Verified demonstration question:** “What is the warranty period for Maruti Suzuki S-Presso?”  
**Verified answer:** 36 months or 100,000 km, whichever occurs first, from the date of invoice to the first owner, subject to policy terms and exceptions. Source: owner's manual page 8.

## 2. Deployment inventory (as observed)

| Resource / component | Observed configuration | Verification |
|---|---|---|
| Azure resource group | `rg-automobile-rag-dev` | Used in successful CLI operations |
| Azure region | Central India | Reflected in Container Apps hostnames |
| Container Apps environment | `cae-automobile-rag-dev` | Earlier troubleshooting; current resource state not re-verified in latest tests |
| Azure Container Registry | `automobileragacr2026` | Image repository names previously used |
| FastAPI backend | Container App `warranty-rag-backend` | Revision restart succeeded; live chatbot now works |
| Backend revision during troubleshooting | `warranty-rag-backend--0000007` | Confirmed by Azure exec/logs |
| React frontend | Container App `warranty-rag-frontend` | Login and chat confirmed working |
| Frontend URL | `https://warranty-rag-frontend.bravecoast-33edf5ab.centralindia.azurecontainerapps.io` | Used for live testing |
| Backend ingress | Internal hostname observed: `warranty-rag-backend.internal.bravecoast-33edf5ab.centralindia.azurecontainerapps.io` | Internal hostname observed; exact frontend-to-backend routing/proxy implementation not fully documented |
| PostgreSQL | Persistent users, sessions, conversations, messages, idempotency | Alembic migrations succeeded; login worked |
| Redis | Used in application for rate limiting / concurrency controls | Earlier connectivity checks; full production behavior not load-tested |
| Qdrant | Existing `spresso_manual_full` plus new `spresso_hybrid_v1` | Hybrid retrieval returned 5 documents |
| OpenAI | Embeddings `text-embedding-3-small`; chat model `gpt-4.1-mini` in inspected code | Full local pipeline produced correct answer; hosted chat confirmed working |

**Important:** The exact hosting SKU and network topology for PostgreSQL, Redis, and Qdrant were not fully established in the captured steps. Do not claim these are Azure-managed services without checking the live deployment.

## 3. Deployment sequence — completed work

### Step 1 — Build the application locally

- Prepared the S-Presso manual corpus (363 pages in earlier project records).
- Extracted text and chunked documents; original collection contained **2,412 chunks**.
- Used OpenAI embeddings, Qdrant vector storage, and source metadata (`chunk_id`, `source_file`, `document_title`, `page_number`, `text`, `embedding_model`).
- Built the React/Vite frontend and FastAPI backend with authentication and persistent chat.
- Added query rewriting, hybrid retrieval, cross-encoder reranking, and grounded answer generation.

### Step 2 — Containerize and publish

- Built backend and frontend Docker images and pushed images to Azure Container Registry.
- Previously observed images included `automobileragacr2026.azurecr.io/warranty-rag-backend:v3` and `.../warranty-rag-frontend:v2`.
- Deployed frontend and backend as Azure Container Apps.
- The backend was accessible through internal Container Apps networking; the frontend had a public HTTPS URL.

> The exact original Docker build/push/deploy commands are not preserved in the current evidence; do not treat illustrative commands as a verified historical transcript.

### Step 3 — Configure application settings and secrets

- Backend environment variables included `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`, and `OPENAI_API_KEY`.
- Confirmed `OPENAI_API_KEY` referenced the Azure Container App secret `openai-api-key`, not an inline environment value.
- Corrected a secret that had effectively supplied the literal text `env:OPENAI_SECRET` to the OpenAI client.
- Saved the actual API key as the secret value **without quotes** or an `env:` prefix, then restarted the active backend revision.

Useful read-only configuration check:

```cmd
az containerapp show --name warranty-rag-backend --resource-group rg-automobile-rag-dev --query "properties.template.containers[0].env[?name=='OPENAI_API_KEY'].{Name:name,SecretRef:secretRef}" --output json
```

Restart command used:

```cmd
az containerapp revision restart --name warranty-rag-backend --resource-group rg-automobile-rag-dev --revision warranty-rag-backend--0000007
```

**Security:** Never print or commit actual secret values. Prefer Azure secret references and managed identity where supported.

### Step 4 — Apply PostgreSQL schema migrations

Initial registration failed with a server error because the `users` table did not exist. We confirmed Alembic migration files were in the backend image, then ran the migrations inside the backend container using a temporary, corrected Alembic configuration.

Migration history observed:

```text
-> 0ccec94b87a4    create users conversations messages
-> fb8380033a92    add authentication sessions
-> 4d1a13d8dfb3    add chat request idempotency
```

After migration, registration/login worked. **Production improvement:** run migrations in a controlled release job, not as an ad hoc operation inside a running application container.

### Step 5 — Diagnose OpenAI authentication failure

**Symptom:** React chat showed “Request failed. Reopen the conversation before retrying.” The backend logged an OpenAI HTTP 401 / `invalid_api_key` exception.

**Cause:** OpenAI received a placeholder-like secret value (`env:OPENAI_SECRET`) rather than a valid API key.

**Fix:** Correct the `openai-api-key` secret value, keep the `OPENAI_API_KEY` environment variable referencing that secret, and restart the backend revision. Subsequent logs progressed beyond OpenAI authentication into retrieval.

### Step 6 — Diagnose missing Qdrant collection

**Symptom:** Backend HTTP 500 during chat. Qdrant returned:

```text
Unexpected Response: 404 (Not Found)
Not found: Collection `spresso_hybrid_v1` doesn't exist!
```

Inspected `/app/services/hybrid_retrieval.py`, which explicitly uses:

```python
COLLECTION = "spresso_hybrid_v1"
# Named vectors: "dense" and "bm25"
# Retrieval: dense prefetch + sparse prefetch + Reciprocal Rank Fusion
```

The original `spresso_manual_full` collection held **2,412 points** and one **unnamed 1,536-dimensional cosine dense vector**; it had **no sparse vectors**. Therefore simply renaming the collection in code would have broken named-vector hybrid retrieval.

### Step 7 — Create the correct hybrid collection

Created `spresso_hybrid_v1` with:

- Named dense vector: `dense`, size 1536, cosine distance.
- Named sparse vector: `bm25`, with IDF modifier.

The original `spresso_manual_full` collection was preserved.

### Step 8 — Migrate 2,412 points without recomputing dense embeddings

- Scrolled original Qdrant points in batches of 50 with payload and vectors.
- Reused existing dense vectors.
- Generated sparse vectors from each chunk's `text` using FastEmbed `SparseTextEmbedding(model_name="Qdrant/bm25")` and `passage_embed`.
- Upserted each point into `spresso_hybrid_v1` with original point ID and payload, named `dense` and `bm25` vectors.
- Verified `Target collection points: 2412`.

This avoided a second OpenAI embedding run for all documents.

### Step 9 — Validate hybrid retrieval

Ran `hybrid_retrieve(question, top_k=5)` inside the Azure backend container.

Observed:

| Rank | Manual page | RRF score | Content |
|---|---:|---:|---|
| 1 | 8 | 0.7 | Warranty Policy |
| 2 | 10 | 0.6666667 | Warranty terms |
| 3 | 2 | 0.53333336 | Manual identification |
| 4 | 10 | 0.5 | Extent of Warranty |
| 5 | 8 | 0.4761905 | Special-component warranty |

These are **fusion scores**, not probabilities or model confidence percentages.

### Step 10 — Validate complete RAG execution

Confirmed function signature:

```python
generate_persistent_answer(question: str, previous_messages: list)
```

A local end-to-end call initially failed with Windows `WinError 10061` because local `QDRANT_URL` was `http://localhost:6333` and the service was not accepting connections. A subsequent local test succeeded after connectivity became available (the exact action restoring local Qdrant connectivity was not recorded).

Successful local call:

```cmd
python -c "from services.persistent_rag import generate_persistent_answer; result = generate_persistent_answer(question='What is the warranty period for Maruti Suzuki S-Presso?', previous_messages=[]); print(result)"
```

The response contained the correct 36-month / 100,000-km answer, a rewritten search query, and five sources including page 8. The user then confirmed the **deployed Azure frontend chatbot also worked**.

## 4. Troubleshooting register

| Issue | Evidence / symptom | Root cause | Fix / lesson |
|---|---|---|---|
| Container Apps environment provisioning/deletion state | Earlier `ScheduledForDelete` status | Environment lifecycle / provisioning complication | Verify provisioning state before deploying dependent apps; retain recovery runbook |
| Chat registration HTTP 500 | `relation "users" does not exist` | Database migrations not applied | Run Alembic migrations as release step |
| Alembic configuration issue | Temporary configuration lacked logging sections | Incomplete runtime Alembic config | Package and test a complete migration config in image |
| OpenAI HTTP 401 | `invalid_api_key`; literal placeholder in key | Incorrect Azure secret value | Correct secret, restart revision, validate without exposing key |
| Chat HTTP 500 after key fix | Qdrant collection 404 | Code expected `spresso_hybrid_v1` | Create matching hybrid collection and migrate points |
| Dense-only vs hybrid schema | Original collection lacked `bm25` | Index schema mismatched retrieval code | Schema validation before deployment; version collections |
| Local Qdrant refused connection | `WinError 10061` | Local `localhost:6333` unavailable at that moment | Check local Docker/endpoint; distinguish local from Azure tests |
| Azure CLI exec / quoting | Session disconnects and Python `unterminated string literal` | Interactive shell and Windows quoting issues | Prefer simple commands or local code inspection; verify execution context |
| Hugging Face symlink warning | Windows FastEmbed model download warning | Symlink caching not enabled | Nonblocking; optionally enable Developer Mode |
| Qdrant version warning | `Failed to obtain server version` | Version probe unsuccessful | Nonblocking for successful queries; inspect compatibility separately |
| Earlier GitHub push protection | Secrets detected in repository history | Sensitive tokens in Git history | Rotate affected secrets and use secret scanning/pre-commit controls |

## 5. Operational commands

**Windows CMD — backend status and logs:**

```cmd
az containerapp show --name warranty-rag-backend --resource-group rg-automobile-rag-dev --query "{name:name,provisioningState:properties.provisioningState}" -o json
az containerapp logs show --name warranty-rag-backend --resource-group rg-automobile-rag-dev --type console --tail 100
az containerapp exec --name warranty-rag-backend --resource-group rg-automobile-rag-dev --command /bin/sh
```

**Inside Linux container — read-only source inspection:**

```sh
cd /app
sed -n '1,130p' services/hybrid_retrieval.py
sed -n '1,100p' services/lcel_rag.py
```

**Qdrant collection verification (inside configured backend environment):**

```python
import os
from qdrant_client import QdrantClient
client = QdrantClient(url=os.environ["QDRANT_URL"])
for name in ("spresso_manual_full", "spresso_hybrid_v1"):
    info = client.get_collection(name)
    print(name, info.points_count, info.config.params.vectors, info.config.params.sparse_vectors)
```

## 6. Remaining work — recommended, NOT yet verified as complete

### P0 — Make the working deployment reproducible

1. **Persist the hybrid indexing procedure in the repository.** The live Qdrant collection is populated, but a fresh environment needs a repeatable migration/indexing job.
2. **Add startup/deployment validation:** required environment variables, Qdrant collection existence, dense dimension, named sparse vector, PostgreSQL migration revision, Redis connectivity, and OpenAI connectivity.
3. **Package Alembic configuration** and execute migrations in a dedicated CI/CD release step.
4. **Review secret handling:** Azure secrets/Key Vault, rotation, least privilege, no keys in Git history or logs.
5. **Document resource dependencies** and backup/restore of PostgreSQL and Qdrant.

### P1 — Enterprise deployment

6. **Terraform:** import existing resource group, ACR, Container Apps environment, apps, logging resources; inspect plan carefully before apply. Do not recreate working resources.
7. **CI/CD:** lint/test → image build → security scan → push to ACR → deploy revision → migration/index validation → smoke tests → rollback.
8. **Autoscaling:** configure min/max replicas and HTTP concurrency rules; test behavior and cost.
9. **Monitoring:** request rate, p50/p95 latency, HTTP 4xx/5xx, token usage, OpenAI errors, Qdrant retrieval latency, DB connections, Redis errors, ingestion failures; configure alerts.
10. **Security:** ingress review, TLS, RBAC, CSRF, rate limiting, network isolation, audit logs, prompt-injection defense, per-user document access filters where relevant.
11. **Performance/reliability:** load testing, timeouts, retry/backoff, circuit breakers, idempotency, resource limits, readiness probes.

### P2 — Document lifecycle / RAG quality

12. **New-document ingestion:** blob upload or approved repository event → extract/OCR → clean/chunk → hash/diff → dense + BM25 embeddings → upsert → validate → activate.
13. **Document versioning:** `document_id`, `version`, `effective_date`, `is_active`, `content_hash`, source/page metadata; ensure obsolete policies are not returned.
14. **Safe deletion:** remove or deactivate deleted/replaced chunks, using deterministic IDs and a manifest; never indiscriminately delete the live collection.
15. **RAG evaluation:** golden questions, retrieval recall@k, MRR, citation correctness, groundedness, answer quality, and regression tests after updates.
16. **Cost management:** Azure budgets, ACR/Container Apps resource sizing, token/embedding cost accounting, lifecycle policies, and alerting.

## 7. Interview-ready explanation

> I deployed an automotive owner's-manual RAG system using React, FastAPI, Azure Container Apps, PostgreSQL, Redis, Qdrant, and OpenAI. During deployment I resolved database migration errors, a misconfigured OpenAI secret, and a Qdrant schema mismatch. The retrieval code expected named dense and BM25 sparse vectors, but the existing 2,412-point collection was dense-only. I created a new hybrid collection, reused the existing 1,536-dimensional embeddings, generated BM25 sparse vectors, and migrated all 2,412 chunks. I validated RRF retrieval, cross-encoder reranking, LLM generation, source citations, and the hosted chatbot. My next steps are Terraform-managed infrastructure, CI/CD, monitoring, autoscaling, and versioned document ingestion.

## 8. Important caveats

- A successful local pipeline test is not proof of Azure networking; the **separate successful frontend chat test** is the end-to-end deployment confirmation.
- The original collection and the hybrid collection currently both exist. Do not delete the original without backup and rollback planning.
- Current chat success does not prove load capacity, disaster recovery, high availability, or automated document refresh.
- Avoid treating an example architecture as a statement of deployed infrastructure until verified against Azure resources.
