
from functools import lru_cache
import re

from sentence_transformers import CrossEncoder


@lru_cache(maxsize=1)
def get_reranker():
    return CrossEncoder(
        "cross-encoder/ms-marco-MiniLM-L-6-v2"
    )


def split_passages(text, max_words=100, overlap=25):
    words = re.findall(r"\S+", text)

    if not words:
        return []

    passages = []
    step = max_words - overlap

    for start in range(0, len(words), step):
        passage = " ".join(
            words[start:start + max_words]
        )

        if passage:
            passages.append(passage)

        if start + max_words >= len(words):
            break

    return passages


def rerank_documents(question, documents, top_k=5):
    if not documents:
        return []

    pairs = []
    mapping = []

    for doc_index, doc in enumerate(documents):
        passages = split_passages(doc.get("text", ""))

        for passage in passages:
            pairs.append((question, passage))
            mapping.append((doc_index, passage))

    if not pairs:
        return []

    scores = get_reranker().predict(
        pairs,
        batch_size=16,
        show_progress_bar=False
    )

    best_scores = {}

    for (doc_index, passage), score in zip(
        mapping, scores
    ):
        score = float(score)

        if (
            doc_index not in best_scores
            or score > best_scores[doc_index][0]
        ):
            best_scores[doc_index] = (
                score,
                passage
            )

    ranked = []

    for index, doc in enumerate(documents):
        if index not in best_scores:
            continue

        score, passage = best_scores[index]

        item = doc.copy()
        item["rerank_score"] = score
        item["best_passage"] = passage

        ranked.append(item)

    ranked.sort(
        key=lambda x: x["rerank_score"],
        reverse=True
    )

    return ranked[:top_k]
