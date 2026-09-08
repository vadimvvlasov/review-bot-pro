"""Groq AI pipeline tests with mocked transport (AC-09..AC-14).

No network calls: the OpenAI-compatible client is faked. Store/DB layers
are untouched; generation is injected via the in-memory store's generator.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.models import BusinessSettings, LLMStructuredOutput, Review, ReviewSource
from app.services import (
    GROQ_BASE_URL,
    GROQ_DEFAULT_MODEL,
    GroqReplyGenerator,
    GroqSettings,
    LLMUnavailableError,
    get_reply_generator,
)


def _settings() -> BusinessSettings:
    return BusinessSettings(
        business_name="Daily Grind Cafe",
        business_type="Coffee Shop",
        description="Cozy local cafe serving organic brews.",
        brand_voice="warm and welcoming",
    )


def _review() -> Review:
    return Review(
        author_name="Ann Lee",
        review_text="Great espresso but service was a bit slow today.",
        rating=4,
        source=ReviewSource.manual,
    )


def _completion(parsed=None, content=""):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed, content=content))])


def _client_with(completion=None, error=None):
    client = MagicMock()
    parse = client.beta.chat.completions.parse
    if error is not None:
        parse.side_effect = error
    else:
        parse.return_value = completion
    return client


def test_groq_defaults_use_expected_endpoint_and_model():
    gen = GroqReplyGenerator(api_key="test-key")
    assert gen.base_url == GROQ_BASE_URL
    assert gen.model == GROQ_DEFAULT_MODEL
    assert gen.timeout == 20.0


def test_groq_settings_read_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-key")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    cfg = GroqSettings()
    assert cfg.groq_api_key == "env-key"
    assert cfg.groq_model == "llama-3.3-70b-versatile"


def test_get_reply_generator_prefers_groq_when_configured(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "env-key")
    assert isinstance(get_reply_generator(), GroqReplyGenerator)


def test_atomic_structured_call_returns_all_fields():
    parsed = LLMStructuredOutput(reply_text="Thank you Ann, we appreciate the detailed feedback here.", detected_sentiment="positive", detected_tags=["service"])
    gen = GroqReplyGenerator(api_key="k")
    with patch("openai.OpenAI", return_value=_client_with(_completion(parsed))):
        out = gen.generate(_settings(), _review(), None)
    assert out.reply_text.startswith("Thank you")
    assert out.detected_sentiment and out.detected_sentiment.value == "positive"
    assert out.detected_tags == ["service"]
    assert 10 <= len(out.reply_text) <= 500


def test_single_call_passes_pydantic_model_as_response_format():
    parsed = LLMStructuredOutput(reply_text="Thank you Ann, we appreciate the detailed feedback here.", detected_sentiment="neutral", detected_tags=["coffee"])
    client = _client_with(_completion(parsed))
    gen = GroqReplyGenerator(api_key="k", model="llama-3.3-70b-versatile")
    with patch("openai.OpenAI", return_value=client) as factory:
        gen.generate(_settings(), _review(), "be brief")
    factory.assert_called_once_with(api_key="k", base_url=GROQ_BASE_URL, timeout=20.0)
    _, kwargs = client.beta.chat.completions.parse.call_args
    assert kwargs["response_format"] is LLMStructuredOutput
    assert kwargs["model"] == "llama-3.3-70b-versatile"


def test_graceful_degradation_keeps_reply_on_bad_metadata():
    raw = {"reply_text": "Thank you Ann, valid reply text long enough here.", "detected_sentiment": "ecstatic", "detected_tags": "not-a-list"}
    gen = GroqReplyGenerator(api_key="k")
    with patch("openai.OpenAI", return_value=_client_with(_completion(None, __import__("json").dumps(raw)))):
        out = gen.generate(_settings(), _review(), None)
    assert out.reply_text == raw["reply_text"]
    assert out.detected_sentiment is None
    assert out.detected_tags == []


def test_missing_key_raises_unavailable():
    with pytest.raises(LLMUnavailableError):
        GroqReplyGenerator(api_key=None).generate(_settings(), _review(), None)


@pytest.mark.parametrize("error", [TimeoutError("timed out"), ConnectionError("down"), Exception("HTTP 429 rate limited")])
def test_transport_failures_raise_unavailable(error):
    gen = GroqReplyGenerator(api_key="k")
    with patch("openai.OpenAI", return_value=_client_with(error=error)):
        with pytest.raises(LLMUnavailableError):
            gen.generate(_settings(), _review(), None)


def test_rate_limit_surfaces_as_http_500(client, monkeypatch):
    from app.services import GroqReplyGenerator as Groq

    def boom(*args, **kwargs):
        raise LLMUnavailableError("HTTP 429 rate limited")

    monkeypatch.setattr(Groq, "generate", boom)
    client.app.state.store._generator = Groq(api_key="fake")
    review_id = client.get("/api/reviews").json()[0]["id"]
    res = client.post(f"/api/reviews/{review_id}/generate")
    assert res.status_code == 500
    assert "message" in res.json()


def test_timeout_surfaces_as_http_500(client, monkeypatch):
    from app.services import GroqReplyGenerator as Groq

    def boom(*args, **kwargs):
        raise LLMUnavailableError("Groq request failed: timed out")

    monkeypatch.setattr(Groq, "generate", boom)
    client.app.state.store._generator = Groq(api_key="fake")
    review_id = client.get("/api/reviews").json()[0]["id"]
    assert client.post(f"/api/reviews/{review_id}/generate").status_code == 500
