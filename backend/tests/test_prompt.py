"""Prompt composition asserts (spec §7, AC-10/AC-15)."""

from app.models import BusinessSettings, Review, ReviewSource
from app.prompt import compose_system_prompt, compose_user_prompt


def _settings() -> BusinessSettings:
    return BusinessSettings(
        business_name="Daily Grind Cafe",
        business_type="Coffee Shop",
        description="Cozy local cafe serving organic brews.",
        brand_voice="warm, welcoming, and slightly playful",
    )


def _review() -> Review:
    return Review(
        author_name="Ann Lee",
        review_text="Great espresso but service was a bit slow today.",
        rating=4,
        source=ReviewSource.manual,
    )


def test_system_prompt_formats_brand_voice():
    prompt = compose_system_prompt(_settings())
    assert "Daily Grind Cafe" in prompt
    assert "warm, welcoming, and slightly playful" in prompt
    assert "Coffee Shop" in prompt
    assert "Cozy local cafe" in prompt


def test_system_prompt_enforces_reply_constraints():
    prompt = compose_system_prompt(_settings())
    assert "1-3 sentences" in prompt
    assert "under 500" in prompt


def test_user_prompt_formats_review_and_instructions():
    prompt = compose_user_prompt(_review(), "offer a free cookie")
    assert "Ann Lee" in prompt
    assert "4/5" in prompt
    assert "Great espresso" in prompt
    assert "offer a free cookie" in prompt


def test_user_prompt_omits_empty_instructions():
    prompt = compose_user_prompt(_review(), "   ")
    assert "Owner instructions" not in prompt


def test_user_prompt_includes_existing_draft():
    review = _review()
    review.reply_text = "Earlier draft reply text here."
    assert "Earlier draft" in compose_user_prompt(review)
