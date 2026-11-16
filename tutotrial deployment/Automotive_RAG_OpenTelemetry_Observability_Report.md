# Automotive RAG — OpenTelemetry Tracing & Observability Report

**Project:** Maruti Suzuki S-Presso Owner's Manual RAG  
**Environment:** Microsoft Azure Container Apps, Central India  
**Backend image:** `automobileragacr2026.azurecr.io/warranty-rag-backend:v7`  
**Backend revision:** `warranty-rag-backend--0000013`  
**Observation date:** 16 November 2026  
**Phase:** 8 — RAG Observability (custom span verification complete)

## 1. Executive summary

The S-Presso RAG application was instrumented with **OpenTelemetry** to measure the execution time and success/failure status of its major pipeline stages. Azure Monitor's OpenTelemetry integration exports telemetry to **Application Insights**, which can be queried through the associated **Log Analytics** workspace.

**Verified outcome:** Five custom spans were found in the `AppDependencies` table, with one successful recorded invocation per span and zero recorded failures. The new backend revision was healthy and the public API health check succeeded.

**Main finding:** CrossEncoder reranking took **14,388 ms (14.388 s)**, approximately **75.7%** of the estimated **19,004 ms** sequential pipeline time in this test. This is a candidate for performance investigation, not proof of a sustained bottleneck: the report contains only one measured request.

## 2. What the technologies do

- **OpenTelemetry (OTel):** A vendor-neutral framework for collecting traces, metrics and logs. In this implementation, the custom work focused on **traces**.
- **Trace:** A representation of work performed for a request, composed of **spans**.
- **Span:** A timed operation, such as query rewriting, retrieval or LLM answer generation. Spans may be nested to show parent/child operations.
- **Azure Monitor OpenTelemetry:** The Azure exporter and instrumentation integration used by the FastAPI service.
- **Application Insights:** Azure's application monitoring service receiving the telemetry.
- **Log Analytics:** The query interface used to inspect telemetry using Kusto Query Language (KQL).

**Terminology:** The correct name is **OpenTelemetry**, not “Open Telematics.”

## 3. Architecture and tracing flow

```text
User browser / React frontend
        |
        v
Azure Container Apps frontend (Nginx /api/ proxy)
        |
        v
FastAPI backend — v7
        |
        +-- POST /api/v1/chat (authenticated, CSRF/rate-limited)
              |
              v
         generate_persistent_answer()
              |
              +-- rag.query_rewrite
              |
              +-- rag.retrieve_and_rerank
              |     +-- rag.hybrid_retrieval
              |     |     +-- hybrid_retrieve() [Qdrant + retrieval work]
              |     +-- rag.crossencoder_reranking
              |           +-- rerank_documents()
              |
              +-- rag.answer_generation
                    +-- answer_chain.invoke() [OpenAI LLM]

OpenTelemetry SDK / Azure Monitor exporter
        |
        v
Azure Application Insights
        |
        v
Log Analytics: AppDependencies / AppRequests
```

The custom spans measure their **enclosing Python function calls**, not necessarily individual downstream network operations. For example, `rag.hybrid_retrieval` is not a Qdrant-only network latency measurement.

## 4. Azure resources verified

| Resource | Value |
|---|---|
| Resource group | `rg-automobile-rag-dev` |
| Azure Container Registry | `automobileragacr2026` |
| Backend Container App | `warranty-rag-backend` |
| Healthy backend revision | `warranty-rag-backend--0000013` |
| Backend image | `automobileragacr2026.azurecr.io/warranty-rag-backend:v7` |
| Application Insights | `warranty-rag-insights` |
| Log Analytics workspace ID | `e0a8f1ff-ed33-4e33-af26-4a4f9561d2fa` |
| Public API health endpoint | `https://warranty-rag-frontend.bravecoast-33edf5ab.centralindia.azurecontainerapps.io/api/v1/health` |

The Application Insights connection string is held in a Container Apps secret, referenced by the `APPLICATIONINSIGHTS_CONNECTION_STRING` environment variable. **Do not paste connection strings, credentials or API keys into logs or reports.**

## 5. Instrumentation implementation

### 5.1 FastAPI initialization (`api/main.py`)

The existing Azure Monitor setup runs early in startup, before the FastAPI import:

```python
import os
from azure.monitor.opentelemetry import configure_azure_monitor

connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if connection_string:
    configure_azure_monitor(
        connection_string=connection_string,
        enable_live_metrics=False,
    )

from fastapi import FastAPI
```

This enables the Azure Monitor OpenTelemetry integration. The deployed dependency versions reported for this project were `azure-monitor-opentelemetry==1.8.12` and `opentelemetry-instrumentation-fastapi==0.66b2`.

### 5.2 Persistent RAG spans (`services/persistent_rag.py`)

The code uses a tracer and adds spans around the existing operations:

```python
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("rag.query_rewrite"):
    search_question = rewrite_chain.invoke({
        "chat_history": history,
        "question": question,
    })

with tracer.start_as_current_span("rag.retrieve_and_rerank") as span:
    documents = retrieve_and_rerank(search_question)
    span.set_attribute("rag.retrieved_documents", len(documents))

context = format_context(documents)

with tracer.start_as_current_span("rag.answer_generation"):
    answer = answer_chain.invoke({
        "question": question,
        "context": context,
    })
```

This snippet documents the added instrumentation; the complete function also builds conversation history and returns answers and source citations.

### 5.3 Retrieval and reranking spans (`services/lcel_rag.py`)

```python
from opentelemetry import trace
tracer = trace.get_tracer(__name__)


def retrieve_and_rerank(question: str):
    with tracer.start_as_current_span("rag.hybrid_retrieval") as span:
        candidates = hybrid_retrieve(question=question, top_k=10)
        span.set_attribute("rag.retrieval.candidate_count", len(candidates))

    with tracer.start_as_current_span("rag.crossencoder_reranking") as span:
        documents = rerank_documents(
            question=question,
            documents=candidates,
            top_k=5,
        )
        span.set_attribute("rag.reranking.document_count", len(documents))

    return documents
```

The tracing additions do not change the configured retrieval and reranking limits: **top 10 candidates**, then **top 5 reranked documents**.

## 6. Validation and deployment record

1. **Syntax check passed** with no output:

   ```powershell
   python -m py_compile `
     .\services\persistent_rag.py `
     .\services\lcel_rag.py
   ```

2. **Local pipeline test passed** after resolving an earlier Qdrant connection refusal. The persistent RAG function returned the correct standard S-Presso warranty: **36 months or 100,000 km, whichever occurs first**, citing page 8 and page 10 chunks. The test confirms pipeline functionality, not Azure telemetry export.

3. **Docker v7 built successfully:**

   ```powershell
   docker build -f Dockerfile.api -t automobileragacr2026.azurecr.io/warranty-rag-backend:v7 .
   ```

4. **Docker v7 pushed to Azure Container Registry:**

   ```powershell
   az acr login --name automobileragacr2026
   docker push automobileragacr2026.azurecr.io/warranty-rag-backend:v7
   ```

   Reported digest: `sha256:63c398bb51494470a47ef62aa35bbd163f2e524e1fb40eb511837008aafc7366`.

5. **Azure Container App updated:**

   ```powershell
   az containerapp update `
     --name warranty-rag-backend `
     --resource-group rg-automobile-rag-dev `
     --image automobileragacr2026.azurecr.io/warranty-rag-backend:v7 `
     --output table
   ```

6. **Revision health verified:** `warranty-rag-backend--0000013` showed `Active=true`, `Health=Healthy`, `Running=Running`, `Replicas=1`.

7. **Public health check passed** using:

   ```powershell
   Invoke-RestMethod `
     -Uri "https://warranty-rag-frontend.bravecoast-33edf5ab.centralindia.azurecontainerapps.io/api/v1/health" `
     -Method GET
   ```

8. **Custom traces verified** in Azure Log Analytics after a deployed chat request. The generation span appeared in a subsequent query; it was not absent from the final telemetry results.

## 7. Actual Azure Application Insights results

**Source:** User-provided output of a Log Analytics `AppDependencies` query, 16 November 2026. All five custom operations had **one recorded call** and **zero recorded failures**.

| Span (`Name`) | Calls | Duration (ms) | Duration (s) | Failures |
|---|---:|---:|---:|---:|
| `rag.query_rewrite` | 1 | 1,748 | 1.748 | 0 |
| `rag.hybrid_retrieval` | 1 | 894 | 0.894 | 0 |
| `rag.crossencoder_reranking` | 1 | 14,388 | 14.388 | 0 |
| `rag.retrieve_and_rerank` | 1 | 15,282 | 15.282 | 0 |
| `rag.answer_generation` | 1 | 1,974 | 1.974 | 0 |

**Estimated sequential pipeline time** = query rewrite + retrieval/reranking + answer generation  
= `1,748 + 15,282 + 1,974 = 19,004 ms` = **19.004 seconds**.

**Important: avoid double-counting.** `rag.retrieve_and_rerank` already contains the hybrid retrieval and CrossEncoder operations. Do **not** add all five row durations together.

**Breakdown of estimated pipeline time:**

| Stage | Duration | Approx. share |
|---|---:|---:|
| Query rewrite | 1.748 s | 9.2% |
| Hybrid retrieval | 0.894 s | 4.7% |
| CrossEncoder reranking | 14.388 s | 75.7% |
| LLM answer generation | 1.974 s | 10.4% |

The measured `rag.retrieve_and_rerank` span equals `894 + 14,388 = 15,282 ms` in the displayed data.

**Limitations:**
- Only **one** recorded invocation per span; reported average and P95 are both that single value and are not meaningful production baselines.
- The **19.004 s** value is a sum of observed sequential spans, **not** a separately measured HTTP request latency. It excludes potential surrounding API, database, network, or UI overhead.
- The observed **14.388 s** reranking time may reflect model initialization or cold-start overhead. Further measurements are required.
- **LLM token usage** and cost were **not** measured by these custom spans.
- The current data does not by itself prove that all traces are preserved under production sampling.

## 8. Reusable Azure Log Analytics commands

### 8.1 Summarize custom RAG spans

```powershell
az monitor log-analytics query `
  --workspace e0a8f1ff-ed33-4e33-af26-4a4f9561d2fa `
  --analytics-query "AppDependencies | where TimeGenerated > ago(1h) | where Name contains 'rag.' | summarize Calls=count(), AvgLatencyMs=round(avg(DurationMs),2), P95LatencyMs=round(percentile(DurationMs,95),2), Failures=countif(Success==false) by Name | order by Name asc" `
  --output table
```

### 8.2 Inspect individual span records

```powershell
az monitor log-analytics query `
  --workspace e0a8f1ff-ed33-4e33-af26-4a4f9561d2fa `
  --analytics-query "AppDependencies | where TimeGenerated > ago(2h) | where Name contains 'rag.' or Name contains 'openai' | project TimeGenerated, Name, DurationMs, Success | order by TimeGenerated desc" `
  --output table
```

### 8.3 Monitor HTTP API requests

```powershell
az monitor log-analytics query `
  --workspace e0a8f1ff-ed33-4e33-af26-4a4f9561d2fa `
  --analytics-query "AppRequests | where TimeGenerated > ago(2h) | summarize Requests=count(), AvgLatencyMs=round(avg(DurationMs),2), P95LatencyMs=round(percentile(DurationMs,95),2), Failures=countif(Success==false) by Name" `
  --output table
```

**Query note:** In this environment, querying `AppDependencies` and `AppRequests` through **Log Analytics** worked. Earlier attempts through `az monitor app-insights query` were not successful.

## 9. What was verified vs. what remains

| Capability | Status | Evidence / next action |
|---|---|---|
| Backend v7 deployment | **Verified** | Revision 0000013 healthy and running |
| Public API health | **Verified** | `/api/v1/health` returned expected response |
| Query rewriting span | **Verified** | `rag.query_rewrite` in `AppDependencies` |
| Hybrid retrieval span | **Verified** | `rag.hybrid_retrieval` in `AppDependencies` |
| CrossEncoder span | **Verified** | `rag.crossencoder_reranking` in `AppDependencies` |
| Combined retrieval/rerank span | **Verified** | `rag.retrieve_and_rerank` in `AppDependencies` |
| LLM generation span | **Verified** | `rag.answer_generation` in `AppDependencies` |
| Error counts for sampled test | **Verified** | Zero failures for these five recorded spans |
| Dedicated Qdrant network-call timing | **Not yet isolated** | Instrument `qdrant.query_points()` separately if needed |
| LLM token usage and cost | **Not yet instrumented** | Capture safe usage metadata; avoid prompt content |
| Representative latency / P95 | **Not yet established** | Collect repeated warm and cold requests |
| Production error scenarios | **Not yet tested** | Validate timeout and dependency-failure tracing |
| Phase 9 security and persistence | **Next phase** | Verify auth, database, Redis and Qdrant persistence |

## 10. Recommended next steps

1. **Collect a baseline:** Run multiple authorized chat requests after the model is warm. Compare median, P95, and failures rather than relying on a single call.
2. **Investigate CrossEncoder latency:** Determine whether the 14.388 s duration is due to cold model loading, CPU contention, batching, or reranking itself. Avoid changing model architecture before gathering evidence.
3. **Add token metrics:** Record input/output token counts and estimated cost where available, without logging private user questions or document content.
4. **Improve trace coverage:** Confirm parent-child span relationships for the FastAPI request and thread-based chat execution. Correlate request traces with database and Qdrant dependencies.
5. **Proceed to Phase 9:** Verify authentication, CSRF, rate limits, PostgreSQL conversation persistence, Redis behavior and Qdrant storage after deployment.

## 11. Interview-ready explanation

> In our Azure-hosted S-Presso RAG application, we integrated OpenTelemetry with FastAPI using Azure Monitor. We created custom spans for query rewriting, hybrid retrieval, CrossEncoder reranking and LLM generation. After deploying Docker v7 to Azure Container Apps, we verified the traces in the Application Insights Log Analytics `AppDependencies` table. In one observed request, query rewriting took 1.75 seconds, hybrid retrieval 0.89 seconds, reranking 14.39 seconds and LLM generation 1.97 seconds. The sequential stages totaled approximately 19 seconds. All five spans reported success. The results identified reranking as the first area to investigate for latency optimization, while additional requests are needed for a reliable P95 baseline.

---

*Prepared from the project code excerpts, deployment commands, revision-health checks, local tests, and Azure Log Analytics results shared in this conversation. No secrets are included.*
