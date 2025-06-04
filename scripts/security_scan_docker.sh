#!/bin/bash
set -e

echo "🔒 Running comprehensive security scan in Docker..."

# Create reports directory
mkdir -p security-reports

# 1. Python security scans (run in security container)
echo "🐍 Running Python security scans..."
bandit -r . -f json -o /reports/bandit-report.json || true
bandit -r . -f txt

safety check --json --output /reports/safety-report.json || true
safety check

pip-audit --format=json --output=/reports/pip-audit-report.json || true
pip-audit

# 2. Docker security scan
echo "🐳 Running Docker security scans..."

# Build main app image for scanning
docker build -t emergency-incident-app:security-test .

# Hadolint (Dockerfile linting)
hadolint /app/Dockerfile > /reports/hadolint-report.txt || true

# Trivy (container vulnerability scanning)
trivy image --format json --output /reports/trivy-report.json \
    emergency-incident-app:security-test || true

# 3. Secret scan
echo "🔍 Scanning for secrets..."
gitleaks detect --source /app --report-format json \
    --report-path /reports/gitleaks-report.json || true

# 4. Semgrep static analysis
echo "🔍 Running Semgrep static analysis..."
semgrep --config=auto --json --output=/reports/semgrep-report.json /app || true

echo "✅ Security scan complete!"
echo "📁 Reports will be extracted to security-reports/ directory"
ls -la /reports/
