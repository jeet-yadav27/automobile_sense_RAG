
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
)

from opentelemetry import trace

from services.conversational_lcel import (
    rewrite_chain,
)

from services.lcel_rag import (
    retrieve_and_rerank,
    format_context,
    answer_chain,
)


# OpenTelemetry tracer
# Uses the Azure Monitor provider configured in api/main.py.
tracer = trace.get_tracer(__name__)


def generate_persistent_answer(
    question: str,
    previous_messages: list,
):
    history = []

    # Keep the latest 10 exchanges in LLM context.
    for message in previous_messages[-20:]:
        if message.role == "user":
            history.append(
                HumanMessage(content=message.content)
            )
        elif message.role == "assistant":
            history.append(
                AIMessage(content=message.content)
            )

    # Step 1: Rewrite the question using conversation history.
    with tracer.start_as_current_span("rag.query_rewrite"):
        search_question = rewrite_chain.invoke({
            "chat_history": history,
            "question": question,
        })

    # Step 2: Retrieve and rerank relevant documents.
    with tracer.start_as_current_span(
        "rag.retrieve_and_rerank"
    ) as span:
        documents = retrieve_and_rerank(search_question)

        span.set_attribute(
            "rag.retrieved_documents",
            len(documents),
        )

    # Step 3: Format retrieved documents for the LLM.
    context = format_context(documents)

    # Step 4: Generate the final answer.
    with tracer.start_as_current_span("rag.answer_generation"):
        answer = answer_chain.invoke({
            "question": question,
            "context": context,
        })

    # Step 5: Prepare document citations.
    sources = [
        {
            "page": doc["page"],
            "chunk_id": doc["chunk_id"],
        }
        for doc in documents
    ]

    return {
        "question": question,
        "search_question": search_question,
        "answer": answer,
        "sources": sources,
    }
