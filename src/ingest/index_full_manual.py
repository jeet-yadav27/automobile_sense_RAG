
import json
import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient, models

PROJECT_DIR = Path(__file__).resolve().parents[2]
CHUNKS_PATH = PROJECT_DIR / "data" / "processed" / "chunks.jsonl"

load_dotenv(PROJECT_DIR / ".env")

openai_client = OpenAI(max_retries=2, timeout=60.0)
qdrant_client = QdrantClient(
    url="http://localhost:6333",
    timeout=60,
)

COLLECTION_NAME = "spresso_manual_full"
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536
BATCH_SIZE = 50
MAX_ATTEMPTS = 3

# Read all chunks.
with CHUNKS_PATH.open("r", encoding="utf-8") as file:
    chunks = [
        json.loads(line)
        for line in file
        if line.strip()
    ]

print("Total chunks loaded:", len(chunks))

if not chunks:
    raise RuntimeError("No chunks found.")

# Create collection if it doesn't exist.
if not qdrant_client.collection_exists(COLLECTION_NAME):
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=VECTOR_SIZE,
            distance=models.Distance.COSINE,
        ),
    )
    print("Collection created:", COLLECTION_NAME)
else:
    info = qdrant_client.get_collection(COLLECTION_NAME)
    config = info.config.params.vectors

    if (
        config.size != VECTOR_SIZE
        or config.distance != models.Distance.COSINE
    ):
        raise RuntimeError(
            "Existing collection has an incompatible vector configuration."
        )

    print("Using existing collection:", COLLECTION_NAME)

total_tokens = 0

for start in range(0, len(chunks), BATCH_SIZE):
    batch = chunks[start:start + BATCH_SIZE]
    texts = [chunk["text"] for chunk in batch]

    # Retry embedding calls on transient failures.
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
            )
            break
        except Exception as exc:
            if attempt == MAX_ATTEMPTS:
                raise

            wait_seconds = 2 ** attempt
            print(
                f"Embedding attempt {attempt} failed: "
                f"{type(exc).__name__}. "
                f"Retrying in {wait_seconds}s..."
            )
            time.sleep(wait_seconds)

    # Match embeddings by the API-provided input index.
    embedding_by_index = {
        item.index: item.embedding
        for item in response.data
    }

    points = []

    for index, chunk in enumerate(batch):
        # Stable UUID from source file + chunk ID.
        point_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{chunk['source_file']}:{chunk['chunk_id']}",
            )
        )

        points.append(
            models.PointStruct(
                id=point_id,
                vector=embedding_by_index[index],
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

    # Upsert is safe to repeat with the same point IDs.
    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True,
    )

    total_tokens += response.usage.total_tokens

    completed = min(start + BATCH_SIZE, len(chunks))
    print(
        f"Indexed {completed}/{len(chunks)} chunks "
        f"| API tokens this run: {total_tokens:,}"
    )

count = qdrant_client.count(
    collection_name=COLLECTION_NAME,
    exact=True,
).count

print("\n" + "=" * 50)
print("FULL INDEXING COMPLETED")
print("=" * 50)
print("Expected chunks:", len(chunks))
print("Stored points:", count)
print("API embedding tokens this run:", total_tokens)
print("Collection:", COLLECTION_NAME)
