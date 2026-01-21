import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any


def generate_junit_xml(vendor: str, results: dict[str, list[dict[str, Any]]], output_path: str | None = None) -> str:
    """
    Generates a JUnit XML report for CI/CD integration.
    """
    testsuites = ET.Element("testsuites", name=f"DORA Audit - {vendor}")

    total_tests = 0
    total_failures = 0

    for module_name, checks in results.items():
        # Clean up module name for display
        display_name = module_name.replace("_", " ").title()

        testsuite = ET.SubElement(testsuites, "testsuite", name=display_name)

        failures = 0
        tests = 0

        for check in checks:
            tests += 1
            status = check.get("status", "UNKNOWN")

            # Use 'endpoint' or 'check_id' or generic name
            case_name = check.get("endpoint", "General Check")
            msg = check.get("message", "")

            testcase = ET.SubElement(testsuite, "testcase", name=case_name, classname=module_name)

            if status != "PASS":
                failures += 1
                failure = ET.SubElement(testcase, "failure", message=msg)
                failure.text = str(check.get("details", ""))

        testsuite.set("tests", str(tests))
        testsuite.set("failures", str(failures))

        total_tests += tests
        total_failures += failures

    # Set globals
    testsuites.set("tests", str(total_tests))
    testsuites.set("failures", str(total_failures))
    testsuites.set("time", "0.0") # We don't track time yet

    tree = ET.ElementTree(testsuites)

    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"reports/dora_junit_{timestamp}.xml"

    # Ensure reports dir exists
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return output_path
