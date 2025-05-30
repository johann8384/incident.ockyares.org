#!/bin/bash

# Create necessary directories
mkdir -p docker/database/init docker/database/backups docker/static/qr_codes docker/logs docker/geoserver/workspaces docker/geoserver/styles

# Set external IP for QField access
export EXTERNAL_IP=$(curl -s ifconfig.me)

# Start services
docker-compose up -d

# Wait for services to be healthy
echo "Waiting for services to start..."
docker-compose exec postgis pg_isready -U postgres -d emergency_ops
docker-compose exec incident_app curl -f http://localhost:5000/health

echo "Services started successfully!"
echo "Application: http://localhost"
echo "GeoServer: http://localhost:8080/geoserver"
echo "PostgREST API: http://localhost:3000"
echo "External IP for QField: $EXTERNAL_IP"
