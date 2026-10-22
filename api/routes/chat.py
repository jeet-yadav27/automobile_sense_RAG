
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.concurrency import rag_semaphore
from api.dependencies import (
    get_current_user,
    verify_csrf,
)
from api.schemas import (
    PersistentChatRequest,
    PersistentChatResponse,
)
from db.database import SessionLocal, get_db
from db.models import User
from db.repository import (
    add_message,
    create_conversation,
    get_conversation,
    get_messages,
    list_user_conversations,
)
from services.persistent_rag import generate_persistent_answer


router = APIRouter()
logger = logging.getLogger(__name__)


def process_chat(user_id: str, data: PersistentChatRequest):
    # Create and use the SQLAlchemy session in the
    # same worker thread.
    with SessionLocal() as db:
        try:
            if data.conversation_id:
                conversation = get_conversation(
                    db,
                    data.conversation_id,
                    user_id,
                )
                if conversation is None:
                    raise HTTPException(
                        404, "Conversation not found"
                    )
            else:
                conversation = create_conversation(
                    db,
                    user_id=user_id,
                    title=data.question[:100],
                )
                db.flush()

            history = get_messages(db, conversation.id)

            result = generate_persistent_answer(
                question=data.question,
                previous_messages=history,
            )

            add_message(
                db,
                conversation.id,
                "user",
                data.question,
            )

            add_message(
                db,
                conversation.id,
                "assistant",
                result["answer"],
                result["sources"],
            )

            conversation.updated_at = (
                datetime.now(timezone.utc)
            )

            db.commit()

            result["conversation_id"] = conversation.id
            return result

        except Exception:
            db.rollback()
            raise



from fastapi import Header

from api.chat_execution import execute_chat_async
from api.rate_limit import enforce_chat_rate_limit


@router.post(
    "/chat",
    response_model=PersistentChatResponse,
    dependencies=[
        Depends(verify_csrf),
        Depends(enforce_chat_rate_limit),
    ],
)
async def chat(
    data: PersistentChatRequest,
    user: User = Depends(get_current_user),
    idempotency_key: str = Header(
        min_length=16,
        max_length=100,
    ),
):
    if not data.question.strip():
        raise HTTPException(
            422,
            "Question cannot be blank",
        )

    return await execute_chat_async(
        user_id=user.id,
        conversation_id=data.conversation_id,
        question=data.question,
        idempotency_key=idempotency_key,
    )


@router.get("/conversations")
def list_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversations = list_user_conversations(
        db, user.id
    )

    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = get_conversation(
        db, conversation_id, user.id
    )

    if conversation is None:
        raise HTTPException(
            404, "Conversation not found"
        )

    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "sources": m.sources,
        }
        for m in get_messages(db, conversation.id)
    ]


@router.delete(
    "/conversations/{conversation_id}",
    dependencies=[Depends(verify_csrf)],
)
def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = get_conversation(
        db, conversation_id, user.id
    )

    if conversation is None:
        raise HTTPException(
            404, "Conversation not found"
        )

    db.delete(conversation)
    db.commit()

    return {"deleted": True}
