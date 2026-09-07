"""Auth router: register / login (OAuth2 password flow) / me.

Additive to the spec — the frontend does not call these yet. They exist
so tokens can be adopted later without changing the spec endpoints.
"""

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from ..auth import (
    authenticate_user,
    create_access_token,
    get_current_user_optional,
    register_user,
)
from ..deps import get_store
from ..errors import ApiError
from ..models import Token, UserPublic, UserRegister
from ..protocols import UserStore
from ..store import DuplicateError

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=UserPublic, status_code=201)
def register(
    payload: UserRegister,
    store: UserStore = Depends(get_store),
) -> UserPublic:
    try:
        record = register_user(store, payload.username, payload.password)
    except DuplicateError as exc:
        raise ApiError(409, str(exc)) from exc
    return UserPublic(username=record.username)


@router.post("/auth/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    store: UserStore = Depends(get_store),
) -> Token:
    record = authenticate_user(store, form.username, form.password)
    if record is None:
        raise ApiError(401, "Incorrect username or password")
    return Token(access_token=create_access_token(record.username))


@router.get("/auth/me", response_model=UserPublic)
def me(username: str | None = Depends(get_current_user_optional)) -> UserPublic:
    if not username:
        raise ApiError(401, "Not authenticated")
    return UserPublic(username=username)
