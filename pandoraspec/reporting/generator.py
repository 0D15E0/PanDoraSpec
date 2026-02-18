import json
import os
from datetime import datetime

from weasyprint import HTML

from ..constants import COMPLIANCE_THRESHOLD
from .templates import get_report_template

REPORTS_DIR = "reports"


def _ensure_reports_dir(path: str) -> None:
    """Creates the reports directory (or any parent dirs) if it does not exist."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else REPORTS_DIR, exist_ok=True)


def _calculate_scores(audit_results: dict) -> tuple[float, bool]:
    """
    Computes the weighted compliance score from audit results.
    Returns (total_score, is_compliant).
    """
    drift_issues = sum(1 for r in audit_results["drift_check"] if r.get("status") != "PASS")
    resilience_issues = sum(1 for r in audit_results["resilience"] if r.get("status") != "PASS")
    security_issues = sum(1 for r in audit_results["security"] if r.get("status") != "PASS")

    drift_score = max(0, 100 - drift_issues * 10)
    resilience_score = max(0, 100 - resilience_issues * 15)
    security_score = max(0, 100 - security_issues * 20)

    total_score = (drift_score + resilience_score + security_score) / 3
    return total_score, total_score >= COMPLIANCE_THRESHOLD


def generate_report(vendor_name: str, audit_results: dict, output_path: str | None = None) -> str:
    """
    Module D: The Compliance Report (The Deliverable)
    Generates a branded PDF report.
    """
    total_score, is_compliant = _calculate_scores(audit_results)

    def render_findings_table(module_name: str, findings: list) -> str:
        if not findings:
            return f"<p class='no-issues'>✅ No issues found in {module_name}.</p>"

        rows = ""
        for f in findings:
            endpoint = f.get("endpoint", "Global")
            status = f.get("status", "FAIL")

            if status == "PASS":
                severity_class = "pass"
                severity_text = "PASS"
            else:
                severity_class = f.get("severity", "LOW").lower()
                severity_text = f.get("severity")

            rows += (
                f"<tr>"
                f"<td><span class='badge badge-{severity_class}'>{severity_text}</span></td>"
                f"<td><code>{endpoint}</code></td>"
                f"<td><strong>{f.get('issue')}</strong></td>"
                f"<td>{f.get('details')}</td>"
                f"</tr>"
            )

        return (
            "<table>"
            "<thead><tr>"
            "<th style='width: 10%'>Status</th>"
            "<th style='width: 25%'>Endpoint</th>"
            "<th style='width: 25%'>Issue</th>"
            "<th>Technical Details</th>"
            "</tr></thead>"
            f"<tbody>{rows}</tbody>"
            "</table>"
        )

    html_content = get_report_template(
        vendor_name=vendor_name,
        total_score=total_score,
        is_compliant=is_compliant,
        audit_results=audit_results,
        render_findings_table_func=render_findings_table,
    )

    if output_path:
        filepath = output_path
    else:
        filename = f"{vendor_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        filepath = os.path.join(REPORTS_DIR, filename)

    _ensure_reports_dir(filepath)
    HTML(string=html_content).write_pdf(filepath)
    return filepath


def generate_json_report(vendor_name: str, audit_results: dict, output_path: str | None = None) -> str:
    """
    Generates a machine-readable JSON report for CI/CD pipelines.
    """
    total_score, is_compliant = _calculate_scores(audit_results)

    report_data = {
        "vendor_name": vendor_name,
        "date": datetime.now().isoformat(),
        "score": round(total_score, 2),
        "is_compliant": is_compliant,
        "results": audit_results,
    }

    if output_path:
        filepath = output_path
    else:
        filename = f"{vendor_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        filepath = os.path.join(REPORTS_DIR, filename)

    _ensure_reports_dir(filepath)
    with open(filepath, "w") as f:
        json.dump(report_data, f, indent=2)

    return filepath
