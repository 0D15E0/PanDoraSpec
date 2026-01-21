from typing import Any

from pydantic import BaseModel, Field, ValidationError

from .constants import DEFAULT_AI_MODEL
from .utils.logger import logger


class PandoraConfig(BaseModel):
    target: str | None = Field(None, description="Target URL or path to OpenAPI schema")
    vendor: str | None = Field(None, description="Vendor name for reports")
    api_key: str | None = Field(None, description="API Key for authenticated endpoints")
    dlp_allowed_domains: list[str] = Field(default_factory=list, description="List of domains to ignore in email leakage checks (e.g. company.com)")

    # AI Auditor Configuration
    openai_api_key: str | None = Field(None, description="OpenAI API Key for Module E")
    ai_model: str = Field(DEFAULT_AI_MODEL, description="Model to use for AI Assessment")

    seed_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Seed data for API testing. Keys can be parameter names or endpoint definitions (METHOD /path)."
    )

def validate_config(config_dict: dict[str, Any]) -> PandoraConfig:
    """
    Validates the configuration dictionary against the PandoraConfig schema.
    Raises ValidationError if invalid.
    """
    try:
        return PandoraConfig(**config_dict)
    except ValidationError as e:
        logger.error("Configuration validation failed!")
        for err in e.errors():
            loc = " -> ".join(str(part) for part in err['loc'])
            logger.error(f"  Field: {loc} | Error: {err['msg']}")
        raise e
