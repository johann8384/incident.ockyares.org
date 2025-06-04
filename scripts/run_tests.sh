#!/bin/bash
set -e

echo "🧪 Starting test run..."

# Start test database if not running
if ! docker ps | grep -q test_postgis; then
    echo "Starting test database..."
    docker run -d \
        --name test_postgis \
        -e POSTGRES_DB=emergency_ops_test \
        -e POSTGRES_USER=postgres \
        -e POSTGRES_PASSWORD=test_password \
        -p 5433:5432 \
        postgis/postgis:15-3.3
    
    echo "Waiting for database to be ready..."
    sleep 15
fi

# Set environment variables
export TEST_DB_HOST=localhost
export TEST_DB_PORT=5433
export TEST_DB_USER=postgres
export TEST_DB_PASSWORD=test_password
export FLASK_ENV=testing

# Install test dependencies
pip install -r test-requirements.txt

# Run tests
echo "Running tests with coverage..."
python -m pytest tests/ -v --cov=app --cov=models --cov-report=html --cov-report=term-missing

echo "✅ Tests completed!"
echo "📊 Coverage report: htmlcov/index.html"

# Cleanup
echo "Cleaning up test database..."
docker stop test_postgis || true
docker rm test_postgis || true