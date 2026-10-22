
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

PROJECT_DIR = Path(__file__).resolve().parents[1]

print(PROJECT_DIR)

load_dotenv(PROJECT_DIR / ".env")

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError(
        "OPENAI_API_KEY is missing. "
        "Add it to your project .env file."
    )

qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6333")
)

COLLECTION = "spresso_manual_full"
EMBED_MODEL = "text-embedding-3-small"


def retrieve_documents(question: str, top_k: int = 10):
    if not question.strip():
        raise ValueError("Question cannot be empty")

    embedding_response = openai_client.embeddings.create(
        model=EMBED_MODEL,
        input=question
    )

    query_vector = embedding_response.data[0].embedding

    results = qdrant_client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        limit=top_k,
        with_payload=True
    ).points

    documents = []

    for point in results:
        payload = point.payload or {}

        documents.append({
            "page": payload.get("page_number"),
            "chunk_id": payload.get("chunk_id"),
            "text": payload.get("text", ""),
            "score": point.score
        })

    return documents

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

# ----------------------------------------
# Project configuration
# ----------------------------------------
PROJECT_DIR = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "http://localhost:6333"
)

COLLECTION = "spresso_manual_full"
EMBED_MODEL = "text-embedding-3-small"

# ----------------------------------------
# Validate API key
# ----------------------------------------
if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is missing. "
        "Add it to the .env file."
    )

# ----------------------------------------
# Initialize clients
# ----------------------------------------
openai_client = OpenAI(
    api_key=OPENAI_API_KEY,
    timeout=30.0
)

qdrant_client = QdrantClient(
    url=QDRANT_URL,
    timeout=30
)

# ----------------------------------------
# Retrieve documents
# ----------------------------------------
def retrieve_documents(
    question: str,
    top_k: int = 10
):
    if not question or not question.strip():
        raise ValueError(
            "Question cannot be empty"
        )

    if top_k < 1:
        raise ValueError(
            "top_k must be at least 1"
        )

    # Generate question embedding
    embedding_response = (
        openai_client.embeddings.create(
            model=EMBED_MODEL,
            input=question.strip()
        )
    )

    query_vector = (
        embedding_response.data[0].embedding
    )

    # Search Qdrant
    results = qdrant_client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        limit=top_k,
        with_payload=True
    ).points

    documents = []

    for point in results:
        payload = point.payload or {}

        documents.append({
            "page": payload.get("page_number"),
            "chunk_id": payload.get("chunk_id"),
            "text": payload.get("text", ""),
            "score": point.score
        })

    return documents
