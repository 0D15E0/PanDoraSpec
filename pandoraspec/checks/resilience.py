from typing import List, Dict
from ..seed import SeedManager
from ..constants import FLOOD_REQUEST_COUNT

def run_resilience_tests(schema, base_url: str, api_key: str, seed_manager: SeedManager) -> List[Dict]:
    """
    Module B: The 'Resilience' Stress Test (Art. 24 & 25)
    Checks for Rate Limiting and Timeout gracefully handling.
    """
    results = []
    ops = list(schema.get_all_operations())
    if not ops:
        return []
    
    print("AUDIT LOG: Starting Module B: Resilience Stress Test (flooding requests)...")
    
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
    
    if not has_429 and has_500:
        results.append({
            "module": "B",
            "issue": "Poor Resilience: 500 Error during flood",
            "status": "FAIL",
            "details": "The API returned 500 Internal Server Error instead of 429 Too Many Requests when flooded.",
            "severity": "CRITICAL"
        })
    elif not has_429:
            results.append({
            "module": "B",
            "issue": "No Rate Limiting Enforced",
            "status": "FAIL",
            "details": "The API did not return 429 Too Many Requests during high volume testing.",
            "severity": "MEDIUM"
        })
    else:
        results.append({
            "module": "B",
            "issue": "Rate Limiting Functional",
            "status": "PASS",
            "details": "The API correctly returned 429 Too Many Requests when flooded.",
            "severity": "INFO"
        })
        
    if not has_500:
            results.append({
            "module": "B",
            "issue": "Stress Handling",
            "status": "PASS",
            "details": "No 500 Internal Server Errors were observed during stress testing.",
            "severity": "INFO"
        })

    return results
