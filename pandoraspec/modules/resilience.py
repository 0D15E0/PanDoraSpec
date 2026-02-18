import time

from ..constants import (
    FLOOD_REQUEST_COUNT,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
    LATENCY_THRESHOLD_WARN,
    RECOVERY_WAIT_TIME,
)
from ..seed import SeedManager
from ..utils.http import build_auth_header
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

    auth_header_value = build_auth_header(api_key) if api_key else None

    # --- Flood Phase ---
    responses = []
    latencies = []

    for _ in range(FLOOD_REQUEST_COUNT):
        try:
            case = operation.as_strategy().example()
        except Exception:
            try:
                cases = list(operation.make_case())
                case = cases[0] if cases else None
            except Exception:
                case = None

        if not case:
            continue

        seed_manager.apply_seed_data(case)

        headers = {"Authorization": auth_header_value} if auth_header_value else {}

        try:
            resp = case.call(base_url=base_url, headers=headers)
            responses.append(resp)

            if hasattr(resp, "elapsed"):
                if hasattr(resp.elapsed, "total_seconds"):
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

    # --- Recovery Phase ---
    logger.info(f"Waiting {RECOVERY_WAIT_TIME}s for circuit breaker recovery check...")
    time.sleep(RECOVERY_WAIT_TIME)

    recovery_failed = False
    try:
        try:
            recovery_case = operation.as_strategy().example()
        except Exception:
            cases = list(operation.make_case())
            recovery_case = cases[0] if cases else None

        if recovery_case:
            seed_manager.apply_seed_data(recovery_case)
            rec_headers = {"Authorization": auth_header_value} if auth_header_value else {}
            recovery_resp = recovery_case.call(base_url=base_url, headers=rec_headers)

            if recovery_resp.status_code == HTTP_500_INTERNAL_SERVER_ERROR:
                recovery_failed = True
    except Exception:
        # Connection error means the service is still down
        recovery_failed = True

    def _result(issue: str, status: str, details: str, severity: str) -> dict[str, str]:
        return {"module": "B", "issue": issue, "status": status, "details": details, "severity": severity}

    # 1. Rate Limiting
    if has_429:
        results.append(_result(
            "Rate Limiting Functional",
            "PASS",
            f"The API correctly returned {HTTP_429_TOO_MANY_REQUESTS} Too Many Requests when flooded.",
            "INFO",
        ))
    else:
        results.append(_result(
            "No Rate Limiting Enforced",
            "FAIL",
            f"The API did not return {HTTP_429_TOO_MANY_REQUESTS} Too Many Requests during high volume testing.",
            "MEDIUM",
        ))

    # 2. Stress Handling (500 Errors)
    if has_500:
        results.append(_result(
            "Poor Resilience: 500 Error during flood",
            "FAIL",
            f"The API returned {HTTP_500_INTERNAL_SERVER_ERROR} Internal Server Error instead of "
            f"{HTTP_429_TOO_MANY_REQUESTS} Too Many Requests when flooded.",
            "CRITICAL",
        ))
    else:
        results.append(_result(
            "Stress Handling",
            "PASS",
            f"No {HTTP_500_INTERNAL_SERVER_ERROR} Internal Server Errors were observed during stress testing.",
            "INFO",
        ))

    # 3. Latency
    if avg_latency > LATENCY_THRESHOLD_WARN:
        results.append(_result(
            "Performance Degradation",
            "FAIL",
            f"Average latency during stress was {avg_latency:.2f}s (Threshold: {LATENCY_THRESHOLD_WARN}s).",
            "WARNING",
        ))
    else:
        results.append(_result(
            "Performance Stability",
            "PASS",
            f"Average latency {avg_latency:.2f}s remained within acceptable limits.",
            "INFO",
        ))

    # 4. Recovery
    if recovery_failed:
        results.append(_result(
            "Recovery Failure",
            "FAIL",
            f"API failed to recover (returned {HTTP_500_INTERNAL_SERVER_ERROR} or crash) after {RECOVERY_WAIT_TIME}s cooldown.",
            "HIGH",
        ))
    else:
        results.append(_result(
            "Self-Healing / Recovery",
            "PASS",
            f"API successfully handled legitimate requests after {RECOVERY_WAIT_TIME}s cooldown.",
            "INFO",
        ))

    return results
