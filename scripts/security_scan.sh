#!/bin/bash

echo "🔒 Running comprehensive security scan in Docker..."

# Detect which docker compose command to use
if command -v "docker-compose" &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "❌ Neither docker-compose nor docker compose found!"
    exit 1
fi

echo "Using: $DOCKER_COMPOSE"

# Create reports directory
mkdir -p security-reports

# Clean up any existing containers
$DOCKER_COMPOSE -f docker-compose.security.yml down 2>/dev/null || true

# Run security scanning in container (don't fail on scan findings)
echo "🔍 Starting security scan container..."
$DOCKER_COMPOSE -f docker-compose.security.yml up --build

# Always clean up regardless of scan results
$DOCKER_COMPOSE -f docker-compose.security.yml down 2>/dev/null || true

echo "✅ Security scan complete!"
echo "📁 Reports saved in security-reports/ directory:"
ls -la security-reports/ 2>/dev/null || echo "No reports directory found"

# Generate summary if script exists
if [ -f "scripts/security_summary.py" ]; then
    echo "📊 Generating security summary..."
    python scripts/security_summary.py || echo "Failed to generate summary"
fi

echo "🔒 Security scanning finished - check reports for findings"
