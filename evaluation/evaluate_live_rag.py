
import csv
import json
from pathlib import Path

from src.rag.rag_with_reranking import (
    retrieve,
    rerank,
    build_context,
    generate_answer,
)

from evaluation.evaluate_rag import (
    recall_at_k,
    reciprocal_rank,
)

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "live_dataset.json"
REPORT_DIR = ROOT / "evaluation" / "reports"


def evaluate_question(item, method):
    question = item["question"]
    relevant_ids = [
        str(x) for x in item.get("relevant_chunk_ids", [])
    ]

    # Retrieve from actual Qdrant collection.
    candidates = retrieve(question)

    if method == "vector":
        selected = candidates[:5]
    elif method == "llm_rerank":
        selected = rerank(question, candidates)
    else:
        raise ValueError(f"Unknown method: {method}")

    # Build context and generate answer.
    context = build_context(selected)

    if selected:
        answer = generate_answer(question, context)
    else:
        answer = "No supporting passages found."

    retrieved_ids = [
        str(c["chunk_id"])
        for c in selected
    ]

    # Calculate metrics only when labels exist.
    recall = recall_at_k(
        retrieved_ids, relevant_ids, k=5
    )
    mrr = reciprocal_rank(
        retrieved_ids, relevant_ids
    )

    return {
        "question": question,
        "method": method,
        "answer": answer,
        "reference": item.get("reference", ""),
        "recall_at_5": recall,
        "mrr": mrr,
        "retrieved_chunk_ids": json.dumps(
            retrieved_ids
        ),
        "retrieved_pages": json.dumps(
            [c["page"] for c in selected]
        ),
        "retrieved_contexts": json.dumps(
            [c["text"] for c in selected],
            ensure_ascii=False,
        ),
    }


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with DATASET.open(encoding="utf-8") as f:
        dataset = json.load(f)

    results = []

    for item in dataset:
        for method in ("vector", "llm_rerank"):
            print(
                f"\nEvaluating: {item['question']}"
                f"\nMethod: {method}",
                flush=True,
            )

            result = evaluate_question(item, method)
            results.append(result)

            print("Answer:", result["answer"][:250])
            print("Recall@5:", result["recall_at_5"])
            print("MRR:", result["mrr"])

    output = REPORT_DIR / "live_retrieval_results.csv"

    with output.open(
        "w", newline="", encoding="utf-8-sig"
    ) as f:
        writer = csv.DictWriter(
            f, fieldnames=list(results[0].keys())
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\nEvaluation saved to: {output}")


if __name__ == "__main__":
    main()
