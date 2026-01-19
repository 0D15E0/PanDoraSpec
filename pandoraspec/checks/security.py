from ..constants import SENSITIVE_PATH_KEYWORDS
from ..logger import logger

def run_security_hygiene(schema, base_url: str) -> list[dict]:
    """
    Module C: Security Hygiene Check
    Checks for TLS and Auth leakage in URL.
    """
    results = []
    logger.info(f"AUDIT LOG: Checking Security Hygiene for base URL: {base_url}")
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
    
    auth_leakage_found = False
    for op in schema.get_all_operations():
        operation = op.ok() if hasattr(op, "ok") else op
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
    
    return results
