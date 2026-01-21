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

---

## 🏭 Production Ready (CI/CD)

PanDoraSpec is designed for automated pipelines. It returns **Exit Code 1** if any issues are found, blocking deployments if needed.

### 🐳 Docker
Run without installing Python:
```bash
docker run -v $(pwd):/data pandoraspec \
  https://api.example.com/spec.json \
  --output /data/report.pdf
```

### 🐙 GitHub Actions
Add this step to your`.github/workflows/pipeline.yml`:

```yaml
- name: DORA Compliance Audit
  uses: pandoraspec/pandoraspec@v1
  with:
    target: 'https://api.example.com/spec.json'
    vendor: 'MyCompany'
    format: 'junit'
    output: 'dora-results.xml'
```

### 📊 JUnit Reporting
Use `--format junit` to generate standard XML test results that CI systems (Jenkins, GitLab, Azure DevOps) can parse to display test pass/fail trends.

---

## 📦 Publishing

### Automated (Recommended)
This repository uses a **Unified Release Pipeline**.

1. **Update Version**: Open `pyproject.toml` and bump the version (e.g., `version = "0.2.8"`). Commit and push.
2. **Draft Release**:
   - Go to the **Releases** tab in GitHub.
   - Click **Draft a new release**.
   - Create a tag MATCHING the version (e.g., `v0.2.8`).
   - Click **Publish release**.

The workflow will:
1. **Verify** that `pyproject.toml` matches the tag (fails if they differ).
2. **Publish to Docker**: `ghcr.io/.../pandoraspec:v0.2.8`.
3. **Publish to PyPI**: Uploads the package to PyPI (requires Trusted Publishing setup).

### Manual
To publish manually to GitHub Container Registry:

```bash
# Login
echo $CR_PAT | docker login ghcr.io -u USERNAME --password-stdin

# Build
docker build -t ghcr.io/OWNER/pandoraspec:latest .

# Push
docker push ghcr.io/OWNER/pandoraspec:latest
```

  
## 🚀 Usage

Run the audit directly from your terminal.

### Basic Scan
```bash
pandoraspec https://petstore.swagger.io/v2/swagger.json
```

### JSON Output (CI/CD)
To generate a machine-readable JSON report for automated pipelines:
```bash
pandoraspec https://api.example.com/spec.json --format json --output report.json
```
This outputs a file like `report.json` containing the full audit results and compliance score.

**Included CI/CD Resources:**
- [`examples/check_compliance.py`](examples/check_compliance.py): Script to parse the JSON report and exit with error if non-compliant.
- [`examples/github_pipeline.yml`](examples/github_pipeline.yml): Example GitHub Actions workflow.

### With Options
```bash
pandoraspec https://api.example.com/spec.json --vendor "Stripe" --key "sk_live_..."
```

### Local File
```bash
pandoraspec ./openapi.yaml
```

### Override Base URL
If your OpenAPI spec uses variables (e.g. `https://{env}.api.com`) or you want to audit a specific target:
```bash
pandoraspec https://api.example.com/spec.json --base-url https://staging.api.example.com
```

---

## 🏎️ Zero-Config Testing (DORA Compliance)

For standard **DORA compliance**, you simply need to verify that your API implementation matches its specification. **No configuration is required.**

```bash
pandoraspec https://petstore.swagger.io/v2/swagger.json
```

This runs a **fuzzing** audit where random data is generated based on your schema types (e.g., sending random integers for IDs). 
- **Value:** This is sufficient to prove that your API correctly handles unexpected inputs and adheres to the basic contract (e.g., returning 400 Bad Request instead of 500 Server Error).
- **Limitation:** Detailed business logic requiring valid IDs (e.g., `GET /user/{id}` where `{id}` must exist) may return `404 Not Found`. This is acceptable for a compliance scan but may not fully exercise deeper code paths.

---

## 🧠 Advanced Testing with Seed Data

To test **specific business workflows** (e.g., successfully retrieving a user profile), you can provide "Seed Data". This tells PanDoraSpec to use known, valid values instead of random fuzzing data.

```bash
pandoraspec https://petstore.swagger.io/v2/swagger.json --config seed_parameters.yaml
```

### Configuration Hierarchy
You can define seed values at three levels of specificity. The engine resolves values in this order: **Endpoints > Verbs > General**.

```yaml
seed_data:
  # 1. General: Applies to EVERYTHING (path params, query params, headers)
  general:
    username: "test_user"
    limit: 50

  # 2. Verbs: Applies only to specific HTTP methods (Overwrites General)
  verbs:
    POST:
      username: "admin_user" # Creation requests use a different user

  # 3. Endpoints: Applies only to specific routes (Overwrites Everything)
  endpoints:
    /users/me:
      GET:
        limit: 10
```

### 🔗 Dynamic Seed Data (Recursive Chaining)
You can even test **dependency chains** where one endpoint requires data from another. PanDoraSpec handles **recursion** automatically: if Endpoint A needs data from B, and B needs data from C, it will resolve the entire chain in order.

**Supported Features:**
- **Recursive Resolution:** Automatically resolves upstream dependencies (chains of `from_endpoint`).
- **Deep Extraction:** Extract values from nested JSON using dot notation, including list indices (e.g., `data.items.0.id`).
- **Parameter Interpolation:** Use `{param}` in the dependency URL to chain multiple steps.
- **Smart Logging:** Fuzzed values are masked as `random` in logs to keep output clean, while your seeded values are shown clearly.

```yaml
endpoints:
  # Level 1: Get the current user ID
  /user/me:
    GET:
      authorization: "Bearer static-token"

  # Level 2: Use that ID to get their orders
  /users/{userId}/orders:
    GET:
      userId:
        from_endpoint: "GET /user/me"
        extract: "data.id"  # JSON extraction

  # Level 3: Get details of the FIRST order from that list (Recursive!)
  /orders/{orderId}:
    GET:
      orderId:
        # This calls Level 2 first (which calls Level 1), then extracts the first order ID
        from_endpoint: "GET /users/{userId}/orders"
        extract: "data.items.0.id" # Supports list index '0'
```
### 🧙 Configuration Wizard
Get started quickly by generating a configuration file interactively:
```bash
pandoraspec init
```
This will guide you through creating a `pandoraspec.yaml` file with your target URL, vendor name, and seed data templates.

### Configuration File (`pandoraspec.yaml`)
You can store your settings in a YAML file:

```yaml
target: "https://petstore.swagger.io/v2/swagger.json"
vendor: "MyVendor"
api_key: "my-secret-key"
seed_data:
  user_id: 123
```

**Precedence Rules:**
1.  **CLI Arguments** (Highest Priority)
2.  **Configuration File**
3.  **Defaults** (Lowest Priority)

Example:
`pandoraspec --vendor "CLI Override" --config pandoraspec.yaml` will use the target from YAML but the vendor "CLI Override".
### ✅ Validate Configuration
Ensure your configuration file is valid before running an audit:
```bash
pandoraspec validate --config pandoraspec.yaml
```
---

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
Alternatively, use `--format json` to get a structured JSON object for:
- CI/CD Gates (e.g., fail build if `is_compliant` is false).
- Custom Dashboards.
- Archival purposes.

---

## 📄 License

MIT
