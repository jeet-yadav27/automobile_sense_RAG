from qdrant_client import QdrantClient

client = QdrantClient(
    url="http://localhost:6333",
    timeout=10,
)