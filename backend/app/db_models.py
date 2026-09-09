"""SQLAlchemy ORM tables mirroring `docs/spec.md` §5 plus auth users.

SRP: schema only — no queries here. Portable column types (String,
Integer, Text, DateTime, JSON) keep the schema database-agnostic:
identical DDL works on SQLite today and Postgres later.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BusinessSettingsRow(Base):
    """Single-row business profile (`id` is always 1, spec AC-01)."""

    __tablename__ = "business_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_settings_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    business_name: Mapped[str] = mapped_column(Text, nullable=False)
    business_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    brand_voice: Mapped[str] = mapped_column(Text, nullable=False)


class ReviewRow(Base):
    """Flat review queue table (spec §5)."""

    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating"),
        CheckConstraint(
            "detected_sentiment IN ('positive', 'neutral', 'negative')",
            name="ck_review_sentiment",
        ),
        CheckConstraint("status IN ('draft', 'approved')", name="ck_review_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    detected_sentiment: Mapped[str | None] = mapped_column(
        String(10), nullable=True, default=None
    )
    detected_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class UserRow(Base):
    """Auth credentials (passwords stored hashed, never plain text)."""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
