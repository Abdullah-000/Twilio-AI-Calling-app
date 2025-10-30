from functools import lru_cache
from typing import List, Optional

from pydantic import BaseSettings, Field, validator
from urllib.parse import urlparse, urlunparse


class Settings(BaseSettings):
    twilio_account_sid: str = Field(..., env="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(..., env="TWILIO_AUTH_TOKEN")
    twilio_caller_id: str = Field(..., env="TWILIO_CALLER_ID")
    public_base_url: str = Field(..., env="PUBLIC_BASE_URL")
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_realtime_model: str = Field("gpt-4o-realtime-preview-2024-12-17", env="OPENAI_REALTIME_MODEL")
    supported_voices: List[str] = Field(default_factory=lambda: ["alloy", "ember", "verse"])
    default_prompt: str = Field(
        default=(
            "You are a cheerful assistant that helps callers with scheduling demo calls. "
            "Gather their name, email, and a preferred callback time."
        )
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("public_base_url")
    def validate_public_url(cls, value: str) -> str:  # noqa: B902
        parsed = urlparse(value)

        if parsed.scheme != "https":
            raise ValueError(
                "PUBLIC_BASE_URL must start with https:// so Twilio can establish a secure "
                "websocket (wss://) connection."
            )

        normalized_path = parsed.path.rstrip("/")
        normalized_url = urlunparse((parsed.scheme, parsed.netloc, normalized_path, "", "", ""))
        return normalized_url

    @validator("supported_voices", pre=True)
    def parse_supported_voices(cls, value):  # noqa: B902, ANN001
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def build_public_url(
        self, path: str, *, scheme: Optional[str] = None, query: str = ""
    ) -> str:
        """Construct a fully-qualified URL rooted at the configured public base."""

        parsed = urlparse(self.public_base_url)
        normalized_path = parsed.path.rstrip("/")
        target_path = path if path.startswith("/") else f"/{path}"
        combined_path = f"{normalized_path}{target_path}"

        return urlunparse((scheme or parsed.scheme, parsed.netloc, combined_path, "", query, ""))


@lru_cache()
def get_settings() -> Settings:
    return Settings()
