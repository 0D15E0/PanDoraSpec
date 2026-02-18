import html
from datetime import datetime
from urllib.parse import unquote

from schemathesis import checks
from schemathesis.checks import CheckContext, ChecksConfig
from schemathesis.specs.openapi import checks as oai_checks

from ..seed import SeedManager
from ..utils.http import build_auth_header
from ..utils.logger import logger


def run_drift_check(schema, base_url: str, api_key: str, seed_manager: SeedManager) -> list[dict]:
    """
    Module A: The 'Docs vs. Code' Drift Check (The Integrity Test)
    Uses schemathesis to verify if the API implementation matches the spec.
    """
    results = []

    check_map = {
        "not_a_server_error": checks.not_a_server_error,
        "status_code_conformance": oai_checks.status_code_conformance,
        "response_schema_conformance": oai_checks.response_schema_conformance,
    }
    check_names = list(check_map.keys())

    # Schemathesis 4.x checks require a context object
    checks_config = ChecksConfig()
    check_ctx = CheckContext(
        override=None,
        auth=None,
        headers=None,
        config=checks_config,
        transport_kwargs=None,
    )

    for op in schema.get_all_operations():
        operation = op.ok() if hasattr(op, "ok") else op

        try:
            # Generate a test case
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

            seeded_keys = seed_manager.apply_seed_data(case) or set()

            # Build a human-readable path for logging (seed values shown, random otherwise)
            formatted_path = operation.path
            if case.path_parameters:
                for key, value in case.path_parameters.items():
                    display_value = unquote(str(value)) if key in seeded_keys else "random"
                    formatted_path = formatted_path.replace(f"{{{key}}}", f"{{{key}:{display_value}}}")

            logger.info(f"AUDIT LOG: Testing endpoint {operation.method.upper()} {formatted_path}")

            headers = {}
            if api_key:
                headers["Authorization"] = build_auth_header(api_key)

            response = case.call(base_url=base_url, headers=headers)
            logger.debug(f"AUDIT LOG: Response Status Code: {response.status_code}")

            for check_name in check_names:
                check_func = check_map[check_name]
                try:
                    check_func(check_ctx, response, case)

                    results.append({
                        "module": "A",
                        "endpoint": f"{operation.method.upper()} {operation.path}",
                        "issue": f"{check_name} - Passed",
                        "status": "PASS",
                        "severity": "INFO",
                        "details": f"Status: {response.status_code}",
                    })

                except AssertionError as e:
                    validation_errors = []
                    causes = getattr(e, "causes", None)

                    if causes:
                        for cause in causes:
                            msg = cause.message if hasattr(cause, "message") else str(cause)

                            # Loose date-time check: treat space-separated ISO datetimes as valid
                            if "is not a 'date-time'" in msg:
                                try:
                                    val_str = msg.split("'")[1]
                                    normalized = val_str.replace(" ", "T")
                                    datetime.fromisoformat(normalized)
                                    logger.info(
                                        f"AUDIT LOG: Ignoring strict date-time failure for plausible value: {val_str}"
                                    )
                                    continue
                                except Exception:
                                    pass

                            validation_errors.append(msg)

                    if not validation_errors:
                        # All causes were filtered out — treat as a loose PASS
                        if causes:
                            results.append({
                                "module": "A",
                                "endpoint": f"{operation.method.upper()} {operation.path}",
                                "issue": f"{check_name} - Passed (Loose Validation)",
                                "status": "PASS",
                                "severity": "INFO",
                                "details": f"Status: {response.status_code}. Ignored minor format mismatches.",
                            })
                            continue
                        validation_errors.append(str(e) or "Validation failed")

                    err_msg = "<br>".join(validation_errors)
                    safe_err = html.escape(err_msg)

                    context_msg = f"Status: {response.status_code}"
                    try:
                        if response.content:
                            preview = response.text[:500]
                            context_msg += f"<br>Response: {html.escape(preview)}"
                    except Exception:
                        pass

                    full_details = (
                        f"<strong>Error:</strong> {safe_err}"
                        f"<br><br><strong>Context:</strong><br>{context_msg}"
                    )

                    logger.warning(f"AUDIT LOG: Validation {check_name} failed: {err_msg}")
                    results.append({
                        "module": "A",
                        "endpoint": f"{operation.method.upper()} {operation.path}",
                        "issue": f"Schema Drift Detected ({check_name})",
                        "status": "FAIL",
                        "details": full_details,
                        "severity": "HIGH",
                    })

                except Exception as e:
                    logger.error(f"AUDIT LOG: Error executing check {check_name}: {str(e)}")
                    results.append({
                        "module": "A",
                        "endpoint": f"{operation.method.upper()} {operation.path}",
                        "issue": f"Check Execution Error ({check_name})",
                        "status": "FAIL",
                        "details": str(e),
                        "severity": "HIGH",
                    })

        except Exception as e:
            logger.critical(f"AUDIT LOG: Critical Error during endpoint test: {str(e)}")
            continue

    return results
