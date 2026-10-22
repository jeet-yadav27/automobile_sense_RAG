
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY is missing")

openai_client = OpenAI()
qdrant_client = QdrantClient(url="http://localhost:6333")

COLLECTION_NAME = "spresso_manual_sample"
EMBEDDING_MODEL = "text-embedding-3-small"

question = "What information does the S-Presso owner's manual contain?"

# Step 1: Embed the question.
response = openai_client.embeddings.create(
    model=EMBEDDING_MODEL,
    input=question,
)

question_vector = response.data[0].embedding

# Step 2: Search Qdrant.
results = qdrant_client.query_points(
    collection_name=COLLECTION_NAME,
    query=question_vector,
    limit=3,
    with_payload=True,
).points

# Step 3: Display results with source references.
print("=" * 60)
print("MANUAL SEMANTIC SEARCH")
print("=" * 60)
print("Question:", question)

for rank, point in enumerate(results, start=1):
    payload = point.payload or {}

    print(f"\nRank: {rank}")
    print(f"Similarity score: {point.score:.4f}")
    print(f"Chunk ID: {payload.get('chunk_id')}")
    print(f"Document: {payload.get('document_title')}")
    print(f"PDF page: {payload.get('page_number')}")
    print("Text preview:")
    print(payload.get("text", "")[:600])
    print("-" * 60)
