import re

import requests

from ..constants import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR, SECURITY_SCAN_LIMIT, SENSITIVE_PATH_KEYWORDS
from ..utils.http import build_auth_header
from ..utils.logger import logger


def _check_headers(base_url: str) -> list[dict]:
    """Check for recommended security headers on the base URL."""
    results = []
    try:
        response = requests.get(base_url, timeout=5)
        headers = response.headers

        required_headers = {
            "Strict-Transport-Security": "HSTS",
            "Content-Security-Policy": "CSP",
            "X-Content-Type-Options": "No-Sniff",
            "X-Frame-Options": "Clickjacking Protection",
        }

        missing = [name for header, name in required_headers.items() if header not in headers]

        if missing:
            results.append({
                "module": "C",
                "issue": "Missing Security Headers",
                "status": "FAIL",
                "details": f"Missing recommended headers: {', '.join(missing)}",
                "severity": "MEDIUM",
            })
        else:
            results.append({
                "module": "C",
                "issue": "Security Headers",
                "status": "PASS",
                "details": "All core security headers are present.",
                "severity": "INFO",
            })

    except Exception as e:
        logger.warning(f"Failed to check headers: {e}")

    return results


def _check_auth_enforcement(ops: list, base_url: str) -> list[dict]:
    """
    Check if endpoints are protected by default.
    Tries to access up to SECURITY_SCAN_LIMIT static GET endpoints without credentials.
    Fails if 200 OK is returned on a non-public path.
    """
    results = []
    simple_gets = [op for op in ops if op.method.upper() == "GET" and "{" not in op.path]
    targets = simple_gets[:SECURITY_SCAN_LIMIT]

    if not targets:
        return []

    public_keywords = ["health", "status", "ping", "login", "auth", "token", "sign", "doc", "openapi", "well-known"]

    failures = []
    for op in targets:
        url = f"{base_url.rstrip('/')}{op.path}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == HTTP_200_OK:
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
            "severity": "CRITICAL",
        })
    else:
        results.append({
            "module": "C",
            "issue": "Auth Enforcement",
            "status": "PASS",
            "details": f"Checked {len(targets)} endpoints; none returned {HTTP_200_OK} OK without credentials.",
            "severity": "INFO",
        })
    return results


def _check_injection(ops: list, base_url: str, api_key: str | None = None) -> list[dict]:
    """
    Basic probe for SQL injection and XSS reflection in query parameters.
    """
    results = []
    # Only probe simple GET endpoints (no path parameters to avoid 404s)
    targets = [op for op in ops if op.method.upper() == "GET" and "{" not in op.path][:SECURITY_SCAN_LIMIT]

    if not targets:
        return []

    headers = {"Authorization": build_auth_header(api_key)} if api_key else {}
    payloads = ["' OR '1'='1", "<script>alert(1)</script>"]

    injection_failures = []

    for op in targets:
        url = f"{base_url.rstrip('/')}{op.path}"
        for payload in payloads:
            try:
                params = {"q": payload, "id": payload, "search": payload}
                resp = requests.get(url, headers=headers, params=params, timeout=5)

                if resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR:
                    injection_failures.append(f"{op.path} (500 Error on injection)")
                if payload in resp.text:
                    injection_failures.append(f"{op.path} (Reflected XSS: payload found in response)")
            except Exception:
                pass

    unique_failures = list(set(injection_failures))
    if unique_failures:
        results.append({
            "module": "C",
            "issue": "Injection Vulnerabilities",
            "status": "FAIL",
            "details": f"Potential issues found: {', '.join(unique_failures)}",
            "severity": "HIGH",
        })
    else:
        results.append({
            "module": "C",
            "issue": "Basic Injection Check",
            "status": "PASS",
            "details": (
                f"No {HTTP_500_INTERNAL_SERVER_ERROR} errors or reflected payloads detected during basic probing."
            ),
            "severity": "INFO",
        })

    return results


def _check_data_leakage(
    ops: list,
    base_url: str,
    api_key: str | None = None,
    allowed_domains: list[str] | None = None,
) -> list[dict]:
    """
    Scans GET responses for PII and secrets (DLP check).
    """
    results = []
    allowed_domains = allowed_domains or []

    patterns = {
        "Email Address": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "US SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "Credit Card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
        "AWS Access Key": r"\bAKIA[0-9A-Z]{16}\b",
        "Private Key": r"-----BEGIN PRIVATE KEY-----",
        "IPv4 Address": r"\b(?!127\.0\.0\.1)(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
    }

    targets = [op for op in ops if op.method.upper() == "GET" and "{" not in op.path][:SECURITY_SCAN_LIMIT]

    if not targets:
        return []

    headers = {"Authorization": build_auth_header(api_key)} if api_key else {}
    leaks: dict[str, list[str]] = {}

    for op in targets:
        url = f"{base_url.rstrip('/')}{op.path}"
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if not resp.text:
                continue

            for name, pattern in patterns.items():
                matches = list(set(re.findall(pattern, resp.text)))
                if not matches:
                    continue

                # Apply email allowlist
                if name == "Email Address" and allowed_domains:
                    matches = [
                        m for m in matches
                        if not any(m.lower().endswith(f"@{d.lower()}") for d in allowed_domains)
                    ]
                    for m in set(re.findall(pattern, resp.text)) - set(matches):
                        logger.debug(f"DLP: Ignoring allowed email {m}")

                if matches:
                    leaks.setdefault(name, []).append(
                        f"{op.path} (Found: {', '.join(matches[:3])})"
                    )

        except Exception:
            pass

    if leaks:
        details = "; ".join(f"{name}: {', '.join(findings)}" for name, findings in leaks.items())
        results.append({
            "module": "C",
            "issue": "Data Leakage (DLP)",
            "status": "FAIL",
            "details": f"Potential PII/Secrets found in responses: {details}",
            "severity": "CRITICAL",
        })
    else:
        results.append({
            "module": "C",
            "issue": "Data Leakage Check",
            "status": "PASS",
            "details": f"Scanned {len(targets)} endpoints; no PII or secrets patterns matched.",
            "severity": "INFO",
        })

    return results


def run_security_hygiene(
    schema,
    base_url: str,
    api_key: str | None = None,
    allowed_domains: list[str] | None = None,
) -> list[dict]:
    """
    Module C: Security Hygiene Check
    Checks for TLS, auth leakage, headers, and basic vulnerabilities.
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
            "severity": "CRITICAL",
        })
    else:
        results.append({
            "module": "C",
            "issue": "Secure Connection (TLS)",
            "status": "PASS",
            "details": "The API uses HTTPS.",
            "severity": "INFO",
        })

    # Collect operations
    try:
        all_ops = list(schema.get_all_operations())
        ops = [op.ok() if hasattr(op, "ok") else op for op in all_ops]
    except Exception:
        ops = []

    # 1. Auth Leakage in URL paths
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
                "severity": "HIGH",
            })

    if not auth_leakage_found:
        results.append({
            "module": "C",
            "issue": "No Auth Leakage in URLs",
            "status": "PASS",
            "details": "No endpoints found with 'key' or 'token' in the path, suggesting safe header-based auth.",
            "severity": "INFO",
        })

    # Sub-checks only make sense when we have a resolvable base_url
    if base_url:
        results.extend(_check_headers(base_url))
        results.extend(_check_auth_enforcement(ops, base_url))
        results.extend(_check_injection(ops, base_url, api_key))
        results.extend(_check_data_leakage(ops, base_url, api_key, allowed_domains))

    return results
