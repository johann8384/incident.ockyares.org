#!/bin/bash

echo "Applying database migrations..."

# Get the database container name
DB_CONTAINER="emergency_postgis"

# Check if container is running
if ! docker ps --format "table {{.Names}}" | grep -q "$DB_CONTAINER"; then
    echo "Database container $DB_CONTAINER is not running!"
    echo "Start it with: docker-compose up -d postgis"
    exit 1
fi

# Apply each migration in order
MIGRATIONS_DIR="docker/database/migrations"

echo "Found migrations:"
ls -la $MIGRATIONS_DIR/*.sql

for migration in $MIGRATIONS_DIR/*.sql; do
    migration_name=$(basename "$migration")
    echo "Applying migration: $migration_name"
    
    docker-compose exec -T postgis psql -U postgres -d emergency_ops -f "/docker-entrypoint-initdb.d/migrations/$migration_name"
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully applied $migration_name"
    else
        echo "❌ Failed to apply $migration_name"
        exit 1
    fi
done

echo "🎉 All migrations applied successfully!"
