from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.di import get_db_session
from app.core.security import create_token_pair, decode_token, get_password_hash, verify_password
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    token = authorization.replace("Bearer ", "")
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    return user


@router.post("/register")
async def register(
    email: str,
    password: str,
    full_name: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    tokens = create_token_pair(user.id, user.email)
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
        },
        **tokens,
    }


@router.post("/login")
async def login(
    email: str,
    password: str,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    tokens = create_token_pair(user.id, user.email)
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
        },
        **tokens,
    }


@router.post("/refresh")
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db_session),
):
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = payload.get("sub")
    email = payload.get("email")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or user.email != email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    tokens = create_token_pair(user.id, user.email)
    return tokens


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
    }


# Export for other routers to use
__all__ = ["router", "get_current_user"]