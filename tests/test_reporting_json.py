import json
import os
from pandoraspec.reporting.generator import generate_json_report

def test_generate_json_report(tmp_path):
    # Mock data
    vendor = "TestVendor"
    results = {
        "drift_check": [{"status": "PASS"}, {"status": "FAIL", "severity": "HIGH"}],
        "resilience": [{"status": "PASS"}],
        "security": [{"status": "PASS"}]
    }
    
    # Patch REPORTS_DIR temporarily or just check return path
    # Since generate_json_report uses a global REPORTS_DIR, we might need to mock os.path.join or setting the var
    # But for simplicity, let's just run it and check if file exists (it handles directory creation)
    
    filepath = generate_json_report(vendor, results)
    
    assert os.path.exists(filepath)
    assert filepath.endswith(".json")
    
    with open(filepath, "r") as f:
        data = json.load(f)
        
    assert data["vendor_name"] == vendor
    assert data["is_compliant"] is True # 96.6 score is passing
    assert "score" in data
    assert data["results"] == results
    
    # Cleanup
    if os.path.exists(filepath):
        os.remove(filepath)
