import os
import yaml
from unittest.mock import patch, MagicMock, ANY
from pandoraspec.orchestrator import run_dora_audit_logic

def test_config_precedence(tmp_path):
    # Setup config file
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "target": "http://config-target.com",
        "vendor": "ConfigVendor",
        "api_key": "config-key"
    }
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
        
    # Mock Engine to avoid running real audit
    with patch("pandoraspec.orchestrator.AuditEngine") as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.run_full_audit.return_value = {"drift": [], "resilience": [], "security": []}
        
        # Mock Report Generator to avoid file IO
        with patch("pandoraspec.orchestrator.generate_report") as mock_report:
            mock_report.return_value = "report.pdf"
            
            # Case 1: Config Only
            run_dora_audit_logic(
                target=None, 
                vendor=None,
                api_key=None,
                config_path=str(config_file)
            )
            # Check Engine was initialized with Config values
            args, kwargs = MockEngine.call_args
            assert kwargs['target'] == "http://config-target.com"
            assert kwargs['api_key'] == "config-key"
            # Check Report used Config Vendor
            mock_report.assert_called_with("ConfigVendor", ANY, output_path=None)
            
            # Reset checks
            MockEngine.reset_mock()
            mock_report.reset_mock()
            
            # Case 2: CLI Overrides
            run_dora_audit_logic(
                target="http://cli-target.com",
                vendor="CLIVendor",
                api_key="cli-key",
                config_path=str(config_file)
            )
            args, kwargs = MockEngine.call_args
            assert kwargs['target'] == "http://cli-target.com"
            assert kwargs['api_key'] == "cli-key"
            mock_report.assert_called_with("CLIVendor", ANY, output_path=None)
            
            # Reset checks
            MockEngine.reset_mock()
            
            # Case 3: CLI + Default (No Config)
            run_dora_audit_logic(
                target="http://cli-target.com",
                vendor=None, # Should fallback to "Vendor" default
                api_key=None,
                config_path=None
            )
            args, kwargs = MockEngine.call_args
            assert kwargs['target'] == "http://cli-target.com"
            mock_report.assert_called_with("Vendor", ANY, output_path=None)
