import os
from datetime import datetime
from weasyprint import HTML
from .templates import get_report_template

REPORTS_DIR = "reports"

if not os.path.exists(REPORTS_DIR):
    os.makedirs(REPORTS_DIR)

def generate_report(vendor_name: str, audit_results: dict, output_path: str = None) -> str:
    """
    Module D: The Compliance Report (The Deliverable)
    Generates a branded PDF report.
    """
    # ... (omitted for brevity, assume logic matches but filename handling changes)
    
    # Calculate scores...
    drift_issues = [r for r in audit_results["drift_check"] if r.get("status") != "PASS"]
    resilience_issues = [r for r in audit_results["resilience"] if r.get("status") != "PASS"]
    security_issues = [r for r in audit_results["security"] if r.get("status") != "PASS"]

    drift_score = max(0, 100 - len(drift_issues) * 10)
    resilience_score = max(0, 100 - len(resilience_issues) * 15)
    security_score = max(0, 100 - len(security_issues) * 20)
    
    total_score = (drift_score + resilience_score + security_score) / 3
    is_compliant = total_score >= 80

    context = {
        "vendor_name": vendor_name,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "score": round(total_score),
        "is_compliant": is_compliant,
        "results": audit_results
    }
    
    # ... (render_findings_table helper omitted) ...
    def render_findings_table(module_name, findings):
        if not findings:
            return f"<p class='no-issues'>✅ No issues found in {module_name}.</p>"
        
        rows = ""
        for f in findings:
            endpoint = f.get('endpoint', 'Global')
            status = f.get('status', 'FAIL')
            
            if status == "PASS":
                severity_class = "pass"
                severity_text = "PASS"
            else:
                severity_class = f.get('severity', 'LOW').lower()
                severity_text = f.get('severity')

            rows += f"<tr><td><span class='badge badge-{severity_class}'>{severity_text}</span></td><td><code>{endpoint}</code></td><td><strong>{f.get('issue')}</strong></td><td>{f.get('details')}</td></tr>"
        
        return f"<table><thead><tr><th style='width: 10%'>Status</th><th style='width: 25%'>Endpoint</th><th style='width: 25%'>Issue</th><th>Technical Details</th></tr></thead><tbody>{rows}</tbody></table>"

    html_content = get_report_template(
        vendor_name=vendor_name,
        total_score=total_score,
        is_compliant=is_compliant,
        audit_results=audit_results,
        render_findings_table_func=render_findings_table
    )

    if output_path:
        filepath = output_path
    else:
        filename = f"{vendor_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        filepath = os.path.join(REPORTS_DIR, filename)
    
    HTML(string=html_content).write_pdf(filepath)
    return filepath

def generate_json_report(vendor_name: str, audit_results: dict, output_path: str = None) -> str:
    """
    Generates a machine-readable JSON report for CI/CD pipelines.
    """
    import json
    
    # Filter out PASS results for scoring
    drift_issues = [r for r in audit_results["drift_check"] if r.get("status") != "PASS"]
    resilience_issues = [r for r in audit_results["resilience"] if r.get("status") != "PASS"]
    security_issues = [r for r in audit_results["security"] if r.get("status") != "PASS"]

    drift_score = max(0, 100 - len(drift_issues) * 10)
    resilience_score = max(0, 100 - len(resilience_issues) * 15)
    security_score = max(0, 100 - len(security_issues) * 20)
    
    total_score = (drift_score + resilience_score + security_score) / 3
    is_compliant = total_score >= 80

    report_data = {
        "vendor_name": vendor_name,
        "date": datetime.now().isoformat(),
        "score": round(total_score, 2),
        "is_compliant": is_compliant,
        "results": audit_results
    }

    if output_path:
        filepath = output_path
    else:
        filename = f"{vendor_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        filepath = os.path.join(REPORTS_DIR, filename)

    with open(filepath, "w") as f:
        json.dump(report_data, f, indent=2)
        
    return filepath
