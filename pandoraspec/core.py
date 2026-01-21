import os
from typing import Any

import schemathesis

from .config import PandoraConfig
from .modules.ai_judge import run_ai_assessment
from .modules.drift import run_drift_check
from .modules.resilience import run_resilience_tests
from .modules.security import run_security_hygiene
from .seed import SeedManager
from .utils.logger import logger
from .utils.url import derive_base_url_from_target


class AuditEngine:
    def __init__(self, target: str, api_key: str | None = None, seed_data: dict[str, Any] | None = None, base_url: str | None = None, allowed_domains: list[str] | None = None, config: PandoraConfig | None = None) -> None:
        self.target = target
        self.api_key = api_key
        self.seed_data = seed_data or {}
        self.base_url = base_url
        self.allowed_domains = allowed_domains or []
        self.config = config or PandoraConfig() # Store full config
        self.dynamic_cache: dict[str, Any] = {}
        self.schema = None

        try:
            if os.path.exists(target) and os.path.isfile(target):
                 logger.debug(f"Loading schema from local file: {target}")
                 self.schema = schemathesis.openapi.from_path(target)
            else:
                 self.schema = schemathesis.openapi.from_url(target)

            # If base_url was manually provided, we skip dynamic resolution
            if self.base_url:
                logger.debug(f"Using manual override base_url: {self.base_url}")
                resolved_url = self.base_url
            else:
                # Priority 1: Extract from the 'servers' field in the spec
                resolved_url = None
                if hasattr(self.schema, "raw_schema"):
                    servers = self.schema.raw_schema.get("servers", [])
                    if servers and isinstance(servers, list) and len(servers) > 0:
                        spec_server_url = servers[0].get("url")
                        if spec_server_url:
                            resolved_url = spec_server_url
                            logger.debug(f"Found server URL in specification: {resolved_url}")

            # Priority 2: Use whatever schemathesis resolved automatically (fallback)
            if not resolved_url:
                resolved_url = getattr(self.schema, "base_url", None)
                logger.debug(f"Falling back to Schemathesis resolved base_url: {resolved_url}")

            if not resolved_url:
                # Fallback: Derive from target URL
                derived = derive_base_url_from_target(self.target)
                if derived:
                   resolved_url = derived
                   logger.debug(f"Derived base_url from schema_url: {resolved_url}")

            logger.debug(f"Final resolved base_url for engine: {resolved_url}")
            self.base_url = resolved_url
            if resolved_url:
                try:
                    self.schema.base_url = resolved_url # type: ignore
                except Exception:
                    pass
        except Exception as e:
             # Handle invalid URL or schema loading error gracefully
             logger.error(f"Error loading schema: {e}")
             if target and (target.startswith("http") or os.path.exists(target)):
                pass # Allow to continue if it's just a warning, but schemathesis might fail later
             else:
                raise ValueError(f"Failed to load OpenAPI schema from {target}. Error: {str(e)}")

        # Initialize Seed Manager
        self.seed_manager = SeedManager(self.seed_data, self.base_url, self.api_key)

    def run_full_audit(self) -> dict:
        # Ensure base_url is strictly string (or fail if logic broke)
        final_base_url = self.base_url or ""

        results = {
            "drift_check": run_drift_check(self.schema, final_base_url, self.api_key or "", self.seed_manager),
            "resilience": run_resilience_tests(self.schema, final_base_url, self.api_key or "", self.seed_manager),
            "security": run_security_hygiene(self.schema, final_base_url, self.api_key or "", allowed_domains=self.allowed_domains)
        }

        # 6. Run AI Assessment
        # config is properly typed
        ai_results = run_ai_assessment(self.schema, results, self.config)
        results["ai_auditor"] = ai_results

        return results
