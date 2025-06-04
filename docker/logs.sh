#!/bin/bash
echo "=== Application Logs ==="
docker-compose logs app

echo "
=== Database Logs ==="
docker-compose logs database

echo "
=== Nginx Logs ==="
docker-compose logs nginx