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

# Extract coverage reports from Docker volume
echo "📊 Extracting coverage reports..."
docker run --rm -v incidentockyaresorg_test_coverage:/src -v $(pwd):/dest alpine sh -c "
    cp -r /src/* /dest/ 2>/dev/null || echo 'No coverage files to copy'
"

# Clean up
$DOCKER_COMPOSE -f docker-compose.test.yml down -v

echo "✅ Tests completed!"
if [ -f "coverage.xml" ] || [ -d "htmlcov" ]; then
    echo "📊 Coverage reports extracted successfully!"
    [ -d "htmlcov" ] && echo "📊 HTML coverage: htmlcov/index.html"
    [ -f "coverage.xml" ] && echo "📊 XML coverage: coverage.xml"
else
    echo "⚠️  Coverage reports not found"
fi
