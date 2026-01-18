import schemathesis
from typing import List, Dict, Any
import requests
import re
from schemathesis import checks
from schemathesis.specs.openapi import checks as oai_checks
from schemathesis.checks import CheckContext, ChecksConfig
import html
import os

class AuditEngine:
    def __init__(self, target: str, api_key: str = None, seed_data: Dict[str, Any] = None):
        self.target = target
        self.api_key = api_key
        self.seed_data = seed_data or {}
        self.base_url = None
        self.dynamic_cache = {} # Cache for dynamic seed values

        try:
            if os.path.exists(target) and os.path.isfile(target):
                 print(f"DEBUG: Loading schema from local file: {target}")
                 self.schema = schemathesis.openapi.from_path(target)
            else:
                 self.schema = schemathesis.openapi.from_url(target)
            
            # Priority 1: Extract from the 'servers' field in the spec
            resolved_url = None
            if hasattr(self.schema, "raw_schema"):
                servers = self.schema.raw_schema.get("servers", [])
                if servers and isinstance(servers, list) and len(servers) > 0:
                    spec_server_url = servers[0].get("url")
                    if spec_server_url:
                        resolved_url = spec_server_url
                        print(f"DEBUG: Found server URL in specification: {resolved_url}")
            
            # Priority 2: Use whatever schemathesis resolved automatically (fallback)
            if not resolved_url:
                resolved_url = getattr(self.schema, "base_url", None)
                print(f"DEBUG: Falling back to Schemathesis resolved base_url: {resolved_url}")

            if not resolved_url and self.target and not os.path.exists(self.target):
                # Fallback: Derive from target URL (e.g., remove swagger.json)
                try:
                    from urllib.parse import urlparse, urlunparse
                    parsed = urlparse(self.target)
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
            self.base_url = resolved_url
            if resolved_url:
                try:
                    self.schema.base_url = resolved_url
                except Exception:
                        pass
        except Exception as e:
             # Handle invalid URL or schema loading error gracefully
             print(f"Error loading schema: {e}")
             if target and (target.startswith("http") or os.path.exists(target)):
                pass # Allow to continue if it's just a warning, but schemathesis might fail later
             else:
                raise ValueError(f"Failed to load OpenAPI schema from {target}. Error: {str(e)}")

    def _resolve_dynamic_value(self, config_value: Any) -> Any:
        """Resolves dynamic seed values like `from_endpoint`"""
        if not isinstance(config_value, dict) or "from_endpoint" not in config_value:
            return config_value

        endpoint_def = config_value["from_endpoint"]
        if endpoint_def in self.dynamic_cache:
            return self.dynamic_cache[endpoint_def]

        try:
            method, path = endpoint_def.split(" ", 1)
            
            # Interpolate path parameters (e.g., /user/{id}) from general seeds
            if '{' in path:
                general_seeds = self.seed_data.get('general', {})
                
                def replace_param(match):
                    param_name = match.group(1)
                    if param_name in general_seeds:
                        return str(general_seeds[param_name])
                    print(f"WARNING: Missing seed value for {{{param_name}}} in dynamic endpoint {endpoint_def}")
                    return match.group(0) # Leave as is

                path = re.sub(r"\{([a-zA-Z0-9_]+)\}", replace_param, path)

            url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
            
            headers = {}
            if self.api_key:
                 auth_header = self.api_key if self.api_key.lower().startswith("bearer ") else f"Bearer {self.api_key}"
                 headers["Authorization"] = auth_header

            print(f"AUDIT LOG: Resolving dynamic seed from {method} {path}")
            response = requests.request(method, url, headers=headers)
            
            if response.status_code >= 400:
                print(f"WARNING: Dynamic seed request failed with {response.status_code}")
                return None

            result = None
            extract_key = config_value.get("extract")
            regex_pattern = config_value.get("regex")

            # JSON Extraction
            if extract_key:
                try:
                    json_data = response.json()
                    # Simple key traversal for now (e.g. 'data.id')
                    keys = extract_key.split('.')
                    val = json_data
                    for k in keys:
                        if isinstance(val, dict):
                            val = val.get(k)
                        else:
                            val = None
                            break
                    result = val
                except Exception:
                    print("WARNING: Failed to parse JSON or extract key")
            else:
                 # Default to text body
                 result = response.text

            # Regex Extraction
            if regex_pattern and result is not None:
                match = re.search(regex_pattern, str(result))
                if match:
                    # Return first group if exists, else the whole match
                    result = match.group(1) if match.groups() else match.group(0)
            
            self.dynamic_cache[endpoint_def] = result
            return result

        except Exception as e:
            print(f"ERROR: Failed to resolve dynamic seed: {e}")
            return None

    def _apply_seed_data(self, case):
        """Helper to inject seed data into test cases with hierarchy: General < Verbs < Endpoints"""
        if not self.seed_data:
            return

        # Determine if using hierarchical structure
        is_hierarchical = any(k in self.seed_data for k in ['general', 'verbs', 'endpoints'])
        
        if is_hierarchical:
            # 1. Start with General
            merged_data = self.seed_data.get('general', {}).copy()
            
            # 2. Apply Verb-specific
            if hasattr(case, 'operation'):
                method = case.operation.method.upper()
                path = case.operation.path
                
                verb_data = self.seed_data.get('verbs', {}).get(method, {})
                merged_data.update(verb_data)
                
                # 3. Apply Endpoint-specific
                # precise match on path template
                endpoint_data = self.seed_data.get('endpoints', {}).get(path, {}).get(method, {})
                merged_data.update(endpoint_data)
        else:
            # Legacy flat structure
            merged_data = self.seed_data.copy() # Copy to avoid mutating original config

        # Resolve dynamic values for the final merged dataset
        resolved_data = {}
        for k, v in merged_data.items():
            resolved_val = self._resolve_dynamic_value(v)
            if resolved_val is not None:
                resolved_data[k] = resolved_val

        # Inject into Path Parameters (e.g., /users/{userId})
        if hasattr(case, 'path_parameters') and case.path_parameters:
            for key in case.path_parameters:
                if key in resolved_data:
                    case.path_parameters[key] = resolved_data[key]

        # Inject into Query Parameters (e.g., ?status=active)
        if hasattr(case, 'query') and case.query:
            for key in case.query:
                if key in resolved_data:
                    case.query[key] = resolved_data[key]
                    
        # Inject into Headers (e.g., X-Tenant-ID)
        if hasattr(case, 'headers') and case.headers:
            for key in case.headers:
                if key in resolved_data:
                    case.headers[key] = str(resolved_data[key])

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

                self._apply_seed_data(case)

                formatted_path = operation.path
                if case.path_parameters:
                    for key, value in case.path_parameters.items():
                         formatted_path = formatted_path.replace(f"{{{key}}}", f"{{{key}:{value}}}")
                
                print(f"AUDIT LOG: Testing endpoint {operation.method.upper()} {formatted_path}")

                headers = {}
                if self.api_key:
                    auth_header = self.api_key if self.api_key.lower().startswith("bearer ") else f"Bearer {self.api_key}"
                    headers["Authorization"] = auth_header

                # Call the API
                target_url = f"{self.base_url.rstrip('/')}/{formatted_path.lstrip('/')}"
                print(f"AUDIT LOG: Calling {operation.method.upper()} {target_url}")
                
                response = case.call(base_url=self.base_url, headers=headers)
                print(f"AUDIT LOG: Response Status Code: {response.status_code}")
                
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
        
        print("AUDIT LOG: Starting Module B: Resilience Stress Test (flooding requests)...")
        
        
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
                self._apply_seed_data(case)

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