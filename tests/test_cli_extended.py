import yaml
from typer.testing import CliRunner

from pandoraspec.cli import app

runner = CliRunner()

def test_validate_command_valid_config(tmp_path):
    config_file = tmp_path / "valid_config.yaml"
    config_data = {
        "target": "https://example.com/spec.json",
        "vendor": "TestVendor"
    }
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    result = runner.invoke(app, ["validate", "--config", str(config_file)])
    assert result.exit_code == 0
    assert "Configuration" in result.stdout
    assert "is valid" in result.stdout

def test_validate_command_invalid_config(tmp_path):
    config_file = tmp_path / "invalid_config.yaml"
    config_data = {
        "target": "https://example.com/spec.json"
        # Missing vendor
    }
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    result = runner.invoke(app, ["validate", "--config", str(config_file)])
    assert result.exit_code == 1
    assert "Validation Failed" in result.stdout
    assert "Missing 'vendor' field" in result.stdout

def test_validate_command_missing_file():
    result = runner.invoke(app, ["validate", "--config", "non_existent.yaml"])
    assert result.exit_code == 1
    assert "Config file not found" in result.stdout

def test_init_command_help():
    # We can't easily test the interactive prompts using CliRunner without complex mocking,
    # but we can check if the help message works, verifying the command is registered.
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "Initialize a new configuration file" in result.stdout
