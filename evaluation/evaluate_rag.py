
import json
from pathlib import Path


def recall_at_k(retrieved_ids, relevant_ids, k=5):
    relevant = set(relevant_ids)

    if not relevant:
        return None

    retrieved = set(retrieved_ids[:k])

    return len(retrieved & relevant) / len(relevant)


def reciprocal_rank(retrieved_ids, relevant_ids):
    relevant = set(relevant_ids)

    if not relevant:
        return None

    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant:
            return 1 / rank

    return 0.0


def evaluate_retrieval(retrieved_ids, relevant_ids):
    return {
        "recall_at_5": recall_at_k(
            retrieved_ids, relevant_ids, k=5
        ),
        "reciprocal_rank": reciprocal_rank(
            retrieved_ids, relevant_ids
        ),
    }


if __name__ == "__main__":
    # Illustrative document IDs, not real Qdrant results.
    retrieved = ["chunk_7", "chunk_2", "chunk_5"]
    relevant = ["chunk_2", "chunk_5"]

    scores = evaluate_retrieval(retrieved, relevant)

    print(json.dumps(scores, indent=2))
