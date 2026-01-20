from pandoraspec.reporting.junit import generate_junit_xml
import os
import xml.etree.ElementTree as ET

def test_generate_junit_xml(tmp_path):
    output_file = tmp_path / "report.xml"
    
    results = {
        "drift_check": [
             {"status": "PASS", "endpoint": "GET /foo"},
             {"status": "FAIL", "endpoint": "POST /bar", "message": "Schema mismatch", "details": "Type diff"}
        ]
    }
    
    path = generate_junit_xml("TestVendor", results, output_path=str(output_file))
    
    assert os.path.exists(path)
    
    tree = ET.parse(path)
    root = tree.getroot()
    
    assert root.get("name") == "DORA Audit - TestVendor"
    assert root.get("tests") == "2"
    assert root.get("failures") == "1"
    
    # Check test suite
    suite = root.find("testsuite")
    assert suite.get("name") == "Drift Check"
    
    # Check cases
    cases = suite.findall("testcase")
    assert len(cases) == 2
    
    # fail case
    fail_case = next(c for c in cases if c.get("name") == "POST /bar")
    failure = fail_case.find("failure")
    assert failure is not None
    assert failure.get("message") == "Schema mismatch"
    assert failure.text == "Type diff"
