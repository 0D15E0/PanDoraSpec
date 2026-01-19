import yaml
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from .core import AuditEngine
from .reporting.generator import generate_report, generate_json_report
from .utils.logger import logger

@dataclass
class AuditRunResult:
    results: Dict[str, Any]
    report_path: str
    seed_count: int

from .config import validate_config, PandoraConfig

def load_config(config_path: str) -> PandoraConfig:
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                raw_data = yaml.safe_load(f) or {}
                return validate_config(raw_data)
        except Exception as e:
            logger.error(f"Failed to load or validate config from {config_path}: {e}")
            return PandoraConfig()
    return PandoraConfig()

def run_dora_audit_logic(
    target: str,
    vendor: str,
    api_key: Optional[str] = None,
    config_path: Optional[str] = None,
    base_url: Optional[str] = None,
    output_format: str = "pdf",
    output_path: Optional[str] = None
) -> AuditRunResult:
    """
    Orchestrates the DORA audit: loads config, runs engine, generates report.
    Decoupled from CLI/Printing.
    """
    # 1. Load Config
    seed_data = {}
    if config_path:
        config_data = load_config(config_path)
        seed_data = config_data.seed_data
    
    # 2. Initialize Engine
    engine = AuditEngine(
        target=target, 
        api_key=api_key, 
        seed_data=seed_data, 
        base_url=base_url
    )
    
    # 3. Run Audit
    logger.info(f"Starting audit for {target}")
    results = engine.run_full_audit()
    
    # 4. Generate Report
    if output_format.lower() == "json":
        report_path = generate_json_report(vendor, results, output_path=output_path)
    else:
        report_path = generate_report(vendor, results, output_path=output_path)
    
    return AuditRunResult(
        results=results,
        report_path=report_path,
        seed_count=len(seed_data)
    )
