from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
import typer
from pandoraspec.cli import run_audit
from pandoraspec.orchestrator import AuditRunResult

runner = CliRunner()
test_app = typer.Typer()
test_app.command()(run_audit)

@patch("pandoraspec.cli.run_dora_audit_logic")
def test_exit_code_on_success(mock_audit):
    # Mock a successful audit
    mock_audit.return_value = AuditRunResult(
        seed_count=0,
        results={
            "drift_check": [{"status": "PASS"}],
            "resilience": [{"status": "PASS"}],
            "security": [{"status": "PASS"}]
        },
        report_path="report.pdf"
    )

    result = runner.invoke(test_app, ["https://example.com/spec.json"])
    assert result.exit_code == 0

@patch("pandoraspec.cli.run_dora_audit_logic")
def test_exit_code_on_failure(mock_audit):
    # Mock a failed audit
    mock_audit.return_value = AuditRunResult(
        seed_count=0,
        results={
            "drift_check": [{"status": "FAIL"}], # One failure
            "resilience": [{"status": "PASS"}],
            "security": [{"status": "PASS"}]
        },
        report_path="report.pdf"
    )

    result = runner.invoke(test_app, ["https://example.com/spec.json"])
    assert result.exit_code == 1
    assert "FAILURE" in result.stdout
