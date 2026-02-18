import re
from typing import Any

import requests

from .utils.http import build_auth_header
from .utils.logger import logger
from .utils.parsing import extract_json_value, extract_regex_value


class SeedManager:
    def __init__(self, seed_data: dict[str, Any], base_url: str | None = None, api_key: str | None = None):
        self.seed_data = seed_data
        self.base_url = base_url
        self.api_key = api_key
        self.dynamic_cache: dict[str, Any] = {}
        self._resolving_stack: set[str] = set()  # Tracks in-progress resolutions to detect cycles

    def _get_seed_config(self, method: str, path: str) -> dict[str, Any]:
        """Merges seed data for a specific endpoint using priority: General < Verb < Endpoint."""
        if not self.seed_data:
            return {}

        is_hierarchical = any(k in self.seed_data for k in ("general", "verbs", "endpoints"))

        if is_hierarchical:
            merged_data: dict[str, Any] = self.seed_data.get("general", {}).copy()
            merged_data.update(self.seed_data.get("verbs", {}).get(method.upper(), {}))
            merged_data.update(
                self.seed_data.get("endpoints", {}).get(path, {}).get(method.upper(), {})
            )
        else:
            merged_data = self.seed_data.copy()

        return merged_data

    def _resolve_dynamic_value(self, config_value: Any) -> Any:
        """Resolves dynamic seed values, supporting recursion and cycle detection."""
        if not isinstance(config_value, dict) or "from_endpoint" not in config_value:
            return config_value

        endpoint_def = config_value["from_endpoint"]

        if endpoint_def in self.dynamic_cache:
            return self.dynamic_cache[endpoint_def]

        if endpoint_def in self._resolving_stack:
            logger.warning(f"Circular dependency detected for {endpoint_def}. Breaking cycle.")
            return None

        self._resolving_stack.add(endpoint_def)

        try:
            try:
                method, path = endpoint_def.split(" ", 1)
            except ValueError:
                logger.warning(f"Invalid endpoint definition '{endpoint_def}'. Expected 'METHOD /path'.")
                return None

            if not self.base_url:
                logger.warning("Cannot resolve dynamic seed: base_url is not set.")
                return None

            # Recursively resolve dependencies for the upstream endpoint
            upstream_seed_config = self._get_seed_config(method, path)
            resolved_upstream_params: dict[str, Any] = {}

            for k, v in upstream_seed_config.items():
                resolved_val = self._resolve_dynamic_value(v)
                if resolved_val is not None:
                    resolved_upstream_params[k] = resolved_val

            # Inject resolved params into path placeholders (e.g. /users/{id})
            general_seeds = self.seed_data.get("general", {}) if self.seed_data else {}

            def replace_param(match: re.Match[str]) -> str:
                param_name = match.group(1)
                if param_name in resolved_upstream_params:
                    return str(resolved_upstream_params[param_name])
                if param_name in general_seeds:
                    return str(general_seeds[param_name])
                logger.warning(f"Missing seed value for {{{param_name}}} in dynamic endpoint {endpoint_def}")
                return match.group(0)

            url_path = re.sub(r"\{([a-zA-Z0-9_]+)\}", replace_param, path)
            url = f"{self.base_url.rstrip('/')}/{url_path.lstrip('/')}"

            headers = {"Authorization": build_auth_header(self.api_key)} if self.api_key else {}

            # Unused resolved params become query string parameters
            query_params = {
                k: v for k, v in resolved_upstream_params.items()
                if f"{{{k}}}" not in path
            }

            logger.debug(f"AUDIT LOG: Resolving dynamic seed from {method} {url_path}")
            response = requests.request(method, url, headers=headers, params=query_params)

            if response.status_code >= 400:
                logger.warning(f"Dynamic seed request failed with {response.status_code}")
                return None

            result: Any = None
            extract_key = config_value.get("extract")
            regex_pattern = config_value.get("regex")

            if extract_key:
                try:
                    json_data = response.json()
                    result = extract_json_value(json_data, extract_key)
                except Exception:
                    logger.warning("Failed to parse JSON for seed extraction.")
            else:
                result = response.text

            if regex_pattern and result is not None:
                result = extract_regex_value(str(result), regex_pattern)

            self.dynamic_cache[endpoint_def] = result
            return result

        except Exception as e:
            logger.error(f"Failed to resolve dynamic seed: {e}")
            return None
        finally:
            self._resolving_stack.discard(endpoint_def)

    def apply_seed_data(self, case) -> set[str]:
        """Injects resolved seed data into a schemathesis test case."""
        if not self.seed_data:
            return set()

        if hasattr(case, "operation"):
            method = case.operation.method.upper()
            path = case.operation.path
            merged_data = self._get_seed_config(method, path)
        else:
            merged_data = self._get_seed_config("", "")

        resolved_data: dict[str, Any] = {}
        for k, v in merged_data.items():
            resolved_val = self._resolve_dynamic_value(v)
            if resolved_val is not None:
                resolved_data[k] = resolved_val

        seeded_keys: set[str] = set()

        if hasattr(case, "path_parameters") and case.path_parameters:
            for key in case.path_parameters:
                if key in resolved_data:
                    case.path_parameters[key] = resolved_data[key]
                    seeded_keys.add(key)

        if hasattr(case, "query") and case.query:
            for key in case.query:
                if key in resolved_data:
                    case.query[key] = resolved_data[key]
                    seeded_keys.add(key)

        if hasattr(case, "headers") and case.headers:
            for key in case.headers:
                if key in resolved_data:
                    case.headers[key] = str(resolved_data[key])
                    seeded_keys.add(key)

        return seeded_keys
