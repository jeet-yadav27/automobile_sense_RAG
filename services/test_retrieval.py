
from retrieval_service import retrieve_documents
from reranking_service import rerank_documents


def main():
    question = "What is the warranty period for S-Presso?"

    # Stage 1: Vector retrieval
    candidates = retrieve_documents(
        question=question,
        top_k=15
    )

    print(f"\nQuestion: {question}")
    print(f"Vector candidates: {len(candidates)}")

    # Stage 2: Reranking
    documents = rerank_documents(
        question=question,
        documents=candidates,
        top_k=5
    )

    print("\nTOP RERANKED RESULTS")

    for index, doc in enumerate(documents, 1):
        print("\n" + "=" * 50)
        print(f"Rank: {index}")
        print(f"Page: {doc['page']}")
        print(f"Chunk ID: {doc['chunk_id']}")
        print(f"Vector score: {doc['score']:.4f}")
        print(f"Rerank score: {doc['rerank_score']:.4f}")
        print(f"Text:\n{doc['text']}")


if __name__ == "__main__":
    main()
