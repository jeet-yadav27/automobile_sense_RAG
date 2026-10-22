
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    Request,
)
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from api.schemas import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
)
from api.security import (
    hash_password,
    verify_password,
    generate_token,
    hash_token,
    session_expiration,
)
from db.database import get_db
from db.models import User, AuthSession

from fastapi import Response, Depends, Request
from api.dependencies import (
    get_auth_session,
    get_current_user,
    verify_csrf,
)


router = APIRouter()

COOKIE_NAME = "warranty_session"


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    user = User(
        email=str(data.email).lower(),
        password_hash=hash_password(data.password),
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        )

    return UserResponse(
        id=user.id,
        email=user.email,
    )


@router.post("/login")
def login(
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    email = str(data.email).lower()

    user = db.scalar(
        select(User).where(User.email == email)
    )

    if (
        user is None
        or not verify_password(
            data.password,
            user.password_hash
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    token = generate_token()
    csrf_token = generate_token()

    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token_hash=hash_token(csrf_token),
        expires_at=session_expiration(),
    )

    db.add(session)
    db.commit()

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,  # Local HTTP only
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/",
    )

    return {
        "message": "Login successful",
        "user": {
            "id": user.id,
            "email": user.email,
        },
        "csrf_token": csrf_token,
    }




@router.get("/me", response_model=UserResponse)
def me(
    user: User = Depends(get_current_user),
):
    return UserResponse(
        id=user.id,
        email=user.email,
    )


@router.get("/csrf")
def get_csrf_token(
    session: AuthSession = Depends(get_auth_session),
    db: Session = Depends(get_db),
):
    # Rotate the CSRF token for this session.
    csrf_token = generate_token()
    session.csrf_token_hash = hash_token(csrf_token)
    db.commit()

    return {"csrf_token": csrf_token}


@router.post("/logout")
def logout(
    response: Response,
    session: AuthSession = Depends(get_auth_session),
    _: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    db.delete(session)
    db.commit()

    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        samesite="lax",
    )

    return {"message": "Logged out successfully"}
