from pydantic import BaseModel, Field, ValidationError
from typing import Dict, Any, Optional, List
from .utils.logger import logger
from .constants import DEFAULT_AI_MODEL

class PandoraConfig(BaseModel):
    target: Optional[str] = Field(None, description="Target URL or path to OpenAPI schema")
    vendor: Optional[str] = Field(None, description="Vendor name for reports")
    api_key: Optional[str] = Field(None, description="API Key for authenticated endpoints")
    dlp_allowed_domains: List[str] = Field(default_factory=list, description="List of domains to ignore in email leakage checks (e.g. company.com)")
    
    # AI Auditor Configuration
    openai_api_key: Optional[str] = Field(None, description="OpenAI API Key for Module E")
    ai_model: str = Field(DEFAULT_AI_MODEL, description="Model to use for AI Assessment")

    seed_data: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Seed data for API testing. Keys can be parameter names or endpoint definitions (METHOD /path)."
    )

def validate_config(config_dict: Dict[str, Any]) -> PandoraConfig:
    """
    Validates the configuration dictionary against the PandoraConfig schema.
    Raises ValidationError if invalid.
    """
    try:
        return PandoraConfig(**config_dict)
    except ValidationError as e:
        logger.error("Configuration validation failed!")
        for err in e.errors():
            loc = " -> ".join(str(l) for l in err['loc'])
            logger.error(f"  Field: {loc} | Error: {err['msg']}")
        raise e
