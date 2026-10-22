
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(
        min_length=1,
        max_length=128
    )
    question: str = Field(
        min_length=1,
        max_length=2000
    )


class SourceResponse(BaseModel):
    page: int | None = None
    chunk_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    question: str
    search_question: str
    answer: str
    sources: list[SourceResponse]


class HealthResponse(BaseModel):
    status: str
    service: str




from pydantic import EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=12,
        max_length=128
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr


class PersistentChatRequest(BaseModel):
    conversation_id: str | None = None
    question: str = Field(
        min_length=1,
        max_length=2000,
    )


class PersistentChatResponse(BaseModel):
    conversation_id: str
    question: str
    search_question: str
    answer: str
    sources: list[SourceResponse]


# from pydantic import BaseModel, Field

# class PersistentChatRequest(BaseModel):
#     message: str = Field(..., min_length=1)
#     conversation_id: int | None = None