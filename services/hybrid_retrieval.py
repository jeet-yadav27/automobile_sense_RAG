
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient, models
from fastembed import SparseTextEmbedding

PROJECT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_DIR / ".env")

openai_client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)

qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6333")
)

sparse_model = SparseTextEmbedding(
    model_name="Qdrant/bm25"
)

COLLECTION = "spresso_hybrid_v1"


def hybrid_retrieve(question: str, top_k: int = 10):
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    if top_k < 1:
        raise ValueError("top_k must be positive")

    # Dense embedding
    dense_response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=question
    )

    dense_vector = dense_response.data[0].embedding

    # Sparse BM25 embedding
    sparse = next(sparse_model.query_embed(question))

    sparse_vector = models.SparseVector(
        indices=sparse.indices.tolist(),
        values=sparse.values.tolist()
    )

    # Hybrid search with Reciprocal Rank Fusion
    result = qdrant.query_points(
        collection_name=COLLECTION,
        prefetch=[
            models.Prefetch(
                query=dense_vector,
                using="dense",
                limit=30
            ),
            models.Prefetch(
                query=sparse_vector,
                using="bm25",
                limit=30
            )
        ],
        query=models.FusionQuery(
            fusion=models.Fusion.RRF
        ),
        limit=top_k,
        with_payload=True
    )

    documents = []

    for point in result.points:
        payload = point.payload or {}

        documents.append({
            "page": payload.get("page_number"),
            "chunk_id": payload.get("chunk_id"),
            "text": payload.get("text", ""),
            "score": point.score,
            "source_file": payload.get("source_file"),
            "vehicle_model": payload.get("vehicle_model")
        })

    return documents
