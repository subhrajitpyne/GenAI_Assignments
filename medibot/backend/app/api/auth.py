from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.auth import authenticate_user, create_access_token
from app.core.config import ROLE_COLLECTIONS

router = APIRouter(tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    name: str
    username: str
    collections: list[str]


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """Authenticate user and return JWT token with role information."""
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(
        data={"sub": user["username"], "role": user["role"], "name": user["name"]}
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        role=user["role"],
        name=user["name"],
        username=user["username"],
        collections=ROLE_COLLECTIONS.get(user["role"], []),
    )
