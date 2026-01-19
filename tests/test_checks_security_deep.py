import responses
from pandoraspec.modules.security import run_security_hygiene
from pandoraspec.constants import HTTP_200_OK, HTTP_401_UNAUTHORIZED, HTTP_500_INTERNAL_SERVER_ERROR

class MockOp:
    def __init__(self, path, method="GET"):
        self.path = path
        self.method = method
    
    def ok(self):
        return self

class MockSchema:
    def get_all_operations(self):
        return [MockOp("/users"), MockOp("/users/{id}"), MockOp("/login")]

@responses.activate
def test_security_headers_missing_and_auth_fail():
    base_url = "https://api.test"
    
    # 1. Base URL Head check - returns 200 but NO headers
    responses.add(responses.GET, base_url, json={}, headers={}, status=HTTP_200_OK)
    
    # 2. Auth Check: Accessing /users returns 200 (FAIL)
    responses.add(responses.GET, base_url + "/users", status=HTTP_200_OK)
    
    # Validation: /login returning 200 should NOT fail
    responses.add(responses.GET, base_url + "/login", status=HTTP_200_OK)

    # 3. Injection Check: Accessing /users returns 200 (PASS)
    responses.add(responses.GET, base_url + "/users", status=HTTP_200_OK)

    schema = MockSchema()
    results = run_security_hygiene(schema, base_url, api_key="secret")
    
    issues = {r["issue"]: r["status"] for r in results}
    
    # Should detect missing headers
    assert "Missing Security Headers" in issues
    assert issues["Missing Security Headers"] == "FAIL"
    
    # Should detect open auth
    assert "Auth Enforcement Failed" in issues
    assert issues["Auth Enforcement Failed"] == "FAIL"

@responses.activate
def test_security_headers_pass_and_auth_pass():
    base_url = "https://api.test"
    secure_headers = {
        "Strict-Transport-Security": "max-age=31536000",
        "Content-Security-Policy": "default-src 'self'",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY"
    }
    # 1. Base URL has headers
    responses.add(responses.GET, base_url, json={}, headers=secure_headers, status=200)
    
    # 2. Auth Check: Accessing /users returns 401 (PASS)
    responses.add(responses.GET, base_url + "/users", status=401)
    
    # 3. Injection Check: Returns 401 or 400 (anything but 500) -> PASS
    responses.add(responses.GET, base_url + "/users", status=401)

    schema = MockSchema()
    results = run_security_hygiene(schema, base_url, api_key="secret")
    
    issues = {r["issue"]: r["status"] for r in results}
    
    assert issues["Security Headers"] == "PASS"
    assert issues["Auth Enforcement"] == "PASS"

@responses.activate
def test_injection_fail_500():
    base_url = "https://api.test"
    # Headers pass
    responses.add(responses.GET, base_url, headers={"Strict-Transport-Security": "yes"}, status=200)
    # Auth pass
    responses.add(responses.GET, base_url + "/users", status=401)
    
    # Injection: Accessing /users (which matches the url checking logic) returns 500
    # Note: The code calls /users with params. responses matches path by default.
    responses.add(responses.GET, base_url + "/users", status=500)

    schema = MockSchema()
    results = run_security_hygiene(schema, base_url, api_key="secret")
    
    issues = {r["issue"]: r["status"] for r in results}
    
    assert "Injection Vulnerabilities" in issues
    assert issues["Injection Vulnerabilities"] == "FAIL"
