#!/usr/bin/env python3
import json
import sys
import os

def check_compliance(report_path):
    if not os.path.exists(report_path):
        print(f"❌ Report not found: {report_path}")
        sys.exit(1)

    try:
        with open(report_path, "r") as f:
            data = json.load(f)
        
        score = data.get("score", 0)
        is_compliant = data.get("is_compliant", False)
        vendor = data.get("vendor_name", "Unknown")

        print(f"🔍 Analyzing DORA Report for {vendor}...")
        print(f"   Score: {score}/100")
        print(f"   Compliant: {'✅ YES' if is_compliant else '❌ NO'}")

        if not is_compliant:
            print("🚨 Compliance Check FAILED. See report for details.")
            sys.exit(1)
        
        print("✅ Compliance Check PASSED.")
        sys.exit(0)

    except Exception as e:
        print(f"❌ Failed to parse report: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_compliance.py <path_to_report.json>")
        sys.exit(1)
    
    check_compliance(sys.argv[1])
