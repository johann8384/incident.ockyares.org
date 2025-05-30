#!/bin/bash

# Start test database
docker run -d \
  --name test_postgis \
  -e POSTGRES_DB=emergency_ops_test \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=test_password \
  -p 5433:5432 \
  postgis/postgis:15-3.3

# Wait for database to be ready
echo "Waiting for test database..."
sleep 10

# Run tests
export TEST_DB_HOST=localhost
export TEST_DB_PORT=5433
export TEST_DB_USER=postgres
export TEST_DB_PASSWORD=test_password

python -m pytest tests/ -v --cov=app --cov-report=html --cov-report=term

# Cleanup
docker stop test_postgis
docker rm test_postgis
