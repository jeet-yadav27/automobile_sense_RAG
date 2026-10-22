
from conversational_lcel import ask_conversational


def main():
    session_id = "test_user_001"

    print("S-PRESSO CONVERSATIONAL RAG")
    print("Type 'exit' to quit")

    while True:
        question = input("\nYou: ").strip()

        if question.lower() == "exit":
            break

        if not question:
            continue

        result = ask_conversational(
            question=question,
            session_id=session_id
        )

        print("\nSearch question:")
        print(result["search_question"])

        print("\nAssistant:")
        print(result["answer"])

        print("\nSources:")
        for source in result["sources"]:
            print(
                f"PDF page {source['page']} | "
                f"{source['chunk_id']}"
            )


if __name__ == "__main__":
    main()
