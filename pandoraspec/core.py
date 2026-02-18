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
from .utils.plugins import load_and_execute_hook
from .utils.url import derive_base_url_from_target


class AuditEngine:
    def __init__(
        self,
        target: str,
        api_key: str | None = None,
        seed_data: dict[str, Any] | None = None,
        base_url: str | None = None,
        allowed_domains: list[str] | None = None,
        config: PandoraConfig | None = None,
    ) -> None:
        self.target = target
        self.api_key = api_key
        self.seed_data = seed_data or {}
        self.base_url = base_url
        self.allowed_domains = allowed_domains or []
        self.config = config or PandoraConfig()
        self.schema = None

        # -------------------------------------------------
        # Schema Loading
        # -------------------------------------------------
        try:
            if os.path.exists(target) and os.path.isfile(target):
                logger.debug(f"Loading schema from local file: {target}")
                self.schema = schemathesis.openapi.from_path(target)
            else:
                self.schema = schemathesis.openapi.from_url(target)

            resolved_url: str | None = None

            if self.base_url:
                # Manual override takes highest priority
                logger.debug(f"Using manual override base_url: {self.base_url}")
                resolved_url = self.base_url
            else:
                # Priority 1: Extract from the 'servers' field in the spec
                if hasattr(self.schema, "raw_schema"):
                    servers = self.schema.raw_schema.get("servers", [])
                    if servers and isinstance(servers, list):
                        spec_server_url = servers[0].get("url")
                        if spec_server_url:
                            resolved_url = spec_server_url
                            logger.debug(f"Found server URL in specification: {resolved_url}")

                # Priority 2: Schemathesis resolved URL (fallback)
                if not resolved_url:
                    resolved_url = getattr(self.schema, "base_url", None)
                    logger.debug(f"Falling back to Schemathesis resolved base_url: {resolved_url}")

                # Priority 3: Derive from the target URL itself
                if not resolved_url:
                    resolved_url = derive_base_url_from_target(self.target)
                    if resolved_url:
                        logger.debug(f"Derived base_url from schema URL: {resolved_url}")

            logger.debug(f"Final resolved base_url for engine: {resolved_url}")
            self.base_url = resolved_url

            if resolved_url:
                try:
                    self.schema.base_url = resolved_url  # type: ignore[attr-defined]
                except Exception:
                    pass  # Some schemathesis versions make base_url read-only; safe to ignore

        except Exception as e:
            logger.error(f"Error loading schema from '{target}': {e}")
            raise ValueError(f"Failed to load OpenAPI schema from '{target}'. Error: {e}") from e

        # -------------------------------------------------
        # Dynamic Authentication Hook
        # -------------------------------------------------
        if self.config.auth_hook:
            logger.info("Auth Hook detected. Executing pre-audit authentication script...")
            try:
                token = load_and_execute_hook(
                    self.config.auth_hook.path,
                    self.config.auth_hook.function_name,
                )
                logger.info(f"Auth Hook executed successfully. Token received (len={len(token)}).")
                self.api_key = token
            except Exception as e:
                logger.error(f"Failed to execute Auth Hook: {e}")
                raise

        # -------------------------------------------------
        # Seed Manager
        # -------------------------------------------------
        self.seed_manager = SeedManager(self.seed_data, self.base_url, self.api_key)

    def run_full_audit(self) -> dict:
        """Runs all audit modules and returns their combined results."""
        final_base_url = self.base_url or ""
        final_api_key = self.api_key or ""

        results = {
            "drift_check": run_drift_check(self.schema, final_base_url, final_api_key, self.seed_manager),
            "resilience": run_resilience_tests(self.schema, final_base_url, final_api_key, self.seed_manager),
            "security": run_security_hygiene(
                self.schema,
                final_base_url,
                self.api_key,  # Optional — modules handle None
                allowed_domains=self.allowed_domains,
            ),
        }

        ai_results = run_ai_assessment(self.schema, results, self.config)
        results["ai_auditor"] = ai_results

        return results
