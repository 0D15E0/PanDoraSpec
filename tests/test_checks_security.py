from unittest.mock import MagicMock
from pandoraspec.checks.security import run_security_hygiene

class TestSecurityCheck:
    def test_no_tls_fail(self):
        mock_schema = MagicMock()
        mock_schema.get_all_operations.return_value = []
        
        results = run_security_hygiene(mock_schema, "http://insecure.test")
        assert results[0]["issue"] == "Insecure Connection (No TLS)"
        assert results[0]["status"] == "FAIL"

    def test_tls_pass(self):
        mock_schema = MagicMock()
        mock_schema.get_all_operations.return_value = []
        
        results = run_security_hygiene(mock_schema, "https://secure.test")
        assert results[0]["issue"] == "Secure Connection (TLS)"
        assert results[0]["status"] == "PASS"

    def test_auth_leakage_fail(self):
        mock_schema = MagicMock()
        mock_op1 = MagicMock()
        mock_op1.ok.return_value = mock_op1
        mock_op1.path = "/users/{token}" # Leakage
        
        mock_op2 = MagicMock()
        mock_op2.ok.return_value = mock_op2
        mock_op2.path = "/users/safe"
        
        mock_schema.get_all_operations.return_value = [mock_op1, mock_op2]
        
        results = run_security_hygiene(mock_schema, "https://api.test")
        
        issues = [r["issue"] for r in results]
        assert "Auth Leakage Risk" in issues
        assert "No Auth Leakage in URLs" not in issues

    def test_auth_leakage_pass(self):
        mock_schema = MagicMock()
        mock_op1 = MagicMock()
        mock_op1.ok.return_value = mock_op1
        mock_op1.path = "/users/{id}"
        
        mock_schema.get_all_operations.return_value = [mock_op1]
        
        results = run_security_hygiene(mock_schema, "https://api.test")
        
        assert results[1]["issue"] == "No Auth Leakage in URLs"
        assert results[1]["status"] == "PASS"
