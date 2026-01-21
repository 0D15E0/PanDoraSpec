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

### Override Base URL
If your OpenAPI spec uses variables (e.g. `https://{env}.api.com`) or you want to audit a specific target:
```bash
pandoraspec https://api.example.com/spec.json --base-url https://staging.api.example.com
```

### JSON Output (CI/CD)
To generate a machine-readable JSON report for automated pipelines:
```bash
pandoraspec https://api.example.com/spec.json --format json --output report.json
```
This outputs a file like `report.json` containing the full audit results and compliance score.

---

## ⚙️ Configuration

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
# Avoid False Positives in DLP by allowing support emails
dlp_allowed_domains:
  - "mycompany.com"
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

## 🧪 Testing Modes

### 🏎️ Zero-Config Testing (Compliance)
For standard **DORA compliance**, you simply need to verify that your API implementation matches its specification. **No configuration is required.**

```bash
pandoraspec https://petstore.swagger.io/v2/swagger.json
```
This runs a **fuzzing** audit where random data is generated based on your schema types.

### 🧠 Advanced Testing (Seed Data)
To test **specific business workflows** (e.g., successfully retrieving a user profile), you can provide "Seed Data". This tells PanDoraSpec to use known, valid values instead of random fuzzing data.

```bash
pandoraspec https://petstore.swagger.io/v2/swagger.json --config seed_parameters.yaml
```

> [!NOTE]
> Any parameters **NOT** explicitly defined in your seed data will continue to be **fuzzed** with random values. This ensures that you still get the benefit of stress testing on non-critical fields while controlling the critical business logic.

#### Configuration Hierarchy
The engine resolves values in this order: **Endpoints > Verbs > General**.

```yaml
seed_data:
  # 1. General: Applies to EVERYTHING (path params, query params, headers)
  general:
    username: "test_user"

  # 2. Verbs: Applies only to specific HTTP methods
  verbs:
    POST:
      username: "admin_user"

  # 3. Endpoints: Applies only to specific routes
  endpoints:
    /users/me:
      GET:
        limit: 10
```

#### 🔗 Dynamic Seed Data (Recursive Chaining)
You can even test **dependency chains** where one endpoint requires data from another.

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
        extract: "data.id"
```

---

## 🛡️ What It Checks

### Module A: The Integrity Test (Drift)
Checks if your API implementation matches your documentation.
- **Why?** DORA requires you to monitor if the service effectively supports your critical functions.

### Module B: The Resilience Test
Stress tests the API to ensure it handles invalid inputs gracefully (`4xx` vs `5xx`).
- **Why?** DORA Article 25 calls for "Digital operational resilience testing".

### Module C: Security Hygiene & DLP
Checked for:
- Security headers (HSTS, CSP, etc.)
- Auth enforcement on sensitive endpoints.
- **Data Leakage Prevention (DLP)**: Scans responses for PII (Emails, SSNs, Credit Cards) and Secrets (AWS Keys, Private Keys).

### Module D: The Report
Generates a PDF report: **"DORA ICT Third-Party Technical Risk Assessment"**.

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

## 🛠️ Development

### Local Setup
To run the CLI locally without reinstalling after every change:

1. **Clone & CD**:
```bash
git clone ...
cd pandoraspec
```

2. **Create & Activate Virtual Environment**:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Editable Install**:
```bash
pip install -e .
```

### 📦 Publishing (Release Flow)
This repository uses a **Unified Release Pipeline**.

1. **Update Version**: Open `pyproject.toml` and bump the version (e.g., `version = "0.2.8"`). Commit and push.
2. **Draft Release**:
   - Go to the **Releases** tab in GitHub.
   - Click **Draft a new release**.
   - Create a tag MATCHING the version (e.g., `v0.2.8`).
   - Click **Publish release**.

The workflow will verify version consistency and automatically publish to **Docker (GHCR)** and **PyPI**.

---

## 📄 License

MIT
