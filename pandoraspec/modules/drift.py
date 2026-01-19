import html
from schemathesis import checks
from schemathesis.specs.openapi import checks as oai_checks
from schemathesis.checks import CheckContext, ChecksConfig
from urllib.parse import unquote
from ..seed import SeedManager
from ..utils.logger import logger

def run_drift_check(schema, base_url: str, api_key: str, seed_manager: SeedManager) -> list[dict]:
    """
    Module A: The 'Docs vs. Code' Drift Check (The Integrity Test)
    Uses schemathesis to verify if the API implementation matches the spec.
    """
    results = []
    # Mapping check names to actual functions
    check_map = {
        "not_a_server_error": checks.not_a_server_error,
        "status_code_conformance": oai_checks.status_code_conformance,
        "response_schema_conformance": oai_checks.response_schema_conformance
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
        # Handle Result type (Ok/Err) wrapping if present
        operation = op.ok() if hasattr(op, "ok") else op
        
        try:
            # Generate test case
            try:
                case = operation.as_strategy().example()
            except (AttributeError, Exception):
                try:
                    cases = list(operation.make_case())
                    case = cases[0] if cases else None
                except (AttributeError, Exception):
                    case = None
            
            if not case:
                continue

            seeded_keys = seed_manager.apply_seed_data(case) or set()

            formatted_path = operation.path
            if case.path_parameters:
                for key, value in case.path_parameters.items():
                        if key in seeded_keys:
                            display_value = unquote(str(value))
                        else:
                            display_value = "random"
                        
                        formatted_path = formatted_path.replace(f"{{{key}}}", f"{{{key}:{display_value}}}")
            
            logger.info(f"AUDIT LOG: Testing endpoint {operation.method.upper()} {formatted_path}")

            headers = {}
            if api_key:
                auth_header = api_key if api_key.lower().startswith("bearer ") else f"Bearer {api_key}"
                headers["Authorization"] = auth_header

            # Call the API
            target_url = f"{base_url.rstrip('/')}/{formatted_path.lstrip('/')}"
            logger.debug(f"AUDIT LOG: Calling {operation.method.upper()} {target_url}")
            
            response = case.call(base_url=base_url, headers=headers)
            logger.debug(f"AUDIT LOG: Response Status Code: {response.status_code}")
            
            # We manually call the check function to ensure arguments are passed correctly.
            for check_name in check_names:
                check_func = check_map[check_name]
                try:
                    # Direct call: check_func(ctx, response, case)
                    check_func(check_ctx, response, case)
                    
                    # If we get here, the check passed
                    results.append({
                        "module": "A",
                        "endpoint": f"{operation.method.upper()} {operation.path}",
                        "issue": f"{check_name} - Passed",
                        "status": "PASS",
                        "severity": "INFO",
                        "details": f"Status: {response.status_code}"
                    })

                except AssertionError as e:
                    # This catches actual drift (e.g., Schema validation failed)
                    # Capture and format detailed error info
                    validation_errors = []
                    
                    # Safely get causes if they exist and are iterable
                    causes = getattr(e, "causes", None)
                    if causes:
                        for cause in causes:
                            msg = cause.message if hasattr(cause, "message") else str(cause)
                            
                            # START: Loose DateTime Check
                            # If strict validation fails on date-time, try to be forgiving
                            if "is not a 'date-time'" in msg:
                                try:
                                    # Extract value from message: "'2023-10-25 12:00:00' is not a 'date-time'"
                                    val_str = msg.split("'")[1]
                                    from datetime import datetime
                                    # specific check for the common "Space instead of T" issue
                                    normalized = val_str.replace(" ", "T")
                                    # check for likely valid formats that jsonschema hates
                                    datetime.fromisoformat(normalized)
                                    # If we parsed it, it's a False Positive for our purposes (drift is minor)
                                    logger.info(f"AUDIT LOG: Ignoring strict date-time failure for plausible value: {val_str}")
                                    continue 
                                except Exception:
                                    pass
                            # END: Loose DateTime Check

                            validation_errors.append(msg)
                    
                    if not validation_errors:
                        # If we filtered everything out, consider it a PASS
                        if causes:
                             results.append({
                                "module": "A",
                                "endpoint": f"{operation.method.upper()} {operation.path}",
                                "issue": f"{check_name} - Passed (Loose Validation)",
                                "status": "PASS",
                                "severity": "INFO",
                                "details": f"Status: {response.status_code}. Ignored minor format mismatches."
                            })
                             continue

                        validation_errors.append(str(e) or "Validation failed")
                    
                    err_msg = "<br>".join(validation_errors)
                    safe_err = html.escape(err_msg)
                    
                    # Add helpful context (Status & Body Preview)
                    context_msg = f"Status: {response.status_code}"
                    try:
                        if response.content:
                            preview = response.text[:500]
                            safe_preview = html.escape(preview)
                            context_msg += f"<br>Response: {safe_preview}"
                    except Exception:
                        pass
                        
                    full_details = f"<strong>Error:</strong> {safe_err}<br><br><strong>Context:</strong><br>{context_msg}"

                    logger.warning(f"AUDIT LOG: Validation {check_name} failed: {err_msg}")
                    results.append({
                        "module": "A",
                        "endpoint": f"{operation.method.upper()} {operation.path}",
                        "issue": f"Schema Drift Detected ({check_name})",
                        "status": "FAIL",
                        "details": full_details,
                        "severity": "HIGH"
                    })
                except Exception as e:
                    # This catches unexpected coding errors
                    logger.error(f"AUDIT LOG: Error executing check {check_name}: {str(e)}")
                    results.append({
                        "module": "A",
                        "endpoint": f"{operation.method.upper()} {operation.path}",
                        "issue": f"Check Execution Error ({check_name})",
                        "status": "FAIL",
                        "details": str(e),
                        "severity": "HIGH"
                    })
                    
        except Exception as e:
            logger.critical(f"AUDIT LOG: Critical Error during endpoint test: {str(e)}")
            continue
            
    return results
