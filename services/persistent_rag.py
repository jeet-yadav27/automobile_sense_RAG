
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
)

from services.conversational_lcel import (
    rewrite_chain,
)
from services.lcel_rag import (
    retrieve_and_rerank,
    format_context,
    answer_chain,
)


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

    search_question = rewrite_chain.invoke({
        "chat_history": history,
        "question": question,
    })

    documents = retrieve_and_rerank(search_question)
    context = format_context(documents)

    answer = answer_chain.invoke({
        "question": question,
        "context": context,
    })

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
