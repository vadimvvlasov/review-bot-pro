"""Central typed configuration (Pydantic v2 pydantic-settings).

Single source of truth for env loading, AI provider selection, and
network timeouts. Import the `settings` singleton; never hardcode keys.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === App ===
    app_name: str = "Review-Reply Bot"
    environment: Literal["development", "production", "test"] = "development"

    # === Database (Milestone 4; Milestone 3 keeps the in-memory store) ===
    database_url: str = Field("sqlite:///./reviews.db", validation_alias="DATABASE_URL")

    # === LLM pipeline ===
    llm_provider: Literal["mock", "groq", "ollama"] = Field("mock", validation_alias="LLM_PROVIDER")
    llm_timeout: float = Field(20.0, validation_alias="LLM_TIMEOUT")

    # === Groq (cloud, OpenAI-compatible) ===
    groq_api_key: str | None = Field(None, validation_alias="GROQ_API_KEY")
    groq_base_url: str = Field("https://api.groq.com/openai/v1", validation_alias="GROQ_BASE_URL")
    groq_model: str = Field("openai/gpt-oss-20b", validation_alias="GROQ_MODEL")

    # === Ollama (local) ===
    ollama_base_url: str = Field("http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_model: str = Field("llama3", validation_alias="OLLAMA_MODEL")

    @property
    def is_ai_enabled(self) -> bool:
        return self.llm_provider in ("groq", "ollama")


settings = Settings()
