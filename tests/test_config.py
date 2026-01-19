from pydantic import ValidationError
import pytest
from pandoraspec.config import validate_config, PandoraConfig

def test_valid_config():
    data = {"seed_data": {"user_id": 123}}
    config = validate_config(data)
    assert isinstance(config, PandoraConfig)
    assert config.seed_data == {"user_id": 123}

def test_empty_config():
    config = validate_config({})
    assert isinstance(config, PandoraConfig)
    assert config.seed_data == {}

def test_invalid_seed_data_type():
    data = {"seed_data": "not-a-dict"}
    with pytest.raises(ValidationError):
        validate_config(data)

def test_extra_fields_ignored_or_allowed():
    # Pydantic ignores extra fields by default unless configured otherwise
    data = {"seed_data": {}, "extra_field": "ignore me"}
    config = validate_config(data)
    assert isinstance(config, PandoraConfig)
    # Ensure extra fields didn't break it
