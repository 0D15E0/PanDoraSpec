from unittest.mock import MagicMock, patch
from pandoraspec.modules.drift import run_drift_check

class TestDriftCheck:
    @patch("pandoraspec.modules.drift.checks.not_a_server_error")
    @patch("pandoraspec.modules.drift.oai_checks.status_code_conformance")
    @patch("pandoraspec.modules.drift.oai_checks.response_schema_conformance")
    def test_drift_all_pass(self, mock_schema_conf, mock_status_conf, mock_server_err):
        # Setup Mocks: Checks just run without raising AssertionError
        mock_schema = MagicMock()
        mock_op = MagicMock()
        mock_op.ok.return_value = mock_op
        mock_schema.get_all_operations.return_value = [mock_op]
        
        mock_case = MagicMock()
        mock_case.call.return_value.status_code = 200
        mock_op.as_strategy().example.return_value = mock_case
        
        seed_manager = MagicMock()
        
        results = run_drift_check(mock_schema, "https://api.test", None, seed_manager)
        
        # 3 checks per operation * 1 operation = 3 results
        assert len(results) == 3
        assert all(r["status"] == "PASS" for r in results)

    @patch("pandoraspec.modules.drift.checks.not_a_server_error")
    @patch("pandoraspec.modules.drift.oai_checks.status_code_conformance")
    @patch("pandoraspec.modules.drift.oai_checks.response_schema_conformance")
    def test_drift_schema_fail(self, mock_schema_conf, mock_status_conf, mock_server_err):
        # Mock Schema Conformance Failure
        mock_schema_conf.side_effect = AssertionError("Schema mismatch")
        
        mock_schema = MagicMock()
        mock_op = MagicMock()
        mock_op.ok.return_value = mock_op
        mock_schema.get_all_operations.return_value = [mock_op]
        
        mock_case = MagicMock()
        mock_case.call.return_value = MagicMock(status_code=200, text="Body")
        mock_op.as_strategy().example.return_value = mock_case
        
        seed_manager = MagicMock()
        
        results = run_drift_check(mock_schema, "https://api.test", None, seed_manager)
        
        statuses = [r["status"] for r in results]
        assert "FAIL" in statuses
        assert "PASS" in statuses # Other checks passed
        
        fail_result = next(r for r in results if r["status"] == "FAIL")
        assert "Schema Drift Detected" in fail_result["issue"]
