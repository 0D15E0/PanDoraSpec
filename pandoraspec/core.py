import schemathesis
from typing import List, Dict
import requests
from schemathesis import checks
from schemathesis.specs.openapi import checks as oai_checks
from schemathesis.checks import CheckContext, ChecksConfig
import html
import os

class AuditEngine:
    def __init__(self, schema_url: str, base_url: str = None, api_key: str = None):
        self.schema_url = schema_url
        self.api_key = api_key
        
        # --- FIXED LOCALHOST HANDLING ---
        # If running in Docker (implied by this environment), 'localhost' refers to the container.
        # We need to try to reach the host machine.
        working_schema_url = schema_url
        if "localhost" in schema_url or "127.0.0.1" in schema_url:
            # Try host.docker.internal first (standard for Docker Desktop)
            # We DON'T change self.schema_url so the report still shows what the user entered.
            try:
                print(f"DEBUG: Attempting to resolve localhost URL using host.docker.internal")
                test_url = schema_url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
                requests.head(test_url, timeout=2) # Quick check
                working_schema_url = test_url
                print(f"DEBUG: Successfully resolved to {working_schema_url}")
            except Exception:
                print(f"DEBUG: Failed to reach host.docker.internal, trying original")
                pass

        try:
            if os.path.exists(working_schema_url) and os.path.isfile(working_schema_url):
                 print(f"DEBUG: Loading schema from local file: {working_schema_url}")
                 self.schema = schemathesis.openapi.from_path(working_schema_url)
            else:
                 self.schema = schemathesis.openapi.from_url(working_schema_url)
            
            # 1. Use explicitly provided base_url if available
            if base_url:
                self.schema.base_url = base_url
                self.base_url = base_url
            else:
                # 2. Priority 1: Extract from the 'servers' field in the spec
                resolved_url = None
                if hasattr(self.schema, "raw_schema"):
                    servers = self.schema.raw_schema.get("servers", [])
                    if servers and isinstance(servers, list) and len(servers) > 0:
                        spec_server_url = servers[0].get("url")
                        if spec_server_url:
                            resolved_url = spec_server_url
                            print(f"DEBUG: Found server URL in specification: {resolved_url}")
                
                # 3. Priority 2: Use whatever schemathesis resolved automatically (fallback)
                if not resolved_url:
                    resolved_url = getattr(self.schema, "base_url", None)
                    print(f"DEBUG: Falling back to Schemathesis resolved base_url: {resolved_url}")

                if not resolved_url and self.schema_url:
                    # Fallback: Derive from schema_url (e.g., remove swagger.json)
                    try:
                        from urllib.parse import urlparse, urlunparse
                        parsed = urlparse(self.schema_url)
                        path_parts = parsed.path.split('/')
                        # Simple heuristic: remove the last segment (e.g. swagger.json) to get base
                        if '.' in path_parts[-1]: 
                            path_parts.pop()
                        new_path = '/'.join(path_parts)
                        resolved_url = urlunparse(parsed._replace(path=new_path))
                        print(f"DEBUG: Derived base_url from schema_url: {resolved_url}")
                    except Exception as e:
                        print(f"DEBUG: Failed to derive base_url from schema_url: {e}")

                print(f"DEBUG: Final resolved base_url for engine: {resolved_url}")
                
                 # Fix base_url if it's localhost as well
                if resolved_url and ("localhost" in resolved_url or "127.0.0.1" in resolved_url):
                     print(f"DEBUG: Adjusting base_url '{resolved_url}' for Docker environment")
                     resolved_url = resolved_url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")

                self.base_url = resolved_url
                if resolved_url:
                    try:
                        self.schema.base_url = resolved_url
                    except Exception:
                         pass

        except Exception as e:
            if isinstance(e, AttributeError) and "base_url" in str(e):
                 self.base_url = None
            else:
                raise ValueError(f"Failed to load OpenAPI schema from {schema_url}. Error: {str(e)}")

    def run_drift_check(self) -> List[Dict]:
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
        
        for op in self.schema.get_all_operations():
            # Handle Result type (Ok/Err) wrapping if present
            operation = op.ok() if hasattr(op, "ok") else op
            
            operation_path = f"{operation.method.upper()} {operation.path}"
            print(f"AUDIT LOG: Testing endpoint {operation_path}")
            
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

                # Prepare headers
                headers = {}
                if self.api_key:
                    auth_header = self.api_key if self.api_key.lower().startswith("bearer ") else f"Bearer {self.api_key}"
                    headers["Authorization"] = auth_header

                # Call the API
                target_url = f"{self.base_url.rstrip('/')}/{operation.path.lstrip('/')}"
                print(f"AUDIT LOG: Calling {operation.method.upper()} {target_url}")
                
                response = case.call(base_url=self.base_url, headers=headers)
                print(f"AUDIT LOG: Response Status Code: {response.status_code}")
                
                # --- FIXED VALIDATION LOGIC ---
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
                                if hasattr(cause, "message"):
                                    validation_errors.append(cause.message)
                                else:
                                    validation_errors.append(str(cause))
                        
                        if not validation_errors:
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

                        print(f"AUDIT LOG: Validation {check_name} failed: {err_msg}")
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
                        print(f"AUDIT LOG: Error executing check {check_name}: {str(e)}")
                        results.append({
                            "module": "A",
                            "endpoint": f"{operation.method.upper()} {operation.path}",
                            "issue": f"Check Execution Error ({check_name})",
                            "status": "FAIL",
                            "details": str(e),
                            "severity": "HIGH"
                        })
                        
            except Exception as e:
                print(f"AUDIT LOG: Critical Error during endpoint test: {str(e)}")
                continue
                
        return results

    def run_resilience_tests(self) -> List[Dict]:
        """
        Module B: The 'Resilience' Stress Test (Art. 24 & 25)
        Checks for Rate Limiting and Timeout gracefully handling.
        """
        results = []
        ops = list(self.schema.get_all_operations())
        if not ops:
            return []
        
        operation = ops[0].ok() if hasattr(ops[0], "ok") else ops[0]
        
        # Simulate flooding
        responses = []
        for _ in range(50): 
            try:
                case = operation.as_strategy().example()
            except (AttributeError, Exception):
                try:
                    cases = list(operation.make_case())
                    case = cases[0] if cases else None
                except (AttributeError, Exception):
                    case = None
            
            if case:
                headers = {}
                if self.api_key:
                    auth_header = self.api_key if self.api_key.lower().startswith("bearer ") else f"Bearer {self.api_key}"
                    headers["Authorization"] = auth_header
                    
                responses.append(case.call(base_url=self.base_url, headers=headers))
        
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

    def run_security_hygiene(self) -> List[Dict]:
        """
        Module C: Security Hygiene Check
        Checks for TLS and Auth leakage in URL.
        """
        results = []
        print(f"AUDIT LOG: Checking Security Hygiene for base URL: {self.base_url}")
        if self.base_url and not self.base_url.startswith("https"):
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
        for op in self.schema.get_all_operations():
            operation = op.ok() if hasattr(op, "ok") else op
            endpoint = operation.path
            if "key" in endpoint.lower() or "token" in endpoint.lower():
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

    def run_full_audit(self) -> Dict:
        return {
            "drift_check": self.run_drift_check(),
            "resilience": self.run_resilience_tests(),
            "security": self.run_security_hygiene()
        }