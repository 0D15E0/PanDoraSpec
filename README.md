# PanDoraSpec

**The Open DORA Compliance Engine for OpenAPI Specs.**

PanDoraSpec is a CLI tool that performs deep technical due diligence on APIs to verify compliance with **DORA (Digital Operational Resilience Act)** requirements. It compares OpenAPI/Swagger specifications against real-world implementation to detect schema drift, resilience gaps, and security issues.

---

## 📦 Installation

```bash
pip install pandoraspec
```

### System Requirements
The PDF report generation requires `weasyprint`, which depends on **Pango**.

**macOS:**
```bash
brew install pango
```

**Debian / Ubuntu:**
```bash
sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0
```

## 🛠️ Development Setup

To run the CLI locally without reinstalling after every change:

1. **Clone & CD**:
```bash
git clone ...
cd pandoraspec
```

2. **Create & Activate Virtual Environment**:
It's recommended to use a virtual environment to keep dependencies isolated.
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Editable Install**:
```bash
pip install -e .
```
This links the `pandoraspec` command directly to your source code. Any changes you make will be reflected immediately.

## 🚀 Usage

Run the audit directly from your terminal.

### Basic Scan
```bash
pandoraspec https://petstore.swagger.io/v2/swagger.json
```

### With Options
```bash
pandoraspec https://api.example.com/spec.json --vendor "Stripe" --key "sk_live_..."
```

### Local File
```bash
pandoraspec ./openapi.yaml
```

---

## 🛡️ What It Checks

### Module A: The Integrity Test (Drift)
Checks if your API implementation matches your documentation.
- **Why?** DORA requires you to monitor if the service effectively supports your critical functions. If the API behaves differently than documented, it's a risk.

### Module B: The Resilience Test
Stress tests the API to ensure it handles invalid inputs gracefully (`4xx` vs `5xx`).
- **Why?** DORA Article 25 calls for "Digital operational resilience testing".

### Module C: Security Hygiene
Checks for common security headers and configurations.

### Module D: The Report
Generates a PDF report: **"DORA ICT Third-Party Technical Risk Assessment"**.

---

## 📄 License

MIT
