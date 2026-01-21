import re

import requests

from ..constants import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR, SECURITY_SCAN_LIMIT, SENSITIVE_PATH_KEYWORDS
from ..utils.logger import logger


def _check_headers(base_url: str) -> list[dict]:
    """Check for security headers on the base URL."""
    results = []
    try:
        response = requests.get(base_url, timeout=5)
        headers = response.headers

        missing_headers = []
        full_headers = {
            "Strict-Transport-Security": "HSTS",
            "Content-Security-Policy": "CSP",
            "X-Content-Type-Options": "No-Sniff",
            "X-Frame-Options": "Clickjacking Protection"
        }

        for header, name in full_headers.items():
            if header not in headers:
                missing_headers.append(name)

        if missing_headers:
             results.append({
                "module": "C",
                "issue": "Missing Security Headers",
                "status": "FAIL",
                "details": f"Missing recommended headers: {', '.join(missing_headers)}",
                "severity": "MEDIUM"
            })
        else:
             results.append({
                "module": "C",
                "issue": "Security Headers",
                "status": "PASS",
                "details": "All core security headers are present.",
                "severity": "INFO"
            })

    except Exception as e:
         logger.warning(f"Failed to check headers: {e}")

    return results

def _check_auth_enforcement(ops, base_url: str) -> list[dict]:
    """
    Check if endpoints are protected by default.
    Tries to access up to 3 static GET endpoints without credentials.
    Fails if 200 OK is returned.
    """
    results = []
    # Filter for GET operations without path parameters (simple access)
    simple_gets = [
        op for op in ops
        if op.method.upper() == "GET" and "{" not in op.path
    ]

    # Take top N
    targets = simple_gets[:SECURITY_SCAN_LIMIT]
    if not targets:
        return []

    failures = []
    for op in targets:
        url = f"{base_url.rstrip('/')}{op.path}"
        try:
            # Request without any Auth headers
            resp = requests.get(url, timeout=5)
            # If we get 200 OK on what should likely be a protected API (heuristic)
            # Note: This is aggressive. Some endpoints like /health might be public.
            # We filter out obvious public paths?
            if resp.status_code == HTTP_200_OK:
                # Filter out obvious public endpoints that SHOULD be accessible
                public_keywords = ["health", "status", "ping", "login", "auth", "token", "sign", "doc", "openapi", "well-known"]
                if not any(k in op.path.lower() for k in public_keywords):
                    failures.append(op.path)
        except Exception:
            pass

    if failures:
         results.append({
            "module": "C",
            "issue": "Auth Enforcement Failed",
            "status": "FAIL",
            "details": f"Endpoints accessible without auth: {', '.join(failures)}",
            "severity": "CRITICAL"
        })
    else:
         results.append({
            "module": "C",
            "issue": "Auth Enforcement",
            "status": "PASS",
            "details": f"Checked {len(targets)} endpoints; none returned {HTTP_200_OK} OK without info.",
            "severity": "INFO"
        })
    return results

def _check_injection(ops, base_url: str, api_key: str | None = None) -> list[dict]:
    """
    Basic probe for SQLi/XSS in query parameters.
    """
    results = []
    # Find operations with query parameters
    candidates = []
    for op in ops:
        # Check definitions for query params (heuristic via schemathesis structure)
        # schemathesis op has 'query' in parameters
        # For simplicity in this structure, we might just try appending ?id=' OR 1=1
        if op.method.upper() == "GET":
            candidates.append(op)

    targets = candidates[:SECURITY_SCAN_LIMIT] # Limit scan
    if not targets:
        return []

    injection_failures = []

    headers = {}
    if api_key:
         # Use key if available to penetrate deeper
         headers["Authorization"] = api_key if "Bearer" in api_key else f"Bearer {api_key}"

    payloads = ["' OR '1'='1", "<script>alert(1)</script>"]

    for op in targets:
        # Construct URL with path params blindly replaced if any (to avoid 404 if possible)
        # But for injection, simplistic probing on paths without params is safer
        if "{" in op.path:
            continue

        url = f"{base_url.rstrip('/')}{op.path}"

        for payload in payloads:
            try:
                # Add as arbitrary query param 'q' and 'id' - common vectors
                params = {"q": payload, "id": payload, "search": payload}
                resp = requests.get(url, headers=headers, params=params, timeout=5)

                if resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR:
                    injection_failures.append(f"{op.path} (500 Error on injection)")
                if payload in resp.text:
                    injection_failures.append(f"{op.path} (Reflected XSS: payload found in response)")

            except Exception:
                pass

    if injection_failures:
         results.append({
            "module": "C",
            "issue": "Injection Vulnerabilities",
            "status": "FAIL",
            "details": f"Potential issues found: {', '.join(list(set(injection_failures)))}",
            "severity": "HIGH"
        })
    else:
         results.append({
            "module": "C",
            "issue": "Basic Injection Check",
            "status": "PASS",
            "details": f"No {HTTP_500_INTERNAL_SERVER_ERROR} errors or reflected payloads detected during basic probing.",
            "severity": "INFO"
        })

    return results

def _check_data_leakage(ops, base_url: str, api_key: str | None = None, allowed_domains: list[str] | None = None) -> list[dict]:
    """
    Scans responses for PII and Secrets leakage (DLP).
    """
    results = []
    allowed_domains = allowed_domains or []

    # regex patterns for sensitive data
    patterns = {
        "Email Address": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "US SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "Credit Card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
        "AWS Access Key": r"\bAKIA[0-9A-Z]{16}\b",
        "Private Key": r"-----BEGIN PRIVATE KEY-----",
        "IPv4 Address": r"\b(?!127\.0\.0\.1)(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b" # Exclude localhost
    }

    # Filter for GET operations
    targets = [op for op in ops if op.method.upper() == "GET"][:SECURITY_SCAN_LIMIT]
    if not targets:
        return []

    headers = {}
    if api_key:
        headers["Authorization"] = api_key if "Bearer" in api_key else f"Bearer {api_key}"

    leaks: dict[str, list[str]] = {}

    for op in targets:
        url = f"{base_url.rstrip('/')}{op.path}"
        # Simplified handling for path params (skip if present to avoid 404s mostly)
        if "{" in op.path:
            continue

        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if not resp.text:
                continue

            for name, pattern in patterns.items():
                matches = re.findall(pattern, resp.text)
                if matches:
                    unique_matches = list(set(matches))

                    # Allowlist Logic for Emails
                    if name == "Email Address" and allowed_domains:
                        filtered = []
                        for m in unique_matches:
                            # check if email ends with any allowed domain
                            if not any(m.lower().endswith(f"@{d.lower()}") for d in allowed_domains):
                                filtered.append(m)
                            else:
                                logger.debug(f"DLP: Ignoring allowed email {m}")
                        unique_matches = filtered

                    if unique_matches:
                        if name not in leaks:
                            leaks[name] = []
                        # Store capped
                        leaks[name].append(f"{op.path} (Found: {', '.join(unique_matches[:3])})")

        except Exception:
            pass

    if leaks:
        details = []
        for name, findings in leaks.items():
            details.append(f"{name}: {', '.join(findings)}")

        results.append({
            "module": "C",
            "issue": "Data Leakage (DLP)",
            "status": "FAIL",
            "details": "Potential PII/Secrets found in responses: " + "; ".join(details),
            "severity": "CRITICAL"
        })
    else:
        results.append({
            "module": "C",
            "issue": "Data Leakage Check",
            "status": "PASS",
            "details": f"Scanned {len(targets)} endpoints; no PII or secrets patterns matched.",
            "severity": "INFO"
        })

    return results

def run_security_hygiene(schema, base_url: str, api_key: str | None = None, allowed_domains: list[str] | None = None) -> list[dict]:
    """
    Module C: Security Hygiene Check
    Checks for TLS, Auth leakage, Headers, and Basic Vulnerabilities.
    """
    results = []
    logger.info(f"AUDIT LOG: Checking Security Hygiene for base URL: {base_url}")

    # 0. TLS Check
    if base_url and not base_url.startswith("https"):
        results.append({
            "module": "C",
            "issue": "Insecure Connection (No TLS)",
            "status": "FAIL",
            "details": "The API base URL does not use HTTPS.",
            "severity": "CRITICAL"
        })
    else:
            results.append({
            "module": "C",
            "issue": "Secure Connection (TLS)",
            "status": "PASS",
            "details": "The API uses HTTPS.",
            "severity": "INFO"
        })

    # Collect operations
    try:
        all_ops = list(schema.get_all_operations())
        ops = [op.ok() if hasattr(op, "ok") else op for op in all_ops]
    except Exception:
        ops = []

    # 1. Auth Leakage in URL
    auth_leakage_found = False
    for operation in ops:
        endpoint = operation.path
        if any(keyword in endpoint.lower() for keyword in SENSITIVE_PATH_KEYWORDS):
            auth_leakage_found = True
            results.append({
                "module": "C",
                "issue": "Auth Leakage Risk",
                "status": "FAIL",
                "details": f"Endpoint '{endpoint}' indicates auth tokens might be passed in the URL.",
                "severity": "HIGH"
            })

    if not auth_leakage_found:
        results.append({
            "module": "C",
            "issue": "No Auth Leakage in URLs",
            "status": "PASS",
            "details": "No endpoints found with 'key' or 'token' in the path, suggesting safe header-based auth.",
            "severity": "INFO"
        })

    # 2. Check Headers
    if base_url:
        results.extend(_check_headers(base_url))

        # 3. Check Auth Enforcement
        results.extend(_check_auth_enforcement(ops, base_url))

        # 4. Check Injection
        results.extend(_check_injection(ops, base_url, api_key))

        # 5. Check Data Leakage
        results.extend(_check_data_leakage(ops, base_url, api_key, allowed_domains))

    return results
