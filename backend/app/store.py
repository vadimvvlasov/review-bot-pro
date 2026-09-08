"""In-memory persistence (Milestone 3): settings, review queue, users.

SRP: this module owns state and simple CRUD only. Reply generation and
CSV parsing live in services; this class composes them (constructor
injection keeps it open for extension, e.g. a real LLM client).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

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


class InMemoryStore:
    """Composition root for state + domain services."""

    def __init__(
        self,
        seed: bool = True,
        generator: ReplyGeneratorProtocol | None = None,
        importer: CsvImporter | None = None,
    ) -> None:
        self.settings: BusinessSettings | None = None
        self.reviews: dict[str, Review] = {}
        self.users: dict[str, UserRecord] = {}
        self._generator = generator or ReplyGenerator()
        self._importer = importer or CsvImporter()
        if seed:
            self.reset()

    def reset(self) -> None:
        """Restore seeded demo data (used on startup and in tests)."""
        self.settings = DEFAULT_SETTINGS.model_copy(deep=True)
        self.reviews = {}
        for seed in SEED_REVIEWS:
            review = _seed_review(seed)
            self.reviews[review.id] = review
        self.users = {}

    # -- settings ------------------------------------------------------
    def get_settings(self) -> BusinessSettings | None:
        return self.settings

    def save_settings(self, payload: BusinessSettings) -> BusinessSettings:
        self.settings = payload
        return self.settings

    # -- reviews -------------------------------------------------------
    @staticmethod
    def _key(author_name: str, review_text: str) -> tuple[str, str]:
        return (author_name.strip().lower(), review_text.strip().lower())

    def _is_duplicate(self, author_name: str, review_text: str) -> bool:
        key = self._key(author_name, review_text)
        return any(self._key(r.author_name, r.review_text) == key for r in self.reviews.values())

    def list_reviews(self) -> list[Review]:
        return sorted(self.reviews.values(), key=lambda r: r.created_at, reverse=True)

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
        self.reviews[review.id] = review
        return review

    def get_review(self, review_id: str) -> Review:
        try:
            return self.reviews[review_id]
        except KeyError:
            raise NotFoundError("Review not found") from None

    def update_review(self, review_id: str, patch: UpdateReviewRequest) -> Review:
        review = self.get_review(review_id)
        if patch.reply_text is not None:
            review.reply_text = patch.reply_text
        if patch.status is not None:
            review.status = patch.status
        return review

    def delete_review(self, review_id: str) -> None:
        if review_id not in self.reviews:
            raise NotFoundError("Review not found")
        del self.reviews[review_id]

    # -- import & generation delegate to domain services -----------------
    def import_csv(self, content: bytes) -> ImportSummary:
        return self._importer.run(content, self._is_duplicate, self.create_review)

    def generate_reply(self, review_id: str, instructions: str | None) -> Review:
        review = self.get_review(review_id)
        if self.settings is None:
            raise SettingsMissingError("Set up your business profile before generating replies")
        try:
            output = self._generator.generate(self.settings, review, instructions)
        except LLMUnavailableError:
            raise
        except Exception as exc:
            # AC-14: transport/unknown failures must surface as 500.
            # AC-13 degradation happens inside parse/degrade helpers,
            # not by swallowing transport errors here.
            raise LLMUnavailableError(f"Reply engine is unavailable: {exc}") from exc
        review.reply_text = output.reply_text
        review.detected_sentiment = output.detected_sentiment
        review.detected_tags = list(output.detected_tags)
        return review
