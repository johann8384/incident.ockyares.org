#!/bin/bash
set -e

echo "🧪 Running tests in Docker containers..."

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

# Clean up any existing test containers
$DOCKER_COMPOSE -f docker-compose.test.yml down -v 2>/dev/null || true

# Build and run tests
$DOCKER_COMPOSE -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from test_runner

# Copy coverage report out of container
echo "📊 Extracting coverage report..."
$DOCKER_COMPOSE -f docker-compose.test.yml run --rm test_runner cp -r htmlcov /tmp/ 2>/dev/null || echo "Coverage report extraction skipped"

# Clean up
$DOCKER_COMPOSE -f docker-compose.test.yml down -v

echo "✅ Tests completed!"
echo "📊 Coverage report: htmlcov/index.html"
