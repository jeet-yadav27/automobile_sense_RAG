# Automotive RAG — Phase 9 Security & Persistence Verification

**Project:** Maruti Suzuki S-Presso Owner's Manual RAG  
**Environment:** Microsoft Azure Container Apps, Central India  
**Verification date:** 16 November 2026  
**Backend revision tested:** `warranty-rag-backend--0000015` (Docker v8)  
**Status:** Planned Phase 9 functional/security checks completed; further production hardening recommended.

> **Security hygiene:** A session cookie value was accidentally included in an earlier diagnostic output. The user was instructed to log out and log back in, creating a new session. Never include actual cookies, passwords, CSRF tokens, connection strings, or API keys in reports, tickets, or screenshots.

## 1. Executive summary
gin and an Azure backend revision restart. The backend health endpoint recovered successfully after restart. PostgreSQL conversation history remained accessible, and Qdrant reported a healthy collection with **2,412 points** after restart.

These are **targeted verification tests**, not a full penetration test or guarantee of comprehensive security.

### Results matrix

| Area | Test | Observed result | Assessment |
|---|---|---|---|
We tested the deployed Automotive RAG application's session-cookie configuration, rejection of unauthenticated requests, rejection of missing/invalid CSRF tokens, access control between two users, and persistence across logout/lo
| Authentication | Unauthenticated `POST /api/v1/chat` with allowed `Origin` | HTTP `401`, `Not authenticated` | Passed |
| Request origin | Request without expected `Origin` | HTTP `403`, `Untrusted request origin` | Observed; origin checks are defense-in-depth, not authentication |
| Cookie attributes | Fresh `warranty_session` after Docker v8 login | `Secure` checked, `HttpOnly` checked, `SameSite=Lax` | Passed |
| CSRF — missing | Logged-in browser `POST /api/v1/chat` without `X-CSRF-Token` | HTTP `403` | Status confirmed; response body not captured |
| CSRF — invalid | Logged-in browser `POST /api/v1/chat` with bogus `X-CSRF-Token` | HTTP `403` | Status confirmed; response body not captured |
| User isolation | User A attempts to read User B's messages | HTTP `404`, `{"detail":"Conversation not found"}` | Passed for tested read endpoint |
| Session persistence | User B logs out, logs in, reopens saved conversation | Conversation and messages still visible | Passed |
| Backend restart | Restart Azure Container Apps revision | Restart succeeded | Passed |
| Health after restart | `GET /api/v1/health` via frontend proxy | `status=ok`, `service=spresso-rag-api` | Passed |
| PostgreSQL after restart | User B refreshes and reopens saved messages | Conversation and messages still visible | Passed |
| Qdrant after restart | Inspect collection status and points | `spresso_hybrid_v1`, `green`, `2412` | Passed |
| Redis | `PING` from backend (before restart) | `True` | Passed before restart; post-restart check not repeated |

## 2. Architecture and why these checks matter

```text
Browser (React/Vite)
  |
  | HTTPS, session cookie, X-CSRF-Token for protected mutations
  v
Azure Container Apps — public frontend (Nginx reverse proxy)
  |
  | /api/v1/* forwarded internally
  v
Azure Container Apps — internal FastAPI backend
  |-- Authentication / authorization / CSRF
  |-- RAG retrieval and generation
  |-- PostgreSQL: users, sessions, conversations, messages
  |-- Qdrant: document embeddings and payloads
  `-- Redis: rate limiting / coordination
```

The frontend is exposed over HTTPS, while backend ingress was previously verified as internal (`external=false`, port 8000). The frontend URL used for testing was:

`https://warranty-rag-frontend.bravecoast-33edf5ab.centralindia.azurecontainerapps.io`

**Why persistence matters:** A Container Apps replica is replaceable/ephemeral. Durable application state must live in appropriate persistent stores, not solely in a container's writable filesystem. The successful restart checks demonstrate continued access to existing PostgreSQL and Qdrant data, but do not independently prove backup/restore capability or multi-zone disaster recovery.

## 3. CSRF explained clearly

**CSRF** stands for **Cross-Site Request Forgery**. It occurs when an attacker-controlled site tricks a user's browser into sending an unwanted request to a site where the user is already authenticated. Browsers can automatically attach cookies to eligible requests; if the server relies only on the cookie, it may mistake the forged request for an intentional user action.

### Example attack

1. A user logs in to the RAG application; the browser stores `warranty_session`.
2. While still logged in, the user visits an attacker-controlled website.
3. The attacker tries to trigger a state-changing request against the RAG application.
4. If the browser sends the session cookie and the backend does not verify request intent, the operation might succeed without the user's authorization.

**CSRF tokens** help by requiring a secret, unpredictable token that the legitimate frontend can send in a custom header such as `X-CSRF-Token`. The server validates it against the authenticated session. A cross-origin attacker generally cannot read the legitimate app's token because of the same-origin policy, and cannot freely send custom headers without CORS authorization. **SameSite=Lax** cookies and origin validation add defense-in-depth, but do not replace a correct CSRF design where CSRF is relevant.

**CSRF vs authentication vs authorization:**

| Control | Question it answers |
|---|---|
| Authentication | Who is making this request? |
| Authorization | May this user access this resource? |
| CSRF protection | Was this cookie-authenticated, state-changing request intentionally issued by the legitimate application? |
| HTTPS | Is traffic protected in transit? |
| HttpOnly | Is JavaScript prevented from directly reading the session cookie? |
| Secure | Is the cookie restricted to secure transport? |
| SameSite=Lax | Are cookies restricted on many cross-site requests? |

`HttpOnly` does **not** prevent the browser from attaching a cookie to a request. `SameSite=Lax` is useful but not a complete substitute for server-side CSRF verification.

## 4. Important FastAPI security code (from the tested project)

The following are representative excerpts of the actual project implementation discussed and inspected during this phase. They omit surrounding imports, validation and database error-handling code for clarity.

### 4.1 Login sets a secure, HttpOnly session cookie

**File:** `api/routes/auth.py`

```python
import os

response.set_cookie(
    key="warranty_session",
    value=token,
    httponly=True,
    secure=os.getenv("APP_ENV", "development").lower() == "production",
    samesite="lax",
    max_age=7 * 24 * 60 * 60,
    path="/",
)
```

- `httponly=True`: frontend JavaScript cannot directly read the session cookie.
- `secure=True` in production: cookie is sent only over HTTPS (subject to browser semantics).
- `samesite="lax"`: restricts many cross-site cookie sends.
- `max_age`: seven-day cookie lifetime; server-side session expiry must also be enforced.
- `path="/"`: cookie applies across the frontend's URL paths.

**Production environment setting:**

```powershell
az containerapp update `
  --name warranty-rag-backend `
  --resource-group rg-automobile-rag-dev `
  --set-env-vars APP_ENV=production
```

Inside the container, verification returned `APP_ENV: production`. The deployed `auth.py` was also inspected and matched the intended `secure=` expression. The first browser check showed Secure unchecked, but after logout, clearing the old cookie and logging in again, **Secure was checked**. This was consistent with an old cookie having been retained; the exact earlier cause was not independently established.

### 4.2 Authenticate a session cookie

**File:** `api/dependencies.py`

```python
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_auth_session(
    warranty_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> AuthSession:
    if not warranty_session:
        raise HTTPException(401, "Not authenticated")

    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_token(warranty_session)
        )
    )
    if session is None:
        raise HTTPException(401, "Invalid session")
    if session.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(401, "Session expired")
    return session
```

The application stores a **hash of the session token** in PostgreSQL, rather than using the raw browser cookie as the database lookup value. Session expiry and existence are checked server-side.

### 4.3 Authorize the current user

```python
def get_current_user(
    session: AuthSession = Depends(get_auth_session),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, "User not found")
    return user
```

A valid login alone is not enough to access arbitrary conversations: the conversation lookup must also constrain the resource to `current_user.id`.

### 4.4 Validate the CSRF header

```python
import hmac
from fastapi import Header, Depends, HTTPException


def verify_csrf(
    x_csrf_token: str | None = Header(default=None),
    session: AuthSession = Depends(get_auth_session),
) -> None:
    if not x_csrf_token:
        raise HTTPException(403, "CSRF token missing")

    if not hmac.compare_digest(
        hash_token(x_csrf_token),
        session.csrf_token_hash,
    ):
        raise HTTPException(403, "Invalid CSRF token")
```

FastAPI maps `x_csrf_token` to the `X-CSRF-Token` HTTP header. `hmac.compare_digest` helps avoid ordinary timing differences in token comparison. In this project, the CSRF token hash is stored on the authenticated session.

### 4.5 Login, CSRF retrieval, logout

**File:** `api/routes/auth.py`:

- `POST /api/v1/auth/register` — create account.
- `POST /api/v1/auth/login` — validate credentials, create a session and CSRF token, set cookie.
- `GET /api/v1/auth/me` — return authenticated user.
- `GET /api/v1/auth/csrf` — generate/rotate a CSRF token for the current session.
- `POST /api/v1/auth/logout` — validate session and CSRF token, delete session and clear cookie.

**Important:** Calling `/auth/csrf` may rotate the token and invalidate the token held by the current UI. We intentionally did **not** call it during negative CSRF tests.

### 4.6 Conversation ownership check — security pattern

The actual deployed endpoint was identified as:

`GET /api/v1/conversations/{conversation_id}/messages`

The following is an **illustrative authorization pattern**, not a verbatim copy of `api/routes/chat.py`:

```python
from fastapi import Depends, HTTPException
from sqlalchemy import select


def get_owned_conversation(db, conversation_id, current_user):
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation
```

Returning `404` for another user's conversation avoids confirming whether a guessed ID exists. The actual browser test returned `404` with `Conversation not found` for User A requesting User B's messages.

## 5. Microsoft Edge DevTools — full test procedure

### 5.1 Find session cookies and security attributes

1. Open the deployed frontend in Microsoft Edge.
2. Press **F12**.
3. Choose **Application** (sometimes under `>>`).
4. Navigate to **Storage → Cookies → frontend domain**.
5. Find the row `warranty_session`.
6. Inspect the **Secure**, **HttpOnly**, and **SameSite** columns.
7. **Never copy the Value column** into chat, email, tickets, or screenshots.

Expected: **Secure checked**, **HttpOnly checked**, **SameSite = Lax**.

If an old cookie is present: log out, delete the remaining `warranty_session` cookie if necessary, log in again, and re-check. A production setting change cannot retroactively rewrite an already-issued cookie.

### 5.2 Inspect the `Set-Cookie` login response

1. Open **F12 → Network**.
2. Enable **Fetch/XHR** and optionally **Preserve log**.
3. Log out, then log back in.
4. Select the `login` network request (usually `POST /api/v1/auth/login`).
5. Open **Headers → Response Headers**.
6. Look for the **attribute names only** on `Set-Cookie`: `Secure`, `HttpOnly`, `SameSite=Lax`.

**Common confusion:** `GET /api/v1/auth/me` shows a **request** `Cookie` header, not the **response** `Set-Cookie` attributes that were set at login. In the test, `/auth/me` returned HTTP `200`, showing the session was recognized, but that alone did not verify the cookie flags.

### 5.3 Test a missing CSRF token (authenticated browser)

Open **User A's browser → F12 → Console** while logged in:

```javascript
fetch("/api/v1/chat", {
  method: "POST",
  credentials: "include",
  headers: {
    "Content-Type": "application/json",
    "Idempotency-Key": "csrf-negative-test-001"
  },
  body: JSON.stringify({
    question: "What is the S-Presso warranty?"
  })
}).then(async response => {
  console.log("HTTP Status:", response.status);
  console.log("Response:", await response.text());
});
```

**Observed:** HTTP `403 Forbidden`. The full response body was not captured in the user's result; the expected implementation detail is `CSRF token missing`. The browser console may display `Promise {<pending>}` before the asynchronous request finishes; this is normal.

### 5.4 Test an invalid CSRF token

```javascript
fetch("/api/v1/chat", {
  method: "POST",
  credentials: "include",
  headers: {
    "Content-Type": "application/json",
    "X-CSRF-Token": "invalid-test-token",
    "Idempotency-Key": "csrf-invalid-test-002"
  },
  body: JSON.stringify({
    question: "What is the S-Presso warranty?"
  })
}).then(async response => {
  console.log("HTTP Status:", response.status);
  console.log("Response:", await response.text());
});
```

**Observed:** HTTP `403`. The expected body is `Invalid CSRF token`, but the user reported only the status code. For stricter verification, inspect the response body in DevTools → Network → request → Response.

### 5.5 Test unauthenticated chat access (PowerShell)

The earlier test used a request with a permitted `Origin` but no session cookie:

```powershell
$base = "https://warranty-rag-frontend.bravecoast-33edf5ab.centralindia.azurecontainerapps.io"
try {
  Invoke-RestMethod `
    -Uri "$base/api/v1/chat" `
    -Method POST `
    -ContentType "application/json" `
    -Headers @{
      "Origin" = $base
      "Idempotency-Key" = "security-test-123456789"
    } `
    -Body '{"question":"What is the S-Presso warranty?"}' `
    -ErrorAction Stop
} catch {
  Write-Host "HTTP Status:" ([int]$_.Exception.Response.StatusCode)
  Write-Host "Response:" $_.ErrorDetails.Message
}
```

**Observed:** HTTP `401`, `{"detail":"Not authenticated"}`. Without the expected `Origin`, an earlier attempt returned HTTP `403`, `Untrusted request origin`. **Origin is not proof of identity**; a non-browser client can set it arbitrarily.

### 5.6 Test cross-user isolation using two separate browser sessions

**Preparation**

1. Open User A in a normal Edge window.
2. Open User B in an **InPrivate** window (`Ctrl+Shift+N`).
3. Register/log in as a distinct User B.
4. Create a new conversation under User B and confirm it appears in User B's history.

**User B: list conversations**

```javascript
fetch("/api/v1/conversations", {
  credentials: "include"
}).then(r => r.json())
  .then(data => console.log(data));
```

The test conversation ID was:

`3b6da878-a296-4c46-9d35-d8e3302d3640`

A conversation ID is not an authentication credential, but avoid unnecessary disclosure of production resource identifiers.

**User A: attempt to read User B's messages**

```javascript
fetch(
  "/api/v1/conversations/3b6da878-a296-4c46-9d35-d8e3302d3640/messages",
  { method: "GET", credentials: "include" }
).then(async response => {
  console.log("HTTP Status:", response.status);
  console.log("Response:", await response.text());
});
```

**Observed:**

```text
HTTP Status: 404
Response: {"detail":"Conversation not found"}
```

This confirms that **the tested User A session could not read User B's messages through that endpoint**. It does not automatically verify every write/delete endpoint or every authorization boundary.

### 5.7 Troubleshooting `405 Method Not Allowed`

The initial request to:

`GET /api/v1/conversations/{conversation_id}`

returned `405`. This means the HTTP method is unsupported at that route; it is **not** proof of an authorization denial. The supported read endpoint was discovered by searching the local route source:

```powershell
Get-ChildItem .\api\routes\ -Filter *.py |
  Select-String -Pattern 'conversations|messages|@router.get|@router.post' |
  Select-Object Path, LineNumber, Line
```

Source showed:

```python
@router.get("/conversations")
@router.get("/conversations/{conversation_id}/messages")
```

The frontend's `/openapi.json` returned a **String** with no OpenAPI version or paths, likely due to frontend Nginx routing/fallback; this URL was not useful for API discovery. Prefer checking actual route definitions or obtaining the backend OpenAPI document through an explicitly configured, protected route.

## 6. Azure CLI — persistence and restart procedure

### 6.1 Verify backend replica

```powershell
az containerapp replica list `
  --name warranty-rag-backend `
  --resource-group rg-automobile-rag-dev `
  --revision warranty-rag-backend--0000015 `
  --query "[].{Replica:name,RunningState:properties.runningState}" `
  --output table
```

**Observed before restart:** one running replica, named `warranty-rag-backend--0000015-6766976dc5-99kf5`.

### 6.2 Restart the revision

The attempted command `az containerapp replica restart` was **not recognized** by the installed CLI extension. The successful command was:

```powershell
az containerapp revision restart `
  --name warranty-rag-backend `
  --resource-group rg-automobile-rag-dev `
  --revision warranty-rag-backend--0000015
```

**Observed:** restart succeeded. Because only one replica was running, a brief service interruption was possible. Do not perform disruptive restart tests during live traffic without an approved maintenance plan.

### 6.3 Verify health after restart

```powershell
$base = "https://warranty-rag-frontend.bravecoast-33edf5ab.centralindia.azurecontainerapps.io"
Invoke-RestMethod "$base/api/v1/health"
```

**Observed:**

```text
status  service
------  -------
ok      spresso-rag-api
```

### 6.4 Verify PostgreSQL conversation persistence

In User B's InPrivate window, refresh the frontend, log in if necessary, and reopen the previously saved conversation. **Observed:** the conversation and both question/answer messages remained visible after restart.

An additional database-level read-only check used earlier in Phase 9 was:

```bash
python -c 'from sqlalchemy import text; from db.database import engine; conn = engine.connect(); print("PostgreSQL:", conn.execute(text("SELECT 1")).scalar()); conn.close()'
```

Earlier result: `PostgreSQL: 1`; the application also exposed tables `alembic_version`, `auth_sessions`, `chat_request_records`, `conversations`, `messages`, `users`.

### 6.5 Verify Qdrant collection persistence

Connect to the backend container from Windows PowerShell:

```powershell
az containerapp exec `
  --name warranty-rag-backend `
  --resource-group rg-automobile-rag-dev `
  --command /bin/sh
```

At the Linux `#` prompt, run:

```bash
python -c 'from services.hybrid_retrieval import qdrant, COLLECTION; info = qdrant.get_collection(COLLECTION); print("Collection:", COLLECTION); print("Status:", info.status); print("Stored points:", info.points_count)'
```

**Observed after restart:**

```text
Collection: spresso_hybrid_v1
Status: green
Stored points: 2412
```

### 6.6 Redis check (performed before restart)

```bash
python -c 'import os, redis; r = redis.Redis.from_url(os.environ["REDIS_URL"], socket_connect_timeout=5, socket_timeout=5); print("Redis PING:", r.ping())'
```

**Earlier observed:** `Redis PING: True`. A post-restart Redis PING was not separately reported. Avoid printing `REDIS_URL` itself because it may contain credentials.

## 7. Troubleshooting lessons from the actual test

| Symptom | Meaning | Resolution |
|---|---|---|
| `APP_ENV:: not found` at Linux `#` | Expected output was pasted as a shell command | Run the actual `python -c ...` check instead |
| Secure unchecked in browser | Existing cookie may have been issued before updated settings | Log out, clear old cookie, log in again; inspect fresh cookie |
| `/auth/me` returns `200` | Session is valid | Use Application → Cookies or login `Set-Cookie` to verify flags |
| `Promise {<pending>}` in Console | Asynchronous fetch has not yet resolved | Wait for printed status/response |
| `403` on missing/invalid CSRF | Request rejected | Inspect response body to confirm the specific reason |
| `405` on `GET /conversations/{id}` | Unsupported method/route | Use `GET /conversations/{id}/messages` |
| `/openapi.json` returns `String` | Frontend proxy may be returning HTML | Inspect local FastAPI route source or configured backend OpenAPI |
| Interactive container session disconnects | Shell/exec session ended | Use local source inspection or reconnect; don't assume backend failed |
| `az containerapp replica restart` unrecognized | CLI does not support that subcommand in installed extension | Use supported `az containerapp revision restart` |

## 8. Interview-ready answers

**Q: What is CSRF and how did you prevent it in your FastAPI RAG application?**  
A: CSRF is when an attacker causes a browser with an existing authenticated cookie to issue an unintended request. We use a server-side session, an unpredictable CSRF token whose hash is stored with the session, and a required `X-CSRF-Token` header on protected mutations. The backend checks the header using `hmac.compare_digest`. We also use Secure, HttpOnly, SameSite=Lax cookies and origin validation as defense-in-depth. We verified that authenticated requests with missing and invalid CSRF headers returned HTTP 403.

**Q: What is the difference between authentication and authorization?**  
A: Authentication verifies the caller's identity, for example by validating the `warranty_session` cookie. Authorization ensures that authenticated User A can only access resources owned by User A. We tested this by requesting User B's message history from User A's browser; the API returned HTTP 404, `Conversation not found`.

**Q: How did you verify data persistence on Azure Container Apps?**  
A: We created a chat conversation, verified it survived logout/login, restarted the running Azure Container Apps revision, checked that `/api/v1/health` returned `ok`, reopened the same conversation, and queried Qdrant. PostgreSQL messages remained accessible and Qdrant reported 2,412 points in a green collection.

**Q: Why use HttpOnly, Secure, and SameSite?**  
A: HttpOnly limits JavaScript access to the session cookie; Secure restricts it to HTTPS; SameSite reduces the chance the cookie is sent on cross-site requests. They are complementary and do not replace server-side authentication, authorization, or CSRF controls.

**Q: Why return 404 instead of 403 for someone else's conversation?**  
A: A 404 can avoid revealing whether the resource exists. The key is to enforce ownership in the database query or equivalent authorization logic, not merely hide the UI link.

**Q: Does a successful restart prove production readiness?**  
A: No. It verifies a useful failure-recovery/persistence scenario. Production readiness also needs backup and restore drills, scaling tests, alerts, secret rotation, broader authorization tests, and deployment rollback validation.

## 9. Recommended next security and reliability tests

1. **Inspect CSRF response bodies** for missing and invalid tokens, not just HTTP 403.
2. **Verify authorization on all conversation operations**, including updates, deletes, streaming endpoints, and any exports. Confirm User A cannot mutate User B's data.
3. **Re-test Redis after restart** and verify rate-limit behavior; consider distributed throttling under concurrent replicas.
4. **Validate session expiration, logout invalidation, and cookie clearing** (including cross-tab behavior).
5. **Verify `Origin`/CORS behavior** with allowed and disallowed browser origins; do not rely on origin headers as authentication.
6. **Test backups and restoration** of PostgreSQL and Qdrant, rather than only application restart.
7. **Review secrets, logging, and telemetry** to ensure session tokens, CSRF tokens, prompts with sensitive data, and connection strings are not recorded.
8. **Load-test autoscaling**, latency, rate limits, and recovery at more than one replica.
9. **Check dependency and container image vulnerabilities**, TLS settings, and Azure network access restrictions.
10. **Document rollback procedures** before Phase 10 CI/CD and Phase 11 Terraform work.

## 10. Final Phase 9 conclusion

**Completed planned verification:** secure cookie attributes after a fresh login, unauthenticated request rejection, CSRF negative tests (status codes), cross-user message read isolation, session persistence, backend revision restart and health recovery, PostgreSQL conversation persistence, and Qdrant collection persistence (2,412 points, green).

**Next project phase:** Phase 10 — CI/CD automation (build, test, scan, publish image to ACR, deploy Azure Container Apps, smoke test, and rollback strategy).
