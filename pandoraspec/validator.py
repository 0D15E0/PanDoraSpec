import os

import yaml
from rich.console import Console

console = Console()

class ValidationError(Exception):
    pass

def validate_config(config_path: str) -> bool:
    """
    Validates a PanDoraSpec configuration file.
    Returns True if valid, raises ValidationError if invalid.
    """
    if not os.path.exists(config_path):
        raise ValidationError(f"Config file not found: {config_path}")

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValidationError(f"Invalid YAML syntax: {e}")

    if not isinstance(config, dict):
        raise ValidationError("Config must be a dictionary.")

    # Required fields
    # actually, strictly speaking, CLI args can override these,
    # but a defined config usually implies intent to define them.
    # We will warn if missing, but maybe not fail if the user intends to supply them via CLI.
    # However, 'seed_data' is the main reason for a config file.

    issues = []

    if "target" not in config:
        issues.append("Missing 'target' field (OpenAPI URL).")

    if "vendor" not in config:
        issues.append("Missing 'vendor' field.")

    # Validate seed_data structure if present
    if "seed_data" in config:
        seed_data = config["seed_data"]
        if not isinstance(seed_data, dict):
            issues.append("'seed_data' must be a dictionary.")
        else:
            valid_sections = ["general", "verbs", "endpoints"]
            for key in seed_data:
                if key not in valid_sections:
                    issues.append(f"Unknown section in 'seed_data': '{key}'. Allowed: {valid_sections}")

    if issues:
        # We raise one error with all issues
        raise ValidationError("Configuration issues found:\n- " + "\n- ".join(issues))

    console.print(f"[bold green]✓ Configuration '{config_path}' is valid.[/bold green]")
    return True
