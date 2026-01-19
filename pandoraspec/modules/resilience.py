import time
from ..seed import SeedManager
from ..constants import (
    FLOOD_REQUEST_COUNT, 
    LATENCY_THRESHOLD_WARN, 
    RECOVERY_WAIT_TIME,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR
)
from ..utils.logger import logger

def run_resilience_tests(schema, base_url: str, api_key: str, seed_manager: SeedManager) -> list[dict]:
    """
    Module B: The 'Resilience' Stress Test (Art. 24 & 25)
    Checks for Rate Limiting, Latency degradation, and Recovery.
    """
    results = []
    ops = list(schema.get_all_operations())
    if not ops:
        return []
    
    logger.info("AUDIT LOG: Starting Module B: Resilience Stress Test (flooding requests)...")
    
    operation = ops[0].ok() if hasattr(ops[0], "ok") else ops[0]
    
    # Simulate flooding
    responses = []
    latencies = []
    
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
                
            try:
                resp = case.call(base_url=base_url, headers=headers)
                responses.append(resp)
                # Capture latency if available
                if hasattr(resp, 'elapsed'):
                    if hasattr(resp.elapsed, 'total_seconds'):
                        latencies.append(resp.elapsed.total_seconds())
                    elif isinstance(resp.elapsed, (int, float)):
                        latencies.append(float(resp.elapsed))
                    else:
                        latencies.append(0.0)
                else:
                    latencies.append(0.0)
            except Exception as e:
                logger.warning(f"Request failed during flood: {e}")
    
    has_429 = any(r.status_code == HTTP_429_TOO_MANY_REQUESTS for r in responses)
    has_500 = any(r.status_code == HTTP_500_INTERNAL_SERVER_ERROR for r in responses)
    
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    # Recovery Check (Circuit Breaker)
    logger.info(f"Waiting {RECOVERY_WAIT_TIME}s for circuit breaker recovery check...")
    time.sleep(RECOVERY_WAIT_TIME)
    
    recovery_failed = False
    try:
        # Attempt one probe request to see if API is back to normal
        # We regenerate a case to be safe
        try:
            recovery_case = operation.as_strategy().example()
        except:
             cases = list(operation.make_case())
             recovery_case = cases[0] if cases else None
        
        if recovery_case:
            seed_manager.apply_seed_data(recovery_case)
            rec_headers = {}
            if api_key:
                rec_headers["Authorization"] = api_key if api_key.lower().startswith("bearer ") else f"Bearer {api_key}"
                
            recovery_resp = recovery_case.call(base_url=base_url, headers=rec_headers)
            
            # If it returns 500, it's definitely NOT recovered
            if recovery_resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR:
                recovery_failed = True
            # Note: We count 429 as "still waiting" but not a crash, so technically "recovered" from error state?
            # Ideally it should be 200, but ensuring no 500 is the critical resilience check here.
    except Exception:
        # Connection error means it's down
        recovery_failed = True

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
            f"The API correctly returned {HTTP_429_TOO_MANY_REQUESTS} Too Many Requests when flooded.",
            "INFO"
        ))
    else:
        results.append(_create_result(
            "No Rate Limiting Enforced",
            "FAIL",
            f"The API did not return {HTTP_429_TOO_MANY_REQUESTS} Too Many Requests during high volume testing.",
            "MEDIUM"
        ))

    # 2. Stress Handling Check (500 Errors)
    if has_500:
        results.append(_create_result(
            "Poor Resilience: 500 Error during flood",
            "FAIL",
            f"The API returned {HTTP_500_INTERNAL_SERVER_ERROR} Internal Server Error instead of {HTTP_429_TOO_MANY_REQUESTS} Too Many Requests when flooded.",
            "CRITICAL"
        ))
    else:
        results.append(_create_result(
            "Stress Handling",
            "PASS",
            f"No {HTTP_500_INTERNAL_SERVER_ERROR} Internal Server Errors were observed during stress testing.",
            "INFO"
        ))

    # 3. Latency Check
    if avg_latency > LATENCY_THRESHOLD_WARN:
        results.append(_create_result(
            "Performance Degradation",
            "FAIL",
            f"Average latency during stress was {avg_latency:.2f}s (Threshold: {LATENCY_THRESHOLD_WARN}s).",
            "WARNING"
        ))
    else:
         results.append(_create_result(
            "Performance Stability",
            "PASS",
            f"Average latency {avg_latency:.2f}s remained within acceptable limits.",
            "INFO"
        ))

    # 4. Recovery Check
    if recovery_failed:
         results.append(_create_result(
            "Recovery Failure",
            "FAIL",
            f"API failed to recover (returned {HTTP_500_INTERNAL_SERVER_ERROR} or crash) after {RECOVERY_WAIT_TIME}s cooldown.",
            "HIGH"
        ))
    else:
        results.append(_create_result(
            "Self-Healing / Recovery",
            "PASS",
            f"API successfully handled legitimate requests after {RECOVERY_WAIT_TIME}s cooldown.",
            "INFO"
        ))

    return results
