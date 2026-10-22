
import os
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from fastembed import SparseTextEmbedding

PROJECT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_DIR / ".env")

QDRANT_URL = os.getenv(
    "QDRANT_URL", "http://localhost:6333"
)

SOURCE_COLLECTION = "spresso_manual_full"
TARGET_COLLECTION = "spresso_hybrid_v1"

DENSE_NAME = "dense"
SPARSE_NAME = "bm25"
BM25_MODEL = "Qdrant/bm25"

BATCH_SIZE = 32

client = QdrantClient(url=QDRANT_URL, timeout=60)
sparse_model = SparseTextEmbedding(model_name=BM25_MODEL)


def get_source_vector(point):
    """Extract existing dense vector."""
    vector = point.vector

    if isinstance(vector, dict):
        # Existing collection may use named vectors.
        if len(vector) != 1:
            raise ValueError(
                "Source has multiple vectors. "
                "Select the correct dense vector explicitly."
            )
        vector = next(iter(vector.values()))

    if vector is None:
        raise ValueError(
            f"Missing vector for point {point.id}"
        )

    return vector


def get_dense_config():
    info = client.get_collection(SOURCE_COLLECTION)
    config = info.config.params.vectors

    if isinstance(config, dict):
        if len(config) != 1:
            raise ValueError(
                "Source has multiple vector configurations."
            )
        return next(iter(config.values()))

    return config


def create_collection():
    source_config = get_dense_config()

    if client.collection_exists(TARGET_COLLECTION):
        raise RuntimeError(
            f"{TARGET_COLLECTION} already exists. "
            "Use a new versioned collection name "
            "instead of overwriting it."
        )

    client.create_collection(
        collection_name=TARGET_COLLECTION,
        vectors_config={
            DENSE_NAME: models.VectorParams(
                size=source_config.size,
                distance=source_config.distance
            )
        },
        sparse_vectors_config={
            SPARSE_NAME: models.SparseVectorParams(
                modifier=models.Modifier.IDF
            )
        }
    )

    print(f"Created collection: {TARGET_COLLECTION}")


def upload_batch(batch):
    texts = [
        (point.payload or {}).get("text", "")
        for point in batch
    ]

    sparse_vectors = list(
        sparse_model.embed(texts)
    )

    points = []

    for point, sparse in zip(batch, sparse_vectors):
        payload = point.payload or {}

        if not payload.get("text", "").strip():
            continue

        dense_vector = get_source_vector(point)

        points.append(
            models.PointStruct(
                id=point.id,
                vector={
                    DENSE_NAME: dense_vector,
                    SPARSE_NAME: models.SparseVector(
                        indices=sparse.indices.tolist(),
                        values=sparse.values.tolist()
                    )
                },
                payload={
                    **payload,
                    "vehicle_model": "S-Presso"
                }
            )
        )

    if points:
        client.upsert(
            collection_name=TARGET_COLLECTION,
            points=points,
            wait=True
        )

    return len(points)


def main():
    if not client.collection_exists(SOURCE_COLLECTION):
        raise RuntimeError(
            f"Source collection not found: {SOURCE_COLLECTION}"
        )

    create_collection()

    offset = None
    total = 0

    while True:
        records, offset = client.scroll(
            collection_name=SOURCE_COLLECTION,
            limit=BATCH_SIZE,
            offset=offset,
            with_payload=True,
            with_vectors=True
        )

        if not records:
            break

        count = upload_batch(records)
        total += count

        print(f"Indexed {total} chunks")

        if offset is None:
            break

    info = client.get_collection(TARGET_COLLECTION)

    print("\nHybrid indexing completed!")
    print("Collection:", TARGET_COLLECTION)
    print("Uploaded chunks:", total)
    print("Stored points:", info.points_count)


if __name__ == "__main__":
    main()
