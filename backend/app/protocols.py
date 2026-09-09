"""Narrow store interfaces (ISP). Routers and services depend on these
abstractions, never on the concrete DbStore (DIP). The composition
root (main.create_app via deps.get_store) wires the concrete class."""

from typing import Protocol

from .models import (
    BusinessSettings,
    ImportSummary,
    Review,
    ReviewCreate,
    UpdateReviewRequest,
    UserRecord,
)


class SettingsStore(Protocol):
    def get_settings(self) -> BusinessSettings | None: ...
    def save_settings(self, payload: BusinessSettings) -> BusinessSettings: ...


class ReviewStore(Protocol):
    def list_reviews(self) -> list[Review]: ...
    def create_review(self, payload: ReviewCreate) -> Review: ...
    def get_review(self, review_id: str) -> Review: ...
    def update_review(self, review_id: str, patch: UpdateReviewRequest) -> Review: ...
    def delete_review(self, review_id: str) -> None: ...
    def import_csv(self, content: bytes) -> ImportSummary: ...
    def generate_reply(self, review_id: str, instructions: str | None) -> Review: ...


class UserStore(Protocol):
    @property
    def users(self) -> dict[str, UserRecord]: ...
