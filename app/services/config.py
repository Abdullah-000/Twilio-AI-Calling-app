from functools import lru_cache
from typing import List

from pydantic import BaseSettings, Field, validator


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
        if value.endswith("/"):
            return value.rstrip("/")
        return value

    @validator("supported_voices", pre=True)
    def parse_supported_voices(cls, value):  # noqa: B902, ANN001
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache()
def get_settings() -> Settings:
    return Settings()
