
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.chat import router as chat_router
from api.routes.health import router as health_router

from api.routes.auth import router as auth_router

from api.origin import validate_origin




app = FastAPI(
    title="S-Presso Warranty RAG API",
    description=(
        "Conversational RAG using LangChain LCEL, "
        "Qdrant hybrid search, BM25 and CrossEncoder"
    ),
    version="1.0.0"
)

app.middleware("http")(validate_origin)


# Local React development origins.
# Restrict these further before production.

# Step 2: Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    # allow_headers=["Content-Type", "X-CSRF-Token"],
    allow_headers=[
    "Content-Type",
    "X-CSRF-Token",
    "Idempotency-Key",
],
)



app.include_router(
    health_router,
    prefix="/api/v1",
    tags=["Health"]
)

app.include_router(
    chat_router,
    prefix="/api/v1",
    tags=["Chat"]
)


@app.get("/")
def root():
    return {
        "message": "S-Presso RAG API",
        "docs": "/docs"
    }


app.include_router(
    auth_router,
    prefix="/api/v1/auth",
    tags=["Authentication"],
)