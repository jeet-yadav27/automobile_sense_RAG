
import os
from pathlib import Path
import json

from dotenv import load_dotenv
from openai import OpenAI

# Import the functions from Lesson 13.
from rag_with_reranking import (
    retrieve,
    rerank,
    build_context,
    generate_answer,
)

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_DIR / ".env")

client = OpenAI()
LLM_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

MAX_HISTORY_MESSAGES = 6




def rewrite_question(question, history):
    if not history:
        return question

    recent_history = history[-MAX_HISTORY_MESSAGES:]

    response = client.chat.completions.create(
        model=LLM_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": """
You are a contextual question rewriting component
for an automotive warranty RAG application.

Your task:
Convert the latest user question into a complete,
standalone search question.

Rules:
1. Never answer the question.
2. Never return warranty durations or mileage limits
   unless explicitly stated in the latest question.
3. Preserve the active conversation topic.
4. If the conversation discusses warranty and the
   user asks "What about [component]?", interpret
   it as a question about that component's warranty.
5. If the conversation discusses maintenance, preserve
   maintenance as the topic instead.
6. Preserve distinctions between lead-acid batteries,
   HEV batteries, and hybrid-system components.
7. Include the vehicle model when relevant.
8. If a question is already complete, keep its meaning.
9. Return a question ending with '?'.
10. Return only JSON with the key "search_question".

Examples:

History: What is the warranty period for S-Presso?
Latest: What about the lead acid battery?
Output: What is the warranty period for the
S-Presso lead-acid battery?

History: What is the warranty period for S-Presso?
Latest: And what about the hybrid battery?
Output: What is the warranty period for the
S-Presso Hybrid Electric Vehicle (HEV) battery?

History: What is the warranty period for S-Presso?
Latest: What happens if my vehicle crosses 100,000 km?
Output: What happens to the standard S-Presso vehicle
warranty after exceeding 100,000 kilometers?
"""
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "history": recent_history,
                        "latest_question": question
                    },
                    ensure_ascii=False
                )
            }
        ]
    )

    data = json.loads(response.choices[0].message.content)
    rewritten = data["search_question"].strip()

    if not rewritten.endswith("?"):
        raise ValueError(
            f"Invalid rewritten question: {rewritten}"
        )

    return rewritten




def main():
    history = []

    print("=" * 60)
    print("S-PRESSO CONVERSATIONAL RAG")
    print("Type 'exit' to stop.")
    print("=" * 60)

    while True:
        question = input("\nYou: ").strip()

        if question.lower() in ("exit", "quit"):
            break

        if not question:
            continue

        # Step 1: Resolve follow-up references.
        search_question = rewrite_question(
            question,
            history
        )

        # print("\nSearch question:", search_question)

        print("Original question:", question)
        print("Rewritten question:", search_question)

        # Step 2: Retrieve and rerank.
        candidates = retrieve(search_question)
        selected = rerank(search_question, candidates)

        if not selected:
            print("Assistant: No supporting passages found.")
            continue

        # Step 3: Generate grounded answer.
        context = build_context(selected)

        answer = generate_answer(
            search_question,
            context
        )

        print("\nAssistant:", answer)

        print("\nSources:")
        for item in selected:
            print(
                f"  PDF page {item['page']} "
                f"| {item['chunk_id']}"
            )

        # Step 4: Update in-memory history.
        history.append({
            "role": "user",
            "content": question
        })

        history.append({
            "role": "assistant",
            "content": answer
        })


if __name__ == "__main__":
    main()
