import os
from typing import List, Dict, Any
from ..config import PandoraConfig
from ..utils.logger import logger

def run_ai_assessment(spec_schema: Any, aggregated_results: Dict[str, List[Dict]], config: PandoraConfig) -> List[Dict]:
    """
    Module E: AI Auditor
    Uses OpenAI to provide a semantic risk assessment of the technical findings.
    """
    api_key = config.openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("Module E Skipped: No OPENAI_API_KEY provided.")
        return []

    try:
        import openai
    except ImportError:
        logger.warning("Module E Skipped: 'openai' package not installed.")
        return []

    logger.info("AUDIT LOG: Starting Module E: AI Risk Assessment...")
    
    # Initialize OpenAI Client
    client = openai.OpenAI(api_key=api_key)

    # 1. Summarize Findings
    summary_text = _summarize_technical_findings(aggregated_results)
    
    # 2. Extract API Info
    api_title = "Unknown API"
    try:
        # schemathesis schema -> raw schema
        if hasattr(spec_schema, "raw_schema"):
            info = spec_schema.raw_schema.get("info", {})
            api_title = info.get("title", "Unknown API")
            description = info.get("description", "")
        else:
            description = "No description available."
    except:
        description = "No description available."

    # 3. Construct Prompt
    prompt = f"""
    You are a Virtual CISO (Chief Information Security Officer) auditing an API for DORA (Digital Operational Resilience Act) compliance.
    
    API Name: {api_title}
    Description: {description}
    
    Here are the technical findings from our automated scanner:
    {summary_text}
    
    Task:
    1. Analyze these findings in the context of DORA compliance (Resilience, Security, Integrity).
    2. Provide a 'Compliance Risk Score' from 0 (Safe) to 10 (Critical Risk).
    3. Write a 1-paragraph Executive Summary explaining the risk to a non-technical board member.
    4. Issue a final verdict: PASS or FAIL.
    
    Format your response exactly as valid JSON:
    {{
        "risk_score": <int>,
        "verdict": "<PASS|FAIL>",
        "executive_summary": "<string>"
    }}
    """

    try:
        response = client.chat.completions.create(
            model=config.ai_model,
            messages=[
                {"role": "system", "content": "You are a strict, risk-focused security auditor."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        import json
        assessment = json.loads(content)
        
        # Convert to standard result format
        result = {
            "module": "E",
            "issue": "AI Risk Assessment",
            "status": assessment.get("verdict", "FAIL"),
            "details": f"Risk Score: {assessment.get('risk_score', 10)}/10. {assessment.get('executive_summary', 'No summary provided.')}",
            "severity": "CRITICAL" if assessment.get("verdict") == "FAIL" else "INFO"
        }
        return [result]

    except Exception as e:
        logger.error(f"Module E Failed: {e}")
        return [{
            "module": "E",
            "issue": "AI Assessment Error",
            "status": "FAIL",
            "details": f"Failed to consult AI: {str(e)}",
            "severity": "LOW"
        }]

def _summarize_technical_findings(results: Dict[str, List[Dict]]) -> str:
    summary = []
    
    for module, checks in results.items():
        failures = [c for c in checks if c["status"] == "FAIL"]
        if failures:
            summary.append(f"\n[{module.upper()}] Failures:")
            for f in failures:
                summary.append(f"- {f['issue']} ({f['severity']}): {f['details']}")
        else:
            summary.append(f"\n[{module.upper()}] Passed all checks.")
            
    return "\n".join(summary)
