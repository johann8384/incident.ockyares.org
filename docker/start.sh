#!/bin/bash
set -e

echo "Starting Emergency Incident Management System..."

# Create necessary directories
mkdir -p logs docker/nginx/ssl

# Start services
docker-compose up -d database

echo "Waiting for database to be ready..."
sleep 10

# Start application and nginx
docker-compose up -d app nginx

echo "Services started successfully!"
echo "Application available at: http://localhost"
echo "Database available at: localhost:5432"

docker-compose ps