#!/bin/bash

# Database Migration Script
# Runs SQL migration files against the database using Docker Compose

set -e

# Configuration
CONTAINER_NAME="${CONTAINER_NAME:-emergency_postgis}"
DB_NAME="${DB_NAME:-emergency_ops}"
DB_USER="${DB_USER:-postgres}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🗄️  Emergency Incident Database Migration${NC}"
echo "=========================================="

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ docker-compose command not found. Please install Docker Compose.${NC}"
    exit 1
fi

# Check if PostgreSQL container is running
echo -e "${YELLOW}📡 Checking if database container is running...${NC}"
if ! docker-compose ps | grep -q "$CONTAINER_NAME.*Up"; then
    echo -e "${RED}❌ Database container '$CONTAINER_NAME' is not running.${NC}"
    echo -e "${YELLOW}💡 Try: docker-compose up -d postgis${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Database container is running${NC}"

# Test database connection
echo -e "${YELLOW}📡 Testing database connection...${NC}"
if ! docker-compose exec -T "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${RED}❌ Cannot connect to database inside container.${NC}"
    echo -e "${YELLOW}💡 Container may still be starting up. Wait a moment and try again.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Database connection successful${NC}"

# Create migrations table if it doesn't exist
echo -e "${YELLOW}📋 Creating migrations tracking table...${NC}"
docker-compose exec -T "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) UNIQUE NOT NULL,
    applied_at TIMESTAMP DEFAULT NOW()
);
" > /dev/null

# Find migration files
MIGRATION_DIR="docker/database/init"
if [ ! -d "$MIGRATION_DIR" ]; then
    echo -e "${RED}❌ Migration directory not found: $MIGRATION_DIR${NC}"
    exit 1
fi

# Get list of SQL files in order
MIGRATION_FILES=($(ls "$MIGRATION_DIR"/*.sql 2>/dev/null | sort))

if [ ${#MIGRATION_FILES[@]} -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No migration files found in $MIGRATION_DIR${NC}"
    exit 0
fi

echo -e "${YELLOW}📁 Found ${#MIGRATION_FILES[@]} migration files${NC}"

# Run migrations
APPLIED_COUNT=0
SKIPPED_COUNT=0

for migration_file in "${MIGRATION_FILES[@]}"; do
    filename=$(basename "$migration_file")
    
    # Check if migration has already been applied
    ALREADY_APPLIED=$(docker-compose exec -T "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT COUNT(*) FROM schema_migrations WHERE filename = '$filename';
    " | xargs)
    
    if [ "$ALREADY_APPLIED" -gt 0 ]; then
        echo -e "${YELLOW}⏭️  Skipping $filename (already applied)${NC}"
        ((SKIPPED_COUNT++))
        continue
    fi
    
    echo -e "${YELLOW}🔄 Applying migration: $filename${NC}"
    
    # Run the migration by copying file to container and executing
    if cat "$migration_file" | docker-compose exec -T "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; then
        # Record successful migration
        docker-compose exec -T "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "
            INSERT INTO schema_migrations (filename) VALUES ('$filename');
        " > /dev/null
        
        echo -e "${GREEN}✅ Successfully applied: $filename${NC}"
        ((APPLIED_COUNT++))
    else
        echo -e "${RED}❌ Failed to apply migration: $filename${NC}"
        echo -e "${RED}   Check the SQL syntax and container logs${NC}"
        echo -e "${YELLOW}💡 Try: docker-compose logs $CONTAINER_NAME${NC}"
        exit 1
    fi
done

# Summary
echo ""
echo -e "${GREEN}🎉 Migration completed!${NC}"
echo -e "${GREEN}   Applied: $APPLIED_COUNT migrations${NC}"
echo -e "${YELLOW}   Skipped: $SKIPPED_COUNT migrations${NC}"

# Show current migration status
echo ""
echo -e "${YELLOW}📊 Current migration status:${NC}"
docker-compose exec -T "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT filename, applied_at 
FROM schema_migrations 
ORDER BY applied_at;
"
