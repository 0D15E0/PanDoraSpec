import responses
import re
from pandoraspec.modules.security import _check_data_leakage
from collections import namedtuple

# Mocking a schemathesis-like operation object
Operation = namedtuple("Operation", ["method", "path"])

@responses.activate
def test_dlp_detection():
    base_url = "http://example.com"
    ops = [Operation(method="GET", path="/leaky_endpoint")]

    # Mock response with sensitive data
    responses.add(
        responses.GET,
        "http://example.com/leaky_endpoint",
        body="Here is a user email: user@example.com and an AWS Key: AKIAIOSFODNN7EXAMPLE",
        status=200
    )

    results = _check_data_leakage(ops, base_url)

    assert len(results) == 1
    issue = results[0]
    
    assert issue["module"] == "C"
    assert issue["issue"] == "Data Leakage (DLP)"
    assert issue["status"] == "FAIL"
    assert issue["severity"] == "CRITICAL"
    
    details = issue["details"]
    assert "Email Address" in details
    assert "user@example.com" in details
    assert "AWS Access Key" in details
    assert "AKIAIOSFODNN7EXAMPLE" in details

@responses.activate
def test_dlp_no_leak():
    base_url = "http://example.com"
    ops = [Operation(method="GET", path="/safe_endpoint")]

    responses.add(
        responses.GET,
        "http://example.com/safe_endpoint",
        body="Nothing to see here.",
        status=200
    )

    results = _check_data_leakage(ops, base_url)

    assert len(results) == 1
    assert results[0]["status"] == "PASS"
    assert "no PII or secrets" in results[0]["details"]
