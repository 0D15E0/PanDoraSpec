from unittest.mock import MagicMock, patch
from pandoraspec.modules.drift import run_drift_check

class MockCause:
    def __init__(self, msg):
        self.message = msg

class MockAssertionError(AssertionError):
    def __init__(self, causes):
        self.causes = causes

def test_loose_datetime_check():
    seed_manager = MagicMock()
    mock_schema = MagicMock()
    mock_op = MagicMock()
    mock_op.ok.return_value = mock_op
    mock_op.method = "GET"
    mock_op.path = "/dates"
    mock_schema.get_all_operations.return_value = [mock_op]
    
    mock_case = MagicMock()
    mock_case.call.return_value.status_code = 200
    mock_op.as_strategy().example.return_value = mock_case

    # Mock schemathesis check to raise mismatch error
    # We patch the check map inside drift.py or just patch the functions it imports
    # Since run_drift_check imports checks from schemathesis, we patch those imports
    
    with patch("pandoraspec.modules.drift.oai_checks.response_schema_conformance") as mock_conf:
        # Simulate failure: '2023-10-10 10:00:00' is not a 'date-time'
        # This is a valid ISO string physically but fails strict jsonschema (no T/Z)
        
        err_msg = "'2023-10-10 10:00:00' is not a 'date-time'"
        mock_conf.side_effect = MockAssertionError([MockCause(err_msg)])
        
        results = run_drift_check(mock_schema, "http://api.test", None, seed_manager)
        
        # We expect 3 results (2 real ones passing, 1 mocked one passing loosely)
        # Find the one dealing with response schema
        schema_Result = next((r for r in results if "response_schema_conformance" in r["issue"]), None)
        assert schema_Result is not None
        
        # Should be PASS with INFO, because we ignored the stricter error
        assert schema_Result["status"] == "PASS"
        assert "Passed (Loose Validation)" in schema_Result["issue"]

def test_loose_datetime_check_still_fails_garbage():
    seed_manager = MagicMock()
    mock_schema = MagicMock()
    mock_op = MagicMock()
    mock_op.ok.return_value = mock_op
    mock_op.method = "GET"
    mock_op.path = "/dates"
    mock_schema.get_all_operations.return_value = [mock_op]
    
    mock_case = MagicMock()
    mock_case.call.return_value.status_code = 200
    mock_op.as_strategy().example.return_value = mock_case

    with patch("pandoraspec.modules.drift.oai_checks.response_schema_conformance") as mock_conf:
        # Garbage date
        err_msg = "'not-a-date' is not a 'date-time'"
        mock_conf.side_effect = MockAssertionError([MockCause(err_msg)])
        
        results = run_drift_check(mock_schema, "http://api.test", None, seed_manager)
        
        schema_result = next((r for r in results if "response_schema_conformance" in r["issue"]), None)
        assert schema_result is not None
        
        # Should be FAIL because 'not-a-date' is not parseable
        assert schema_result["status"] == "FAIL"
        assert "Schema Drift Detected" in schema_result["issue"]
