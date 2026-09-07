"""Settings router: GET/PUT /api/settings."""

from typing import Optional

from fastapi import APIRouter, Depends

from ..auth import get_current_user_optional
from ..deps import get_store
from ..models import BusinessSettings
from ..protocols import SettingsStore

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=Optional[BusinessSettings])
def get_settings(
    store: SettingsStore = Depends(get_store),
    _: str | None = Depends(get_current_user_optional),
) -> BusinessSettings | None:
    return store.get_settings()


@router.put("/settings", response_model=BusinessSettings)
def save_settings(
    payload: BusinessSettings,
    store: SettingsStore = Depends(get_store),
    _: str | None = Depends(get_current_user_optional),
) -> BusinessSettings:
    return store.save_settings(payload)
