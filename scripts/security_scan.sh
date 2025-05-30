#!/bin/bash

echo "🔒 Running comprehensive security scan..."

# Create reports directory
mkdir -p security-reports

# 1. Python security scan
echo "🐍 Running Python security scans..."
bandit -r . -f json -o security-reports/bandit-report.json
safety check --json --output security-reports/safety-report.json
pip-audit --format=json --output=security-reports/pip-audit-report.json

# 2. Docker security scan
echo "🐳 Running Docker security scans..."
docker build -t emergency-incident-app:security-test .

# Hadolint
docker run --rm -i hadolint/hadolint < Dockerfile > security-reports/hadolint-report.txt

# Trivy
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/security-reports:/reports \
  aquasec/trivy image --format json --output /reports/trivy-report.json \
  emergency-incident-app:security-test

# Dockle
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  goodwithtech/dockle:latest \
  --format json --output security-reports/dockle-report.json \
  emergency-incident-app:security-test

# 3. Secret scan
echo "🔍 Scanning for secrets..."
if command -v gitleaks &> /dev/null; then
    gitleaks detect --source . --report-format json --report-path security-reports/gitleaks-report.json
fi

# 4. Generate summary report
echo "📊 Generating security summary..."
python scripts/security_summary.py

echo "✅ Security scan complete! Check security-reports/ directory for detailed results."
