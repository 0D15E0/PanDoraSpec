from ..seed import SeedManager
from ..constants import FLOOD_REQUEST_COUNT
from ..logger import logger

def run_resilience_tests(schema, base_url: str, api_key: str, seed_manager: SeedManager) -> list[dict]:
    """
    Module B: The 'Resilience' Stress Test (Art. 24 & 25)
    Checks for Rate Limiting and Timeout gracefully handling.
    """
    results = []
    ops = list(schema.get_all_operations())
    if not ops:
        return []
    
    logger.info("AUDIT LOG: Starting Module B: Resilience Stress Test (flooding requests)...")
    
    operation = ops[0].ok() if hasattr(ops[0], "ok") else ops[0]
    
    # Simulate flooding
    responses = []
    for _ in range(FLOOD_REQUEST_COUNT): 
        try:
            case = operation.as_strategy().example()
        except (AttributeError, Exception):
            try:
                cases = list(operation.make_case())
                case = cases[0] if cases else None
            except (AttributeError, Exception):
                case = None
        
        if case:
            seed_manager.apply_seed_data(case)

            headers = {}
            if api_key:
                auth_header = api_key if api_key.lower().startswith("bearer ") else f"Bearer {api_key}"
                headers["Authorization"] = auth_header
                
            responses.append(case.call(base_url=base_url, headers=headers))
    
    has_429 = any(r.status_code == 429 for r in responses)
    has_500 = any(r.status_code == 500 for r in responses)

    # Helper to create consistent result objects
    def _create_result(issue, status, details, severity):
        return {
            "module": "B",
            "issue": issue,
            "status": status,
            "details": details,
            "severity": severity
        }

    # 1. Rate Limiting Check
    if has_429:
         results.append(_create_result(
            "Rate Limiting Functional",
            "PASS",
            "The API correctly returned 429 Too Many Requests when flooded.",
            "INFO"
        ))
    else:
        results.append(_create_result(
            "No Rate Limiting Enforced",
            "FAIL",
            "The API did not return 429 Too Many Requests during high volume testing.",
            "MEDIUM"
        ))

    # 2. Stress Handling Check (500 Errors)
    if has_500:
        results.append(_create_result(
            "Poor Resilience: 500 Error during flood",
            "FAIL",
            "The API returned 500 Internal Server Error instead of 429 Too Many Requests when flooded.",
            "CRITICAL"
        ))
    else:
        results.append(_create_result(
            "Stress Handling",
            "PASS",
            "No 500 Internal Server Errors were observed during stress testing.",
            "INFO"
        ))

    return results
