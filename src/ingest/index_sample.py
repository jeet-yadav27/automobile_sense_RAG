
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient, models

PROJECT_DIR = Path(__file__).resolve().parents[2]
CHUNKS_PATH = PROJECT_DIR / "data" / "processed" / "chunks.jsonl"

load_dotenv(PROJECT_DIR / ".env")

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY is missing")

openai_client = OpenAI()
qdrant_client = QdrantClient(url="http://localhost:6333")

COLLECTION_NAME = "spresso_manual_sample"
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536
SAMPLE_SIZE = 10

# Read the first 10 chunks from the JSONL file.
chunks = []

with CHUNKS_PATH.open("r", encoding="utf-8") as file:
    for line in file:
        if not line.strip():
            continue

        chunks.append(json.loads(line))

        if len(chunks) == SAMPLE_SIZE:
            break

if not chunks:
    raise RuntimeError("No chunks found in chunks.jsonl")

# Create collection if necessary.
if not qdrant_client.collection_exists(COLLECTION_NAME):
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=VECTOR_SIZE,
            distance=models.Distance.COSINE,
        ),
    )
    print("Collection created:", COLLECTION_NAME)

# Generate embeddings for the sample chunks.
response = openai_client.embeddings.create(
    model=EMBEDDING_MODEL,
    input=[chunk["text"] for chunk in chunks],
)

points = []

for index, embedding in enumerate(response.data):
    chunk = chunks[index]

    points.append(
        models.PointStruct(
            id=index + 1,
            vector=embedding.embedding,
            payload={
                "chunk_id": chunk["chunk_id"],
                "source_file": chunk["source_file"],
                "document_title": "S-Presso Owner's Manual",
                "page_number": chunk["page_number"],
                "text": chunk["text"],
                "embedding_model": EMBEDDING_MODEL,
            },
        )
    )

qdrant_client.upsert(
    collection_name=COLLECTION_NAME,
    points=points,
    wait=True,
)

count = qdrant_client.count(
    collection_name=COLLECTION_NAME,
    exact=True,
).count

print("=" * 50)
print("SAMPLE INDEXING COMPLETED")
print("=" * 50)
print("Chunks indexed:", len(points))
print("Total points in collection:", count)
print("Embedding tokens used:", response.usage.total_tokens)
print("Collection:", COLLECTION_NAME)
