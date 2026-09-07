"""Stateless domain services: reply generation and CSV import.

SRP: pure business logic lives here, independent of HTTP (routers) and
persistence (store). Both services depend on abstractions (callables /
protocols), never on the concrete store (DIP). Swap ReplyGenerator for a
real LLM client without touching callers (OCP).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable

from .models import (
    BusinessSettings,
    ImportRowError,
    ImportSummary,
    Review,
    ReviewCreate,
    ReviewSource,
    Sentiment,
)

CSV_MAX_BYTES = 1024 * 1024  # 1 MB (AC-04)
CSV_MAX_ROWS = 100  # AC-04
REQUIRED_HEADERS = ("author_name", "review_text", "rating")

_POSITIVE_WORDS = (
    "great", "best", "love", "lovely", "amazing", "friendly", "fresh", "unreal", "perfect",
)
_NEGATIVE_WORDS = (
    "wait", "waited", "slow", "cold", "lukewarm", "rude", "dirty", "expensive", "bad",
)
_TAG_WORDS: dict[str, tuple[str, ...]] = {
    "service": ("service", "staff", "barista", "waited", "wait", "rude", "friendly"),
    "pricing": ("price", "pricing", "expensive", "cheap", "value", "high"),
    "coffee": ("coffee", "espresso", "latte", "brew", "flat white", "cold brew"),
    "food": ("pastry", "pastries", "bun", "buns", "cake", "food", "sandwich"),
    "atmosphere": ("cozy", "atmosphere", "music", "wifi", "seating", "spot", "place"),
    "speed": ("slow", "fast", "quick", "minutes", "rush"),
}


class CsvFileError(Exception):
    """Whole-file rejection -> 400."""


class ReplyGenerator:
    """Deterministic stand-in for the single structured LLM call (AC-09..AC-13)."""

    def generate(
        self, settings: BusinessSettings, review: Review, instructions: str | None
    ) -> tuple[str, Sentiment, list[str]]:
        sentiment = self._classify(review.review_text, review.rating)
        first_name = (review.author_name.split(" ")[0] or "there").strip() or "there"
        reply = f"{self._opening(sentiment, first_name)} {self._middle(sentiment, settings)} {self._closing(instructions)}"
        return self._clamp(reply), sentiment, self._extract_tags(review.review_text)

    @staticmethod
    def _classify(review_text: str, rating: int) -> Sentiment:
        text = review_text.lower()
        pos = sum(w in text for w in _POSITIVE_WORDS) + (2 if rating >= 4 else 0)
        neg = sum(w in text for w in _NEGATIVE_WORDS) + (2 if rating <= 2 else 0)
        if pos > neg:
            return Sentiment.positive
        if neg > pos:
            return Sentiment.negative
        return Sentiment.neutral

    @staticmethod
    def _opening(sentiment: Sentiment, first_name: str) -> str:
        if sentiment is Sentiment.positive:
            return f"Thank you for the kind words, {first_name}!"
        if sentiment is Sentiment.negative:
            return f"Thank you for the honest feedback, {first_name}, and we're sorry we fell short."
        return f"Thanks for taking the time to share this, {first_name}."

    @staticmethod
    def _middle(sentiment: Sentiment, settings: BusinessSettings) -> str:
        if sentiment is Sentiment.negative:
            return (
                f"We're reviewing how we handle busy periods at {settings.business_name} "
                "so the wait and the quality both improve."
            )
        return (
            f"Hearing that from a guest at {settings.business_name} genuinely makes our day."
        )

    @staticmethod
    def _closing(instructions: str | None) -> str:
        if instructions and instructions.strip():
            return f"As promised: {' '.join(instructions.split())[:160]}"
        return "We hope to welcome you back soon."

    @staticmethod
    def _extract_tags(review_text: str) -> list[str]:
        text = review_text.lower()
        return [tag for tag, words in _TAG_WORDS.items() if any(w in text for w in words)][:3]

    @staticmethod
    def _clamp(text: str) -> str:
        text = text.strip()
        return text if len(text) <= 500 else f"{text[:497].rstrip()}..."


class CsvImporter:
    """Parses review CSVs (AC-04..AC-06). Store-agnostic: persistence enters
    via the is_duplicate/save callables (DIP)."""

    def run(
        self,
        content: bytes,
        is_duplicate: Callable[[str, str], bool],
        save: Callable[[ReviewCreate], None],
    ) -> ImportSummary:
        headers, data = self._split_rows(self._decode(content))
        errors: list[ImportRowError] = []
        imported = 0
        for index, cells in enumerate(data):
            row = self._validate_row(headers, cells, index + 2)
            if isinstance(row, ImportRowError):
                errors.append(row)
            elif is_duplicate(row.author_name, row.review_text):
                errors.append(ImportRowError(row=index + 2, error="Duplicate review skipped"))
            else:
                save(row)
                imported += 1
        return ImportSummary(status="success", imported=imported, skipped=len(errors), errors=errors)

    @staticmethod
    def _decode(content: bytes) -> str:
        if len(content) > CSV_MAX_BYTES:
            raise CsvFileError("CSV file exceeds the 1 MB size limit")
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise CsvFileError("Invalid CSV encoding (expected UTF-8)") from None

    @staticmethod
    def _split_rows(text: str) -> tuple[list[str], list[list[str]]]:
        rows = [row for row in csv.reader(io.StringIO(text)) if any(c.strip() for c in row)]
        if not rows:
            raise CsvFileError("CSV file is empty")
        headers = [h.strip().lower() for h in rows[0]]
        missing = [h for h in REQUIRED_HEADERS if h not in headers]
        if missing:
            raise CsvFileError(f"CSV is missing required column(s): {', '.join(missing)}")
        data = rows[1:]
        if len(data) > CSV_MAX_ROWS:
            raise CsvFileError(f"CSV contains {len(data)} reviews; the limit is {CSV_MAX_ROWS}")
        return headers, data

    @staticmethod
    def _validate_row(
        headers: list[str], cells: list[str], row_number: int
    ) -> ReviewCreate | ImportRowError:
        def get(key: str) -> str:
            pos = headers.index(key)
            return cells[pos].strip() if pos < len(cells) else ""

        author_name, review_text, rating_raw = get("author_name"), get("review_text"), get("rating")
        try:
            rating = int(rating_raw)
        except ValueError:
            return ImportRowError(row=row_number, error="Rating must be between 1 and 5")
        if not 1 <= rating <= 5:
            return ImportRowError(row=row_number, error="Rating must be between 1 and 5")
        if not author_name or len(author_name) > 100:
            return ImportRowError(row=row_number, error="Author name cannot be empty")
        if not 3 <= len(review_text) <= 5000:
            return ImportRowError(row=row_number, error="Review text must be 3-5000 characters")
        return ReviewCreate(
            author_name=author_name,
            review_text=review_text,
            rating=rating,
            source=ReviewSource.csv,
        )
