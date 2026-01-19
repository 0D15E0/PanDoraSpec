from unittest.mock import MagicMock, patch
from pandoraspec.modules.resilience import run_resilience_tests
from pandoraspec.constants import (
    FLOOD_REQUEST_COUNT, 
    HTTP_200_OK, 
    HTTP_429_TOO_MANY_REQUESTS, 
    HTTP_500_INTERNAL_SERVER_ERROR
)

class TestResilienceCheck:
    @patch('pandoraspec.modules.resilience.time.sleep') # Mock sleep to be instant
    def test_resilience_pass_all(self, mock_sleep):
        seed_manager = MagicMock()
        mock_schema = MagicMock()
        mock_op = MagicMock()
        mock_op.ok.return_value = mock_op
        mock_schema.get_all_operations.return_value = [mock_op]
        
        mock_case = MagicMock()
        
        # Responses for flood
        # All 200 OK, Low latency (0.1s)
        resp_ok = MagicMock(status_code=HTTP_200_OK)
        resp_ok.elapsed.total_seconds.return_value = 0.1
        
        # Recovery Response (also OK)
        resp_rec = MagicMock(status_code=HTTP_200_OK)
        
        # Setup side effects
        # Flood + Recovery
        mock_case.call.side_effect = [resp_ok] * FLOOD_REQUEST_COUNT + [resp_rec]
        
        mock_op.as_strategy().example.return_value = mock_case

        results = run_resilience_tests(mock_schema, "http://api.test", None, seed_manager)
        
        statuses = {r["issue"]: r["status"] for r in results}
        
        # Assertions
        assert statuses["No Rate Limiting Enforced"] == "FAIL" # Since we returned 200s
        assert statuses["Stress Handling"] == "PASS"
        assert statuses["Performance Stability"] == "PASS" # 0.1s < 1.0s
        assert statuses["Self-Healing / Recovery"] == "PASS"

    @patch('pandoraspec.modules.resilience.time.sleep')
    def test_resilience_high_latency_and_recovery_fail(self, mock_sleep):
        seed_manager = MagicMock()
        mock_schema = MagicMock()
        mock_op = MagicMock()
        mock_op.ok.return_value = mock_op
        mock_schema.get_all_operations.return_value = [mock_op]
        
        mock_case = MagicMock()
        
        # Responses for flood: High Latency (2.0s)
        resp_slow = MagicMock(status_code=HTTP_200_OK)
        resp_slow.elapsed.total_seconds.return_value = 2.0
        
        # Recovery Response: 500 Error
        resp_crash = MagicMock(status_code=HTTP_500_INTERNAL_SERVER_ERROR)
        
        mock_case.call.side_effect = [resp_slow] * FLOOD_REQUEST_COUNT + [resp_crash]
        mock_op.as_strategy().example.return_value = mock_case

        results = run_resilience_tests(mock_schema, "http://api.test", None, seed_manager)
        
        statuses = {r["issue"]: r["status"] for r in results}
        
        assert statuses["Performance Degradation"] == "FAIL"
        assert statuses["Recovery Failure"] == "FAIL"

    @patch('pandoraspec.modules.resilience.time.sleep')
    def test_resilience_rate_limit_pass(self, mock_sleep):
        seed_manager = MagicMock()
        mock_schema = MagicMock()
        mock_op = MagicMock()
        mock_op.ok.return_value = mock_op
        mock_schema.get_all_operations.return_value = [mock_op]
        
        mock_case = MagicMock()
        
        # Mix of 200 and 429
        resp_429 = MagicMock(status_code=HTTP_429_TOO_MANY_REQUESTS)
        resp_429.elapsed.total_seconds.return_value = 0.1
        
        mock_case.call.return_value = resp_429 # Just return 429s for simplicity
        mock_op.as_strategy().example.return_value = mock_case

        results = run_resilience_tests(mock_schema, "http://api.test", None, seed_manager)
        
        statuses = {r["issue"]: r["status"] for r in results}
        
        assert statuses["Rate Limiting Functional"] == "PASS"
