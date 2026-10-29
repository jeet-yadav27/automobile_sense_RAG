
import json
from pathlib import Path

from src.rag.rag_with_reranking import retrieve

ROOT = Path(__file__).resolve().parents[1]

with open(
    ROOT / "evaluation" / "live_dataset.json",
    encoding="utf-8",
) as f:
    dataset = json.load(f)

for item in dataset:
    question = item["question"]
    print("\n" + "=" * 70)
    print("QUESTION:", question)

    candidates = retrieve(question)

    for rank, c in enumerate(candidates, start=1):
        print(f"\nRank: {rank}")
        print("Chunk ID:", c["chunk_id"])
        print("PDF page:", c["page"])
        print("Vector score:", round(c["vector_score"], 4))
        print("Text:", c["text"][:700])
