
from lcel_rag import ask


questions = [
    "What is the warranty period for S-Presso?",
    "What is the warranty for the lead acid battery?",
    # "What is the warranty for the ISG?",
]

for question in questions:
    print("\n" + "=" * 70)

    result = ask(question)

    print("Question:", result["question"])
    print("Search query:", result["search_question"])

    print("\nANSWER:")
    print(result["answer"])

    print("\nRETRIEVED SOURCES:")

    for source in result["sources"]:
        print(
            f"Page {source['page']} | "
            f"{source['chunk_id']} | "
            f"Rerank: {source['rerank_score']:.3f}"
        )
