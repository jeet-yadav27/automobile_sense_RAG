
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

COLLECTION_NAME = "spresso_embedding_demo"
EMBEDDING_MODEL = "text-embedding-3-small"

question = "How many years is my car covered under warranty?"

# Step 1: Convert the question into an embedding.
response = openai_client.embeddings.create(
    model=EMBEDDING_MODEL,
    input=question,
)

question_vector = response.data[0].embedding

print("Question:", question)
print("Question vector dimensions:", len(question_vector))
print("Embedding tokens used:", response.usage.total_tokens)

# Step 2: Search the existing Qdrant collection.
results = qdrant_client.query_points(
    collection_name=COLLECTION_NAME,
    query=question_vector,
    limit=3,
    with_payload=True,
).points

# Step 3: Display the matching sentences.
print("\n" + "=" * 50)
print("SEMANTIC SEARCH RESULTS")
print("=" * 50)

for rank, point in enumerate(results, start=1):
    print(f"\nRank: {rank}")
    print(f"Point ID: {point.id}")
    print(f"Similarity score: {point.score:.4f}")
    print(f"Text: {point.payload.get('text')}")
