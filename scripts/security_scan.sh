#!/bin/bash
set -e

echo "🔒 Running comprehensive security scan..."

# Create reports directory
mkdir -p security-reports

# Install security tools
echo "Installing security tools..."
pip install bandit safety pip-audit

# 1. Python security scan
echo "🐍 Running Python security scans..."
bandit -r . -f json -o security-reports/bandit-report.json || true
bandit -r . -f txt

safety check --json --output security-reports/safety-report.json || true
safety check

pip-audit --format=json --output=security-reports/pip-audit-report.json || true
pip-audit

# 2. Docker security scan
echo "🐳 Running Docker security scans..."
docker build -t emergency-incident-app:security-test .

# Hadolint
if command -v hadolint &> /dev/null; then
    hadolint Dockerfile > security-reports/hadolint-report.txt || true
else
    echo "Hadolint not found, skipping Dockerfile lint"
fi

# Trivy (if available)
if command -v trivy &> /dev/null; then
    trivy image --format json --output security-reports/trivy-report.json \
        emergency-incident-app:security-test || true
else
    echo "Trivy not found, skipping container vulnerability scan"
fi

# 3. Secret scan
echo "🔍 Scanning for secrets..."
if command -v gitleaks &> /dev/null; then
    gitleaks detect --source . --report-format json \
        --report-path security-reports/gitleaks-report.json || true
else
    echo "Gitleaks not found, skipping secret scan"
fi

echo "✅ Security scan complete!"
echo "📁 Reports saved in security-reports/ directory"
ls -la security-reports/