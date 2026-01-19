from unittest.mock import MagicMock
from pandoraspec.checks.resilience import run_resilience_tests
from pandoraspec.constants import FLOOD_REQUEST_COUNT

class TestResilienceCheck:
    def test_resilience_pass_no_errors(self):
        seed_manager = MagicMock()
        mock_schema = MagicMock()
        mock_op = MagicMock()
        mock_op.ok.return_value = mock_op # Handle ok()
        mock_schema.get_all_operations.return_value = [mock_op]
        
        mock_case = MagicMock()
        mock_case.call.return_value.status_code = 200
        mock_op.as_strategy().example.return_value = mock_case

        results = run_resilience_tests(mock_schema, "http://api.test", None, seed_manager)
        
        # Expect FAIL (No Rate Limiting) and PASS (Stress Handling)
        statuses = {r["issue"]: r["status"] for r in results}
        assert statuses["No Rate Limiting Enforced"] == "FAIL"
        assert statuses["Stress Handling"] == "PASS"
        assert len(results) == 2

    def test_resilience_rate_limit_functional(self):
        seed_manager = MagicMock()
        mock_schema = MagicMock()
        mock_op = MagicMock()
        mock_op.ok.return_value = mock_op
        mock_schema.get_all_operations.return_value = [mock_op]
        
        mock_case = MagicMock()
        # Mix of 200 and 429
        mock_case.call.side_effect = [MagicMock(status_code=200)] * 5 + [MagicMock(status_code=429)] * (FLOOD_REQUEST_COUNT - 5)
        mock_op.as_strategy().example.return_value = mock_case

        results = run_resilience_tests(mock_schema, "http://api.test", None, seed_manager)
        
        statuses = {r["issue"]: r["status"] for r in results}
        assert statuses["Rate Limiting Functional"] == "PASS"
        assert statuses["Stress Handling"] == "PASS"

    def test_resilience_fail_500(self):
        seed_manager = MagicMock()
        mock_schema = MagicMock()
        mock_op = MagicMock()
        mock_op.ok.return_value = mock_op
        mock_schema.get_all_operations.return_value = [mock_op]
        
        mock_case = MagicMock()
        # Mix of 200 and 500
        mock_case.call.side_effect = [MagicMock(status_code=200)] * 5 + [MagicMock(status_code=500)] * (FLOOD_REQUEST_COUNT - 5)
        mock_op.as_strategy().example.return_value = mock_case

        results = run_resilience_tests(mock_schema, "http://api.test", None, seed_manager)
        
        statuses = {r["issue"]: r["status"] for r in results}
        assert statuses["No Rate Limiting Enforced"] == "FAIL"
        assert statuses["Poor Resilience: 500 Error during flood"] == "FAIL"
