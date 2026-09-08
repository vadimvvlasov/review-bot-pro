"""Pydantic contracts mirroring the frontend zod schemas and openapi.yaml."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReviewStatus(str, Enum):
    draft = "draft"
    approved = "approved"


class Sentiment(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class ReviewSource(str, Enum):
    manual = "manual"
    csv = "csv"
    google = "google"
    yelp = "yelp"
    tripadvisor = "tripadvisor"


class BusinessSettings(BaseModel):
    """PUT /api/settings payload and GET /api/settings response (AC-01/AC-02)."""

    business_name: str = Field(min_length=1, max_length=100)
    business_type: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=3, max_length=1000)
    brand_voice: str = Field(min_length=1, max_length=100)


class ReviewCreate(BaseModel):
    """POST /api/reviews payload (AC-03)."""

    author_name: str = Field(min_length=1, max_length=100)
    review_text: str = Field(min_length=3, max_length=5000)
    rating: int = Field(ge=1, le=5)
    source: ReviewSource = ReviewSource.manual

    @field_validator("author_name", "review_text", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        # Mirror the frontend, which trims before validating lengths.
        return v.strip() if isinstance(v, str) else v


class Review(ReviewCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reply_text: Optional[str] = Field(default=None, max_length=500)
    detected_sentiment: Optional[Sentiment] = None
    detected_tags: list[str] = Field(default_factory=list)
    status: ReviewStatus = ReviewStatus.draft
    created_at: str = Field(default_factory=_utcnow_iso)


class GenerateReplyRequest(BaseModel):
    """POST /api/reviews/{id}/generate payload. The whole body is optional."""

    instructions: Optional[str] = Field(default=None, max_length=500)


class LLMStructuredOutput(BaseModel):
    """Single-call structured LLM contract (AC-09..AC-13, spec §6)."""

    reply_text: str = Field(min_length=10, max_length=500)
    detected_sentiment: Optional[Sentiment] = None
    detected_tags: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("detected_tags", mode="before")
    @classmethod
    def _coerce_tags(cls, v: object) -> object:
        # Graceful degradation: invalid tag payloads fall back to [].
        if v is None:
            return []
        if not isinstance(v, list):
            return []
        cleaned = [t.strip().lower() for t in v if isinstance(t, str) and t.strip()]
        return cleaned[:3]

    @field_validator("detected_sentiment", mode="before")
    @classmethod
    def _coerce_sentiment(cls, v: object) -> object:
        # Graceful degradation: unknown sentiment falls back to None.
        if v is None:
            return None
        if isinstance(v, Sentiment):
            return v
        if isinstance(v, str):
            try:
                return Sentiment(v.strip().lower())
            except ValueError:
                return None
        return None


class UpdateReviewRequest(BaseModel):
    """PATCH /api/reviews/{id} payload (AC-16/AC-17). Both fields optional."""

    reply_text: Optional[str] = Field(default=None, max_length=500)
    status: Optional[ReviewStatus] = None


class ImportRowError(BaseModel):
    row: int
    error: str


class ImportSummary(BaseModel):
    """POST /api/reviews/import 201 response (AC-06)."""

    status: str = "success"
    imported: int
    skipped: int
    errors: list[ImportRowError] = Field(default_factory=list)


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class UserPublic(BaseModel):
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


@dataclass
class UserRecord:
    """Stored credentials (password never stored in plain text)."""

    username: str
    password_hash: str
