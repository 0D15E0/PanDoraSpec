from unittest.mock import patch

import typer
from typer.testing import CliRunner

# We need to test the actual Typer app setup or run_audit
from pandoraspec.cli import run_audit

runner = CliRunner()

def test_cli_target_optional(tmp_path):
    # Setup dummy config
    config_file = tmp_path / "pandoraspec.yaml"
    with open(config_file, "w") as f:
        f.write("target: https://example.com\nvendor: TestVendor\n")

    # Create a test app wrapping the function to test invocation behavior
    app = typer.Typer()
    app.command()(run_audit)

    # Mock the internal logic so we don't start a scan
    with patch("pandoraspec.cli.run_dora_audit_logic") as mock_logic:
        mock_logic.return_value.seed_count = 0
        mock_logic.return_value.results = {"drift_check": [], "resilience": [], "security": []}
        mock_logic.return_value.report_path = "report.pdf"

        # 1. Run with NO target, but WITH config
        # Invocation: pandoraspec --config ...
        # Note: Typer treats --flags relative to arguments.
        result = runner.invoke(app, ["--config", str(config_file)])

        assert result.exit_code == 0
        # Verify target was passed as None to the function (Typer parsing check)
        # But wait, logic resolves it inside. We mock run_dora_audit_logic.
        # Check what arguments run_dora_audit_logic received.
        args, kwargs = mock_logic.call_args
        # target passed to cli function should be None
        # target passed to logic should include what?
        # CLI function calls run_dora_audit_logic(target=target, ...)
        # So target passed to logic SHOULD be None.
        assert kwargs['target'] is None
        assert kwargs['config_path'] == str(config_file)

        # 2. Run with target (Legacy)
        mock_logic.reset_mock()
        result = runner.invoke(app, ["https://legacy.com"])
        assert result.exit_code == 0
        args, kwargs = mock_logic.call_args
        assert kwargs['target'] == "https://legacy.com"
