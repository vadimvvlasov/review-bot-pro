"""System prompt composition (spec §7) + LLM degradation/failure (AC-13/AC-14)."""

from app.models import BusinessSettings, LLMStructuredOutput, Review, ReviewSource
from app.prompt import compose_system_prompt, compose_user_prompt
from app.services import (
    LLMUnavailableError,
    OpenAIReplyGenerator,
    degrade_llm_output,
    parse_llm_output,
)
from app.store import DbStore


def _settings() -> BusinessSettings:
    return BusinessSettings(
        business_name="Test Cafe",
        business_type="Restaurant",
        description="Warm soup and quiet corners.",
        brand_voice="funny and warm",
    )


def _review() -> Review:
    return Review(
        author_name="Ann Lee",
        review_text="Great espresso but service was a bit slow today.",
        rating=4,
        source=ReviewSource.manual,
    )


def test_prompt_composition_includes_profile_and_constraints():
    prompt = compose_system_prompt(_settings())
    assert "Test Cafe" in prompt
    assert "funny and warm" in prompt
    assert "1-3 sentences" in prompt
    assert "under 500" in prompt


def test_user_prompt_includes_review_and_instructions():
    review = _review()
    plain = compose_user_prompt(review)
    assert "Ann Lee" in plain
    assert "Great espresso" in plain
    steered = compose_user_prompt(review, "offer a free cookie")
    assert "free cookie" in steered


def test_user_prompt_includes_existing_draft_on_regenerate():
    review = _review()
    review.reply_text = "Old draft reply text here."
    assert "Old draft" in compose_user_prompt(review, None)


def test_graceful_degradation_coerces_bad_metadata():
    out = parse_llm_output(
        {
            "reply_text": "Thank you, this valid reply is long enough.",
            "detected_sentiment": "angry_and_not_in_enum",
            "detected_tags": None,
        }
    )
    assert out.detected_sentiment is None
    assert out.detected_tags == []


def test_degrade_keeps_valid_reply_text():
    out = degrade_llm_output(
        {"reply_text": "Thank you, valid reply long enough here.", "detected_tags": "oops"},
        "Fallback reply that is also long enough.",
    )
    assert out.reply_text.startswith("Thank you")
    assert out.detected_sentiment is None
    assert out.detected_tags == []


def test_llm_down_without_key_returns_500(client):
    store: DbStore = client.app.state.store
    store._generator = OpenAIReplyGenerator(api_key=None)
    review_id = client.get("/api/reviews").json()[0]["id"]
    res = client.post(f"/api/reviews/{review_id}/generate")
    assert res.status_code == 500


def test_llm_transport_failure_returns_500(client, monkeypatch):
    from app import services as svc
    from app.services import LLMUnavailableError

    def boom(*args, **kwargs):
        raise LLMUnavailableError("API connection failed")

    monkeypatch.setattr(svc.OpenAIReplyGenerator, "generate", boom)
    store: DbStore = client.app.state.store
    store._generator = OpenAIReplyGenerator(api_key="fake")
    review_id = client.get("/api/reviews").json()[0]["id"]
    res = client.post(f"/api/reviews/{review_id}/generate")
    assert res.status_code == 500


def test_openai_generator_without_key_raises_unavailable():
    gen = OpenAIReplyGenerator(api_key=None)
    try:
        gen.generate(_settings(), _review(), None)
    except LLMUnavailableError:
        pass
    else:
        raise AssertionError("expected LLMUnavailableError")


def test_llm_output_schema_rejects_short_reply():
    try:
        LLMStructuredOutput(reply_text="short", detected_sentiment=None, detected_tags=[])
    except Exception:
        pass
    else:
        raise AssertionError("expected validation error for short reply")
