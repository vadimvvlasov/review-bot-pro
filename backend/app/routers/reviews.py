"""Reviews router: queue CRUD, CSV import, on-demand generation."""

from fastapi import APIRouter, Body, Depends, File, Response, UploadFile

from ..auth import get_current_user_optional
from ..deps import get_store
from ..errors import ApiError
from ..models import (
    GenerateReplyRequest,
    ImportSummary,
    Review,
    ReviewCreate,
    UpdateReviewRequest,
)
from ..protocols import ReviewStore
from ..services import CsvFileError, LLMUnavailableError
from ..store import DuplicateError, NotFoundError, SettingsMissingError

router = APIRouter(tags=["reviews"])


@router.get("/reviews", response_model=list[Review])
def list_reviews(
    store: ReviewStore = Depends(get_store),
    _: str | None = Depends(get_current_user_optional),
) -> list[Review]:
    return store.list_reviews()


@router.post("/reviews", response_model=Review, status_code=201)
def create_review(
    payload: ReviewCreate,
    store: ReviewStore = Depends(get_store),
    _: str | None = Depends(get_current_user_optional),
) -> Review:
    try:
        return store.create_review(payload)
    except DuplicateError as exc:
        raise ApiError(409, str(exc)) from exc


@router.post("/reviews/import", response_model=ImportSummary, status_code=201)
async def import_reviews_csv(
    file: UploadFile = File(...),
    store: ReviewStore = Depends(get_store),
    _: str | None = Depends(get_current_user_optional),
) -> ImportSummary:
    try:
        return store.import_csv(await file.read())
    except CsvFileError as exc:
        raise ApiError(400, str(exc)) from exc


@router.post("/reviews/{review_id}/generate", response_model=Review)
def generate_reply(
    review_id: str,
    payload: GenerateReplyRequest | None = Body(default=None),
    store: ReviewStore = Depends(get_store),
    _: str | None = Depends(get_current_user_optional),
) -> Review:
    try:
        return store.generate_reply(
            review_id, payload.instructions if payload else None
        )
    except NotFoundError as exc:
        raise ApiError(404, str(exc)) from exc
    except SettingsMissingError as exc:
        raise ApiError(400, str(exc)) from exc
    except LLMUnavailableError as exc:
        raise ApiError(500, str(exc) or "Reply engine is unavailable") from exc


@router.patch("/reviews/{review_id}", response_model=Review)
def update_review(
    review_id: str,
    payload: UpdateReviewRequest,
    store: ReviewStore = Depends(get_store),
    _: str | None = Depends(get_current_user_optional),
) -> Review:
    try:
        return store.update_review(review_id, payload)
    except NotFoundError as exc:
        raise ApiError(404, str(exc)) from exc


@router.delete("/reviews/{review_id}", status_code=204)
def delete_review(
    review_id: str,
    store: ReviewStore = Depends(get_store),
    _: str | None = Depends(get_current_user_optional),
) -> Response:
    try:
        store.delete_review(review_id)
    except NotFoundError as exc:
        raise ApiError(404, str(exc)) from exc
    return Response(status_code=204)
