#!/bin/bash
set -e

echo "🧪 Running tests in Docker containers..."

# Clean up any existing test containers
docker-compose -f docker-compose.test.yml down -v 2>/dev/null || true

# Build and run tests
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from test_runner

# Copy coverage report out of container
echo "📊 Extracting coverage report..."
docker-compose -f docker-compose.test.yml run --rm test_runner cp -r htmlcov /tmp/
docker cp $(docker-compose -f docker-compose.test.yml ps -q test_runner):/tmp/htmlcov ./htmlcov 2>/dev/null || echo "Coverage report already extracted"

# Clean up
docker-compose -f docker-compose.test.yml down -v

echo "✅ Tests completed!"
echo "📊 Coverage report: htmlcov/index.html"
