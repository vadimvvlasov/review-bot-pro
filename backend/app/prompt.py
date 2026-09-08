"""Prompt composition for the reply-generation pipeline (AC-09/AC-15).

SRP: pure string building only. Mirrors frontend prompt.ts so mock and
real LLM clients exercise the same context-engineering path. Unit-tested
per spec §7; no network access here.
"""

from __future__ import annotations

from .models import BusinessSettings, Review


def compose_system_prompt(settings: BusinessSettings) -> str:
    return "\n".join(
        [
            f'You are the owner of "{settings.business_name}", a {settings.business_type}.',
            f"Business context: {settings.description}",
            f"Brand voice: {settings.brand_voice}.",
            "Reply to the customer review in 1-3 sentences, under 500 characters.",
            "Return JSON with keys reply_text, detected_sentiment "
            "(positive|neutral|negative) and detected_tags "
            "(1-3 short lowercase keywords).",
        ]
    )


def compose_user_prompt(review: Review, instructions: str | None = None) -> str:
    parts = [f"Review by {review.author_name} ({review.rating}/5): {review.review_text}"]
    if review.reply_text:
        parts.append(f"Existing draft: {review.reply_text}")
    if instructions and instructions.strip():
        parts.append(f"Owner instructions: {instructions.strip()}")
    return "\n".join(parts)
