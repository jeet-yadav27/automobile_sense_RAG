
from pathlib import Path
import os

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY is missing from .env")

client = OpenAI()

texts = [
    "What is the warranty period of the vehicle?",
    "How long does the vehicle warranty last?",
    "How do I check the engine oil level?",
]

response = client.embeddings.create(
    model="text-embedding-3-small",
    input=texts,
)

embeddings = [item.embedding for item in response.data]

print("Number of embeddings:", len(embeddings))
print("Dimensions per embedding:", len(embeddings[0]))
print("First five values:", embeddings[0][:5])
print("Tokens used:", response.usage.total_tokens)



import math

def cosine_similarity(vector_a, vector_b):
    dot_product = sum(
        a * b for a, b in zip(vector_a, vector_b)
    )

    magnitude_a = math.sqrt(
        sum(a * a for a in vector_a)
    )

    magnitude_b = math.sqrt(
        sum(b * b for b in vector_b)
    )

    if magnitude_a == 0 or magnitude_b == 0:
        raise ValueError("Cannot compare zero-length vectors")

    return dot_product / (magnitude_a * magnitude_b)


print("\n" + "=" * 50)
print("COSINE SIMILARITY RESULTS")
print("=" * 50)

similarity_ab = cosine_similarity(
    embeddings[0], embeddings[1]
)

similarity_ac = cosine_similarity(
    embeddings[0], embeddings[2]
)

similarity_bc = cosine_similarity(
    embeddings[1], embeddings[2]
)

print(f"A vs B (Warranty vs Warranty): {similarity_ab:.4f}")
print(f"A vs C (Warranty vs Oil):      {similarity_ac:.4f}")
print(f"B vs C (Warranty vs Oil):      {similarity_bc:.4f}")

print("\nIs A-B more similar than A-C?", similarity_ab > similarity_ac)
