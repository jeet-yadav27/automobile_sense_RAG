
import asyncio
import logging
import threading

from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError

from api.concurrency import rag_semaphore
from api.locks import ConversationLock
from db.database import SessionLocal
from db.idempotency import (
    find_request,
    request_fingerprint,
)
from db.models import ChatRequestRecord
from services.persistent_rag import generate_persistent_answer
from db.repository import (
    create_conversation,
    get_conversation,
    get_messages,
    add_message,
)

logger = logging.getLogger(__name__)


def execute_chat(
    user_id: str,
    conversation_id: str | None,
    question: str,
    idempotency_key: str,
):
    fingerprint = request_fingerprint(
        conversation_id,
        question,
    )

    # A new conversation has no ID yet, so serialize
    # its creation using the idempotency key.
    lock_id = (
        conversation_id
        or f"new:{user_id}:{idempotency_key}"
    )

    lock = ConversationLock(lock_id, ttl=120)

    try:
        if not lock.acquire():
            raise HTTPException(
                409,
                "Conversation is currently processing",
            )
    except RedisError:
        raise HTTPException(
            503,
            "Conversation lock unavailable",
        )

    try:
        with SessionLocal() as db:
            existing = find_request(
                db, user_id, idempotency_key
            )

            if existing:
                if existing.request_hash != fingerprint:
                    raise HTTPException(
                        409,
                        "Idempotency key reused with different data",
                    )

                if existing.status == "completed":
                    return existing.response_json

                raise HTTPException(
                    409,
                    "Request is already processing",
                )

            record = ChatRequestRecord(
                user_id=user_id,
                idempotency_key=idempotency_key,
                request_hash=fingerprint,
                status="processing",
            )

            db.add(record)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(
                    409,
                    "Request is already registered",
                )

        # Load history without holding an open transaction
        # during expensive RAG inference.
        with SessionLocal() as db:
            if conversation_id:
                conversation = get_conversation(
                    db, conversation_id, user_id
                )
                if conversation is None:
                    raise HTTPException(
                        404, "Conversation not found"
                    )
                history = get_messages(
                    db, conversation.id
                )
            else:
                history = []

            # Materialize messages before closing session.
            history_data = [
                type(
                    "HistoryMessage",
                    (),
                    {
                        "role": m.role,
                        "content": m.content,
                    },
                )()
                for m in history
            ]

        result = generate_persistent_answer(
            question=question,
            previous_messages=history_data,
        )

        with SessionLocal() as db:
            record = find_request(
                db, user_id, idempotency_key
            )

            if conversation_id:
                conversation = get_conversation(
                    db, conversation_id, user_id
                )
                if conversation is None:
                    raise HTTPException(
                        404, "Conversation not found"
                    )
            else:
                conversation = create_conversation(
                    db,
                    user_id,
                    title=question[:100],
                )

            db.flush()

            add_message(
                db, conversation.id, "user", question
            )
            add_message(
                db,
                conversation.id,
                "assistant",
                result["answer"],
                result["sources"],
            )

            result["conversation_id"] = conversation.id

            record.status = "completed"
            record.conversation_id = conversation.id
            record.response_json = result

            db.commit()

            return result

    finally:
        try:
            lock.release()
        except RedisError:
            logger.exception("Failed to release lock")


async def execute_chat_async(
    user_id: str,
    conversation_id: str | None,
    question: str,
    idempotency_key: str,
):
    async with rag_semaphore:
        task = asyncio.create_task(
            asyncio.to_thread(
                execute_chat,
                user_id,
                conversation_id,
                question,
                idempotency_key,
            )
        )

        try:
            return await asyncio.wait_for(
                asyncio.shield(task),
                timeout=60,
            )
        except asyncio.TimeoutError:
            # The worker continues and retains the lock.
            # Retrieve the result later using the same key.
            task.add_done_callback(
                lambda t: (
                    logger.error(
                        "Background chat failed: %s",
                        t.exception(),
                    )
                    if not t.cancelled() and t.exception()
                    else None
                )
            )

            raise HTTPException(
                504,
                "RAG request timed out; retry with the same key",
            )
