
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient, models

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY is missing")

openai_client = OpenAI()
qdrant_client = QdrantClient(url="http://localhost:6333")

COLLECTION_NAME = "spresso_embedding_demo"
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536

texts = [
    "What is the warranty period of the vehicle?",
    "How long does the vehicle warranty last?",
    "How do I check the engine oil level?",
]

# 1. Create the collection only if it does not exist.
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
    print("Collection already exists:", COLLECTION_NAME)

# 2. Convert the three sentences into vectors.
response = openai_client.embeddings.create(
    model=EMBEDDING_MODEL,
    input=texts,
)

# 3. Prepare Qdrant points.
points = []

for index, item in enumerate(response.data):
    points.append(
        models.PointStruct(
            id=index + 1,
            vector=item.embedding,
            payload={
                "text": texts[index],
                "source": "embedding_demo",
                "embedding_model": EMBEDDING_MODEL,
            },
        )
    )

# 4. Store points in Qdrant.
qdrant_client.upsert(
    collection_name=COLLECTION_NAME,
    points=points,
    wait=True,
)

# 5. Check the number of stored points.
count = qdrant_client.count(
    collection_name=COLLECTION_NAME,
    exact=True,
).count

print("Stored points:", count)
print("Vector dimensions:", VECTOR_SIZE)
print("Embedding tokens used:", response.usage.total_tokens)
print("Qdrant storage successful!")
