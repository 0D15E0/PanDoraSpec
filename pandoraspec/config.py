from pydantic import BaseModel, Field, ValidationError
from typing import Dict, Any
from .utils.logger import logger

class PandoraConfig(BaseModel):
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
