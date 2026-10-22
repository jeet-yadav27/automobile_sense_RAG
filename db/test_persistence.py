
from pathlib import Path
import sys
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from db.database import SessionLocal
from db.models import User
from db.repository import (
    create_conversation,
    add_message,
    get_messages,
    get_user_conversations,
)


def main():
    db = SessionLocal()

    try:
        test_email = (
            f"test-{uuid.uuid4().hex[:8]}@example.com"
        )

        # This user is only for database testing.
        # Never use a placeholder hash for login.
        user = User(
            email=test_email,
            password_hash="TEST_ONLY_NOT_A_REAL_HASH",
        )

        db.add(user)
        db.flush()

        conversation = create_conversation(
            db=db,
            user_id=user.id,
            title="S-Presso warranty discussion",
        )

        add_message(
            db=db,
            conversation_id=conversation.id,
            role="user",
            content="What is the S-Presso warranty?",
        )

        add_message(
            db=db,
            conversation_id=conversation.id,
            role="assistant",
            content=(
                "36 months or 100,000 km, "
                "whichever comes first."
            ),
            sources=[
                {
                    "page": 8,
                    "chunk_id": "page_8_chunk_0",
                }
            ],
        )

        db.commit()

        print("Saved conversation:", conversation.id)

        conversations = get_user_conversations(
            db, user.id
        )

        print("User conversations:", len(conversations))

        messages = get_messages(
            db, conversation.id
        )

        for message in messages:
            print(
                message.role,
                "=>",
                message.content,
            )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
