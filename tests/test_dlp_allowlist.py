import responses
from pandoraspec.modules.security import _check_data_leakage
from collections import namedtuple

# Mocking a schemathesis-like operation object
Operation = namedtuple("Operation", ["method", "path"])

@responses.activate
def test_dlp_allowlist():
    base_url = "http://example.com"
    ops = [Operation(method="GET", path="/support_info")]

    # Response with both allowed and disallowed emails
    # allowed: support@company.com
    # leakage: leaked.user@gmail.com
    responses.add(
        responses.GET,
        "http://example.com/support_info",
        body="Contact us at support@company.com or leaked.user@gmail.com",
        status=200
    )

    # 1. Without allowlist (Should catch both)
    # Note: Regex finds both. 
    results = _check_data_leakage(ops, base_url, allowed_domains=[])
    assert len(results) == 1
    assert results[0]["status"] == "FAIL"
    details = results[0]["details"]
    assert "support@company.com" in details
    assert "leaked.user@gmail.com" in details

    # 2. With allowlist (Should ignore support@company.com)
    results = _check_data_leakage(ops, base_url, allowed_domains=["company.com"])
    assert len(results) == 1
    assert results[0]["status"] == "FAIL"
    details = results[0]["details"]
    assert "support@company.com" not in details
    assert "leaked.user@gmail.com" in details

@responses.activate
def test_dlp_allowlist_full_ignore():
    base_url = "http://example.com"
    ops = [Operation(method="GET", path="/contact")]

    # Response with ONLY allowed email
    responses.add(
        responses.GET,
        "http://example.com/contact",
        body="Contact us at help@safe-domain.io",
        status=200
    )

    results = _check_data_leakage(ops, base_url, allowed_domains=["safe-domain.io"])
    
    # Should PASS because the only finding was allowed
    assert len(results) == 1
    assert results[0]["status"] == "PASS"
    assert "no PII or secrets" in results[0]["details"]
