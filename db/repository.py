
from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlalchemy import select

from db.models import (
    User,
    Conversation,
    Message,
)


def create_conversation(
    db: Session,
    user_id: str,
    title: str = "New conversation",
):
    conversation = Conversation(
        user_id=user_id,
        title=title[:200],
    )

    db.add(conversation)
    db.flush()

    return conversation


def get_user_conversations(
    db: Session,
    user_id: str,
):
    statement = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )

    return db.scalars(statement).all()


# def get_conversation(
#     db: Session,
#     conversation_id: str,
#     user_id: str,
# ):
#     statement = select(Conversation).where(
#         Conversation.id == conversation_id,
#         Conversation.user_id == user_id,
#     )

#     return db.scalar(statement)

def get_conversation(db, conversation_id, user_id):
    return db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )


def add_message(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
    sources=None,
):
    if role not in {"user", "assistant"}:
        raise ValueError("Invalid message role")

    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        sources=sources or [],
    )

    db.add(message)
    db.flush()

    return message


def get_messages(
    db: Session,
    conversation_id: str,
):
    statement = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id
        )
        .order_by(
            Message.created_at.asc(),
            Message.id.asc(),
        )
    )

    return db.scalars(statement).all()




def list_user_conversations(db, user_id: str):
    return db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(
            Conversation.updated_at.desc(),
            Conversation.id.desc(),
        )
    ).all()

