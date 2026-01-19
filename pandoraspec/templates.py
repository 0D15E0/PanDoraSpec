from datetime import datetime

def get_report_template(vendor_name: str, total_score: float, is_compliant: bool, audit_results: dict, render_findings_table_func) -> str:
    """
    Returns the HTML content for the DORA Compliance Report.
    """
    return f"""
    <html>
    <head>
        <style>
            @page {{ margin: 50px; }}
            body {{ font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.5; }}
            .header {{ 
                background: linear-gradient(135deg, #1e1b4b 0%, #4338ca 100%); 
                color: white; 
                padding: 40px; 
                text-align: center; 
                border-radius: 12px;
                margin-bottom: 40px;
            }}
            .header h1 {{ margin: 0; font-size: 28px; letter-spacing: -0.5px; }}
            .header p {{ margin: 10px 0 0; opacity: 0.8; font-size: 16px; }}
            
            .summary-grid {{ display: flex; justify-content: space-between; margin-bottom: 40px; }}
            .summary-card {{ 
                background: #f8fafc; 
                padding: 20px; 
                border-radius: 8px; 
                width: 45%; 
                border: 1px solid #e2e8f0;
            }}
            
            .score-big {{ font-size: 56px; font-weight: 800; margin: 10px 0; }}
            .status-badge {{ 
                display: inline-block; 
                padding: 6px 16px; 
                border-radius: 99px; 
                font-weight: 700; 
                text-transform: uppercase;
                font-size: 14px;
            }}
            .status-pass {{ background: #dcfce7; color: #166534; }}
            .status-fail {{ background: #fee2e2; color: #991b1b; }}
            
            .section {{ margin-top: 40px; page-break-inside: avoid; }}
            .section h3 {{ border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; color: #0f172a; margin-bottom: 20px; }}
            
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; table-layout: fixed; word-wrap: break-word; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
            td {{ word-break: break-word; white-space: pre-wrap; }}
            th {{ background-color: #f1f5f9; color: #475569; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
            
            .badge {{ 
                padding: 4px 8px; 
                border-radius: 4px; 
                font-size: 10px; 
                font-weight: 700; 
                color: white; 
                text-transform: uppercase; 
                font-size: 10px; 
                font-weight: 700; 
                color: white; 
                text-transform: uppercase; 
            }}
            .badge-critical {{ background: #ef4444; }}
            .badge-high {{ background: #f97316; }}
            .badge-medium {{ background: #eab308; }}
            .badge-low {{ background: #3b82f6; }}
            .badge-pass {{ background: #16a34a; }}
            
            .no-issues {{ color: #059669; font-weight: 500; padding: 10px 0; }}
            code {{ font-family: 'Courier New', monospace; background: #f1f5f9; padding: 2px 4px; border-radius: 3px; font-size: 11px; }}
            
            footer {{ margin-top: 50px; text-align: center; color: #94a3b8; font-size: 10px; border-top: 1px solid #e2e8f0; padding-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>DORA ICT Third-Party Risk Assessment</h1>
            <p>Vendor Compliance Audit for <strong>{vendor_name}</strong></p>
            <p>Report Date: {datetime.now().strftime("%B %d, %Y")}</p>
        </div>

        <div class="summary-grid">
            <div class="summary-card">
                <p style="margin:0; color:#64748b; font-weight:600;">Overall Risk Score</p>
                <div class="score-big" style="color: {'#166534' if is_compliant else '#991b1b'}">{round(total_score)}<span style="font-size: 24px; color:#94a3b8; font-weight:400;">/100</span></div>
            </div>
            <div class="summary-card">
                <p style="margin:0; color:#64748b; font-weight:600;">Compliance Status</p>
                <div style="margin-top: 20px;">
                    <span class="status-badge {'status-pass' if is_compliant else 'status-fail'}">
                        {'COMPLIANT (PASS)' if is_compliant else 'NON-COMPLIANT (FAIL)'}
                    </span>
                </div>
            </div>
        </div>

        <div class="section">
            <h3>Technical Findings - Module A: Schema Integrity (Docs vs. Code)</h3>
            <p style="font-size: 13px; color: #64748b; margin-bottom: 15px;">
                This check verifies if the actual API implementation adheres to the provided OpenAPI specification.
                Discrepancies here indicate "Schema Drift," which violates DORA requirements for accurate ICT documentation.
            </p>
            {render_findings_table_func("Module A", audit_results['drift_check'])}
        </div>

        <div class="section">
            <h3>Technical Findings - Module B: Resilience Stress Test</h3>
            <p style="font-size: 13px; color: #64748b; margin-bottom: 15px;">
                Assesses high-load behavior and error handling (DORA Art. 24 & 25).
                Checks if the system gracefully handles request flooding with appropriate 429 status codes.
            </p>
            {render_findings_table_func("Module B", audit_results['resilience'])}
        </div>

        <div class="section">
            <h3>Technical Findings - Module C: Security Hygiene</h3>
            <p style="font-size: 13px; color: #64748b; margin-bottom: 15px;">
                Evaluates baseline security controls including TLS encryption and sensitive information leakage in URLs.
            </p>
            {render_findings_table_func("Module C", audit_results['security'])}
        </div>

        <footer>
            <p>CONFIDENTIAL - FOR INTERNAL AUDIT PURPOSES ONLY</p>
            <p>Generated by PanDoraSpec</p>
        </footer>
    </body>
    </html>
    """
