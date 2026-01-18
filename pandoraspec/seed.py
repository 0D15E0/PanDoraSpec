import re
import requests
from typing import Dict, Any, Optional

class SeedManager:
    def __init__(self, seed_data: Dict[str, Any], base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.seed_data = seed_data
        self.base_url = base_url
        self.api_key = api_key
        self.dynamic_cache = {}

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

            if not self.base_url:
                print("WARNING: Cannot resolve dynamic seed, base_url is not set.")
                return None

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

    def apply_seed_data(self, case):
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
