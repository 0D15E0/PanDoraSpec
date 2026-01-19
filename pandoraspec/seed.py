import re
import requests
from typing import Any, Optional
from .utils import extract_json_value, extract_regex_value
from .logger import logger

class SeedManager:
    def __init__(self, seed_data: dict[str, Any], base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.seed_data = seed_data
        self.base_url = base_url
        self.api_key = api_key
        self.dynamic_cache = {}
        self._resolving_stack = set() # To detect recursion cycles

    def _get_seed_config(self, method: str, path: str) -> dict[str, Any]:
        """Merges seed data for a specific endpoint (General < Verb < Endpoint)"""
        if not self.seed_data:
            return {}

        is_hierarchical = any(k in self.seed_data for k in ['general', 'verbs', 'endpoints'])
        
        if is_hierarchical:
            # 1. General
            merged_data = self.seed_data.get('general', {}).copy()
            # 2. Verb
            verb_data = self.seed_data.get('verbs', {}).get(method.upper(), {})
            merged_data.update(verb_data)
            # 3. Endpoint
            endpoint_data = self.seed_data.get('endpoints', {}).get(path, {}).get(method.upper(), {})
            merged_data.update(endpoint_data)
        else:
            merged_data = self.seed_data.copy()
            
        return merged_data

    def _resolve_dynamic_value(self, config_value: Any) -> Any:
        """Resolves dynamic seed values with recursion support"""
        if not isinstance(config_value, dict) or "from_endpoint" not in config_value:
            return config_value

        endpoint_def = config_value["from_endpoint"]
        
        # Check cache first
        if endpoint_def in self.dynamic_cache:
            return self.dynamic_cache[endpoint_def]

        # Cycle detection
        if endpoint_def in self._resolving_stack:
            logger.warning(f"Circular dependency detected for {endpoint_def}. Breaking cycle.")
            return None
        
        self._resolving_stack.add(endpoint_def)

        try:
            try:
                method, path = endpoint_def.split(" ", 1)
            except ValueError:
                logger.warning(f"Invalid endpoint definition '{endpoint_def}'. Expected 'METHOD /path'")
                return None

            if not self.base_url:
                logger.warning("Cannot resolve dynamic seed, base_url is not set.")
                return None

            # Recursive Step: Resolve dependencies BEFORE making the request
            # We get the seed config for the *upstream* endpoint we are about to call
            upstream_seed_config = self._get_seed_config(method, path)
            resolved_upstream_params = {}
            
            for k, v in upstream_seed_config.items():
                resolved_val = self._resolve_dynamic_value(v)
                if resolved_val is not None:
                    resolved_upstream_params[k] = resolved_val

            # URL Parameter Injection
            # Iterate through resolved params to inject into path (e.g. /users/{id})
            # Also fall back to general seeds if not explicitly resolved above (legacy behavior)
            general_seeds = self.seed_data.get('general', {}) if self.seed_data else {}
            
            def replace_param(match):
                param_name = match.group(1)
                # specific resolved param > general seed
                if param_name in resolved_upstream_params:
                    return str(resolved_upstream_params[param_name])
                if param_name in general_seeds:
                     return str(general_seeds[param_name])
                logger.warning(f"Missing seed value for {{{param_name}}} in dynamic endpoint {endpoint_def}")
                return match.group(0)

            url_path = re.sub(r"\{([a-zA-Z0-9_]+)\}", replace_param, path)
            url = f"{self.base_url.rstrip('/')}/{url_path.lstrip('/')}"
            
            # Prepare Request
            headers = {}
            if self.api_key:
                 auth_header = self.api_key if self.api_key.lower().startswith("bearer ") else f"Bearer {self.api_key}"
                 headers["Authorization"] = auth_header

            # Query Params from unused resolved seeds
            query_params = {}
            for k, v in resolved_upstream_params.items():
                 # If it wasn't used in the path, put it in query params
                 if f"{{{k}}}" not in path:
                     query_params[k] = v

            logger.debug(f"AUDIT LOG: Resolving dynamic seed from {method} {url_path}")
            response = requests.request(method, url, headers=headers, params=query_params)
            
            if response.status_code >= 400:
                logger.warning(f"Dynamic seed request failed with {response.status_code}")
                return None

            result = None
            extract_key = config_value.get("extract")
            regex_pattern = config_value.get("regex")

            # JSON Extraction
            if extract_key:
                try:
                    json_data = response.json()
                    result = extract_json_value(json_data, extract_key)
                except Exception:
                    logger.warning("Failed to parse JSON for seed extraction")
            else:
                 result = response.text

            # Regex Extraction
            if regex_pattern and result is not None:
                result = extract_regex_value(str(result), regex_pattern)
            
            self.dynamic_cache[endpoint_def] = result
            return result

        except Exception as e:
            logger.error(f"Failed to resolve dynamic seed: {e}")
            return None
        finally:
            self._resolving_stack.discard(endpoint_def)

    def apply_seed_data(self, case):
        """Helper to inject seed data into test cases with hierarchy: General < Verbs < Endpoints"""
        if not self.seed_data:
            return set()

        if hasattr(case, 'operation'):
            method = case.operation.method.upper()
            path = case.operation.path
            merged_data = self._get_seed_config(method, path)
        else:
            merged_data = self._get_seed_config("", "")

        # Resolve dynamic values for the final merged dataset
        resolved_data = {}
        for k, v in merged_data.items():
            resolved_val = self._resolve_dynamic_value(v)
            if resolved_val is not None:
                resolved_data[k] = resolved_val

        seeded_keys = set()
        # Inject into Path Parameters (e.g., /users/{userId})
        if hasattr(case, 'path_parameters') and case.path_parameters:
            for key in case.path_parameters:
                if key in resolved_data:
                    case.path_parameters[key] = resolved_data[key]
                    seeded_keys.add(key)

        # Inject into Query Parameters (e.g., ?status=active)
        if hasattr(case, 'query') and case.query:
            for key in case.query:
                if key in resolved_data:
                    case.query[key] = resolved_data[key]
                    seeded_keys.add(key)
                    
        # Inject into Headers (e.g., X-Tenant-ID)
        if hasattr(case, 'headers') and case.headers:
            for key in case.headers:
                if key in resolved_data:
                    case.headers[key] = str(resolved_data[key])
                    seeded_keys.add(key)
        
        return seeded_keys
