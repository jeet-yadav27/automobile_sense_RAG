
from pathlib import Path
import sys

from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
)
from langchain_openai import ChatOpenAI

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
load_dotenv(PROJECT_DIR / ".env")

from services.lcel_rag import (
    retrieve_and_rerank,
    format_context,
    answer_chain,
)


llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0
)


rewrite_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
Rewrite the latest user question into a
standalone search question about the
Maruti Suzuki S-Presso Owner's Manual.

Use chat history only to resolve references
and ambiguity.

Preserve the user's intended meaning.
Do not answer the question.
Return only the rewritten question.
"""
    ),
    ("placeholder", "{chat_history}"),
    ("human", "{question}")
])


rewrite_chain = (
    rewrite_prompt
    | llm
    | RunnableLambda(
        lambda message: message.content.strip()
    )
)


# Learning-only in-memory conversation store.
# Later we will replace this with persistent storage.
sessions = {}


def ask_conversational(question: str, session_id: str):
    if not question.strip():
        raise ValueError("Question cannot be empty")

    history = sessions.setdefault(session_id, [])

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

    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=answer))

    # Keep the latest 10 exchanges.
    sessions[session_id] = history[-20:]

    return {
        "session_id": session_id,
        "question": question,
        "search_question": search_question,
        "answer": answer,
        "sources": [
            {
                "page": doc["page"],
                "chunk_id": doc["chunk_id"],
            }
            for doc in documents
        ],
    }
