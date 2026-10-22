
from hybrid_retrieval import hybrid_retrieve
from reranking_service import rerank_documents
from query_rewrite import rewrite_query


def main():
    questions = [
        "What is the warranty period for S-Presso?",
        "What is the warranty for the lead acid battery?",
        "What is the warranty for the ISG?",
        "What happens when the vehicle crosses 100000 km?",
    ]

    for question in questions:
        print("\n" + "=" * 70)
        print("QUESTION:", question)

        # Hybrid dense + BM25 retrieval
        candidates = hybrid_retrieve(
            question=question,
            top_k=15
        )


        search_question = rewrite_query(question)

        print("Original question:", question)
        print("Search question:", search_question)

        candidates = hybrid_retrieve(
            question=search_question,
            top_k=30
        )

        # results = rerank_documents(
        #     question=search_question,
        #     documents=candidates,
        #     top_k=5
        # )

        # Cross-encoder reranking
        results = rerank_documents(
            question=question,
            documents=candidates,
            top_k=5
        )

        for rank, doc in enumerate(results, start=1):
            print(f"\nRank: {rank}")
            print(f"Page: {doc['page']}")
            print(f"Chunk: {doc['chunk_id']}")
            print(f"RRF score: {doc['score']:.4f}")
            print(f"Rerank score: {doc['rerank_score']:.4f}")
            print(f"Best passage:\n{doc['best_passage']}")
            print("-" * 50)


if __name__ == "__main__":
    main()
