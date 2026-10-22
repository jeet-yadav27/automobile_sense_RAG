
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")

openai_client = OpenAI()
qdrant_client = QdrantClient(url="http://localhost:6333")

COLLECTION_NAME = "spresso_manual_full"
EMBEDDING_MODEL = "text-embedding-3-small"
TOP_K = 5

question = input("Enter your question: ").strip()

if not question:
    raise ValueError("Question cannot be empty.")

# Step 1: Generate question embedding.
response = openai_client.embeddings.create(
    model=EMBEDDING_MODEL,
    input=question,
)

question_vector = response.data[0].embedding

# Step 2: Retrieve similar chunks.
results = qdrant_client.query_points(
    collection_name=COLLECTION_NAME,
    query=question_vector,
    limit=TOP_K,
    with_payload=True,
).points

# Step 3: Display evidence and citations.
print("\n" + "=" * 60)
print("FULL MANUAL SEMANTIC SEARCH")
print("=" * 60)
print("Question:", question)

for rank, point in enumerate(results, start=1):
    payload = point.payload or {}

    print(f"\nRank: {rank}")
    print(f"Similarity score: {point.score:.4f}")
    print(f"PDF page: {payload.get('page_number')}")
    print(f"Chunk ID: {payload.get('chunk_id')}")
    print("Retrieved text:")
    print(payload.get("text", ""))
    print("-" * 60)

print(f"\nQuestion embedding tokens: {response.usage.total_tokens}")
