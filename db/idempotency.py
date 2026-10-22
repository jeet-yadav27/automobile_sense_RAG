
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ChatRequestRecord


def request_fingerprint(
    conversation_id: str | None,
    question: str,
) -> str:
    payload = json.dumps(
        {
            "conversation_id": conversation_id,
            "question": question,
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def find_request(
    db: Session,
    user_id: str,
    idempotency_key: str,
):
    return db.scalar(
        select(ChatRequestRecord).where(
            ChatRequestRecord.user_id == user_id,
            ChatRequestRecord.idempotency_key ==
            idempotency_key,
        )
    )
