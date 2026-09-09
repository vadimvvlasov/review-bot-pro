"""Database-backed persistence (Milestone 4): settings, review queue, users.

SRP: this module owns state and simple CRUD only. Reply generation and
CSV parsing live in services; this class composes them (constructor
injection keeps it open for extension, e.g. a real LLM client).

Database-agnostic: all queries use portable SQLAlchemy constructs that
render on SQLite and Postgres alike. The URL comes from `DATABASE_URL`
(`app.config.Settings`); only the URL changes to switch databases.
A short session is opened per operation, so callers (routers, tests)
keep the same synchronous store API regardless of backend.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, MutableMapping
from datetime import datetime, timezone

from sqlalchemy import func, select

from . import db_models  # noqa: F401 — registers tables on Base.metadata.
from .db import create_engine_for_url, create_session_factory, init_db
from .db_models import BusinessSettingsRow, ReviewRow, UserRow
from .models import (
    BusinessSettings,
    ImportSummary,
    Review,
    ReviewCreate,
    ReviewSource,
    ReviewStatus,
    Sentiment,
    UpdateReviewRequest,
    UserRecord,
)
from .services import CsvImporter, LLMUnavailableError, ReplyGenerator, ReplyGeneratorProtocol


class NotFoundError(Exception):
    pass


class DuplicateError(Exception):
    pass


class SettingsMissingError(Exception):
    pass


DEFAULT_SETTINGS = BusinessSettings(
    business_name="Daily Grind Cafe",
    business_type="Coffee Shop",
    description="Cozy local cafe serving organic single-origin brews and homemade pastries.",
    brand_voice="warm, welcoming, and slightly playful",
)

# Mirror of the frontend mock seeds so the UI has something to show.
SEED_REVIEWS: tuple[dict, ...] = (
    {
        "author_name": "Maria Petrova",
        "rating": 5,
        "review_text": (
            "The flat white here is the best in town and the staff remembered "
            "my name on my second visit. The pastries are always fresh."
        ),
        "source": "google",
        "reply_text": None,
        "detected_sentiment": None,
        "detected_tags": [],
        "status": "draft",
        "created_at": "2026-09-05T08:12:00+00:00",
    },
    {
        "author_name": "Tom Ridley",
        "rating": 2,
        "review_text": (
            "Waited 20 minutes for a latte during the morning rush and it "
            "arrived lukewarm. Nice place, but the service needs work."
        ),
        "source": "yelp",
        "reply_text": None,
        "detected_sentiment": None,
        "detected_tags": [],
        "status": "draft",
        "created_at": "2026-09-04T15:40:00+00:00",
    },
    {
        "author_name": "Aiko Tanaka",
        "rating": 4,
        "review_text": (
            "Lovely spot to work from in the afternoon. Wifi is fast, "
            "though the pricing on cold brew feels a touch high."
        ),
        "source": "tripadvisor",
        "reply_text": None,
        "detected_sentiment": None,
        "detected_tags": [],
        "status": "draft",
        "created_at": "2026-09-03T11:05:00+00:00",
    },
    {
        "author_name": "Daniel Okafor",
        "rating": 5,
        "review_text": (
            "Great espresso, friendly barista, and the cinnamon buns are "
            "unreal. Will be back weekly."
        ),
        "source": "google",
        "reply_text": (
            "Thank you so much, Daniel! We are thrilled the espresso and "
            "cinnamon buns hit the spot. See you next week!"
        ),
        "detected_sentiment": "positive",
        "detected_tags": ["espresso", "service"],
        "status": "approved",
        "created_at": "2026-09-01T09:22:00+00:00",
    },
)


def _parse_created_at(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _row_to_review(row: ReviewRow) -> Review:
    created = row.created_at
    if created.tzinfo is None:  # SQLite drops tzinfo; stored values are UTC.
        created = created.replace(tzinfo=timezone.utc)
    return Review(
        id=row.id,
        author_name=row.author_name,
        rating=row.rating,
        review_text=row.review_text,
        source=ReviewSource(row.source),
        reply_text=row.reply_text,
        detected_sentiment=Sentiment(row.detected_sentiment) if row.detected_sentiment else None,
        detected_tags=list(row.detected_tags or []),
        status=ReviewStatus(row.status),
        created_at=created.isoformat(),
    )


def _seed_review(seed: dict) -> Review:
    return Review(
        id=str(uuid.uuid4()),
        author_name=seed["author_name"],
        rating=seed["rating"],
        review_text=seed["review_text"],
        source=ReviewSource(seed["source"]),
        reply_text=seed["reply_text"],
        detected_sentiment=Sentiment(seed["detected_sentiment"])
        if seed["detected_sentiment"]
        else None,
        detected_tags=list(seed["detected_tags"]),
        status=ReviewStatus(seed["status"]),
        created_at=seed["created_at"],
    )


def _insert_review_row(session, review: Review) -> ReviewRow:
    row = ReviewRow(
        id=review.id,
        author_name=review.author_name,
        rating=review.rating,
        review_text=review.review_text,
        source=review.source.value,
        reply_text=review.reply_text,
        detected_sentiment=review.detected_sentiment.value if review.detected_sentiment else None,
        detected_tags=list(review.detected_tags),
        status=review.status.value,
        created_at=_parse_created_at(review.created_at),
    )
    session.add(row)
    return row


class DbUserMap(MutableMapping):
    """Dict-like user view over the `users` table.

    Lets `app.auth` keep plain dict syntax (`in`, `[]`, `.get`) while
    persisting every write — no auth code changes needed.
    """

    def __init__(self, session_factory) -> None:
        self._sessions = session_factory

    def __getitem__(self, username: str) -> UserRecord:
        with self._sessions() as session:
            row = session.get(UserRow, username)
        if row is None:
            raise KeyError(username)
        return UserRecord(username=row.username, password_hash=row.password_hash)

    def __setitem__(self, username: str, record: UserRecord) -> None:
        with self._sessions() as session:
            session.merge(UserRow(username=record.username, password_hash=record.password_hash))
            session.commit()

    def __delitem__(self, username: str) -> None:
        with self._sessions() as session:
            row = session.get(UserRow, username)
            if row is None:
                raise KeyError(username)
            session.delete(row)
            session.commit()

    def __iter__(self) -> Iterator[str]:
        with self._sessions() as session:
            return iter(list(session.scalars(select(UserRow.username))))

    def __len__(self) -> int:
        with self._sessions() as session:
            return session.query(UserRow).count()


class DbStore:
    """Composition root for state + domain services, backed by SQLAlchemy."""

    def __init__(
        self,
        database_url: str = "sqlite:///./reviews.db",
        seed: bool = True,
        generator: ReplyGeneratorProtocol | None = None,
        importer: CsvImporter | None = None,
    ) -> None:
        self.database_url = database_url
        self._engine = create_engine_for_url(database_url)
        init_db(self._engine)
        self._Session = create_session_factory(self._engine)
        self._generator = generator or ReplyGenerator()
        self._importer = importer or CsvImporter()
        if seed:
            self.seed_if_empty()

    @property
    def users(self) -> DbUserMap:
        return DbUserMap(self._Session)

    def seed_if_empty(self) -> None:
        """Insert demo data only when the database has none.

        Seeding (not wiping) preserves rows across server restarts —
        the Milestone 4 verification gate. Use `reset()` for a hard
        wipe back to demo data.
        """
        with self._Session() as session:
            has_settings = session.get(BusinessSettingsRow, 1) is not None
            has_reviews = session.query(ReviewRow).first() is not None
            if has_settings or has_reviews:
                return
            session.merge(
                BusinessSettingsRow(id=1, **DEFAULT_SETTINGS.model_copy(deep=True).model_dump())
            )
            for seed in SEED_REVIEWS:
                _insert_review_row(session, _seed_review(seed))
            session.commit()

    def reset(self) -> None:
        """Wipe all tables and restore seeded demo data (tests/dev)."""
        with self._Session() as session:
            session.query(ReviewRow).delete()
            session.query(UserRow).delete()
            session.query(BusinessSettingsRow).delete()
            session.merge(BusinessSettingsRow(id=1, **DEFAULT_SETTINGS.model_copy(deep=True).model_dump()))
            for seed in SEED_REVIEWS:
                _insert_review_row(session, _seed_review(seed))
            session.commit()

    # -- settings ------------------------------------------------------
    def get_settings(self) -> BusinessSettings | None:
        with self._Session() as session:
            row = session.get(BusinessSettingsRow, 1)
            if row is None:
                return None
            return BusinessSettings(
                business_name=row.business_name,
                business_type=row.business_type,
                description=row.description,
                brand_voice=row.brand_voice,
            )

    def save_settings(self, payload: BusinessSettings) -> BusinessSettings:
        with self._Session() as session:
            session.merge(BusinessSettingsRow(id=1, **payload.model_dump()))
            session.commit()
        return payload

    # -- reviews -------------------------------------------------------
    @staticmethod
    def _duplicate_stmt(author_name: str, review_text: str):
        return select(ReviewRow.id).where(
            func.lower(ReviewRow.author_name) == author_name.strip().lower(),
            func.lower(ReviewRow.review_text) == review_text.strip().lower(),
        )

    def _is_duplicate(self, author_name: str, review_text: str, session=None) -> bool:
        stmt = self._duplicate_stmt(author_name, review_text)
        if session is not None:
            return session.scalar(stmt) is not None
        with self._Session() as fresh:
            return fresh.scalar(stmt) is not None

    def list_reviews(self) -> list[Review]:
        with self._Session() as session:
            rows = session.scalars(select(ReviewRow).order_by(ReviewRow.created_at.desc())).all()
            return [_row_to_review(r) for r in rows]

    def create_review(self, payload: ReviewCreate) -> Review:
        if self._is_duplicate(payload.author_name, payload.review_text):
            raise DuplicateError("This review already exists in your queue")
        review = Review(
            id=str(uuid.uuid4()),
            author_name=payload.author_name,
            rating=payload.rating,
            review_text=payload.review_text,
            source=payload.source,
            reply_text=None,
            detected_sentiment=None,
            detected_tags=[],
            status=ReviewStatus.draft,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._Session() as session:
            _insert_review_row(session, review)
            session.commit()
        return review

    def get_review(self, review_id: str) -> Review:
        with self._Session() as session:
            row = session.get(ReviewRow, review_id)
            if row is None:
                raise NotFoundError("Review not found")
            return _row_to_review(row)

    def update_review(self, review_id: str, patch: UpdateReviewRequest) -> Review:
        with self._Session() as session:
            row = session.get(ReviewRow, review_id)
            if row is None:
                raise NotFoundError("Review not found")
            if patch.reply_text is not None:
                row.reply_text = patch.reply_text
            if patch.status is not None:
                row.status = patch.status.value
            session.commit()
            return _row_to_review(row)

    def delete_review(self, review_id: str) -> None:
        with self._Session() as session:
            row = session.get(ReviewRow, review_id)
            if row is None:
                raise NotFoundError("Review not found")
            session.delete(row)
            session.commit()

    # -- import & generation delegate to domain services -----------------
    def import_csv(self, content: bytes) -> ImportSummary:
        """Validate via CsvImporter, insert valid rows in one transaction."""
        with self._Session() as session:
            def is_duplicate(author_name: str, review_text: str) -> bool:
                return self._is_duplicate(author_name, review_text, session)

            def save(payload: ReviewCreate) -> None:
                _insert_review_row(
                    session,
                    Review(
                        id=str(uuid.uuid4()),
                        author_name=payload.author_name,
                        rating=payload.rating,
                        review_text=payload.review_text,
                        source=payload.source,
                        reply_text=None,
                        detected_sentiment=None,
                        detected_tags=[],
                        status=ReviewStatus.draft,
                        created_at=datetime.now(timezone.utc).isoformat(),
                    ),
                )
                session.flush()  # expose the row to later duplicate checks.

            summary = self._importer.run(content, is_duplicate, save)
            session.commit()
            return summary

    def generate_reply(self, review_id: str, instructions: str | None) -> Review:
        # Snapshot outside any transaction: never hold a DB lock during
        # the (possibly network) LLM call.
        with self._Session() as session:
            row = session.get(ReviewRow, review_id)
            if row is None:
                raise NotFoundError("Review not found")
            review = _row_to_review(row)
            settings_row = session.get(BusinessSettingsRow, 1)
            if settings_row is None:
                raise SettingsMissingError("Set up your business profile before generating replies")
            business = BusinessSettings(
                business_name=settings_row.business_name,
                business_type=settings_row.business_type,
                description=settings_row.description,
                brand_voice=settings_row.brand_voice,
            )
        try:
            output = self._generator.generate(business, review, instructions)
        except LLMUnavailableError:
            raise
        except Exception as exc:
            # AC-14: transport/unknown failures must surface as 500.
            # AC-13 degradation happens inside parse/degrade helpers,
            # not by swallowing transport errors here.
            raise LLMUnavailableError(f"Reply engine is unavailable: {exc}") from exc
        with self._Session() as session:
            row = session.get(ReviewRow, review_id)
            if row is None:
                raise NotFoundError("Review not found")
            row.reply_text = output.reply_text
            row.detected_sentiment = output.detected_sentiment.value if output.detected_sentiment else None
            row.detected_tags = list(output.detected_tags)
            session.commit()
            return _row_to_review(row)
