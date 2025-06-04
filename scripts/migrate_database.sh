#!/bin/bash

# Database Migration Script
# Runs SQL migration files against the database

set -e

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-emergency_ops}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-emergency_password}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🗄️  Emergency Incident Database Migration${NC}"
echo "=========================================="

# Check if PostgreSQL client is available
if ! command -v psql &> /dev/null; then
    echo -e "${RED}❌ psql command not found. Please install PostgreSQL client.${NC}"
    exit 1
fi

# Test database connection
echo -e "${YELLOW}📡 Testing database connection...${NC}"
export PGPASSWORD="$DB_PASSWORD"

if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${RED}❌ Cannot connect to database. Please check your configuration.${NC}"
    echo "Host: $DB_HOST:$DB_PORT"
    echo "Database: $DB_NAME"
    echo "User: $DB_USER"
    exit 1
fi

echo -e "${GREEN}✅ Database connection successful${NC}"

# Create migrations table if it doesn't exist
echo -e "${YELLOW}📋 Creating migrations tracking table...${NC}"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
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
    ALREADY_APPLIED=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT COUNT(*) FROM schema_migrations WHERE filename = '$filename';
    " | xargs)
    
    if [ "$ALREADY_APPLIED" -gt 0 ]; then
        echo -e "${YELLOW}⏭️  Skipping $filename (already applied)${NC}"
        ((SKIPPED_COUNT++))
        continue
    fi
    
    echo -e "${YELLOW}🔄 Applying migration: $filename${NC}"
    
    # Run the migration
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$migration_file" > /dev/null 2>&1; then
        # Record successful migration
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
            INSERT INTO schema_migrations (filename) VALUES ('$filename');
        " > /dev/null
        
        echo -e "${GREEN}✅ Successfully applied: $filename${NC}"
        ((APPLIED_COUNT++))
    else
        echo -e "${RED}❌ Failed to apply migration: $filename${NC}"
        echo -e "${RED}   Check the SQL syntax and database logs${NC}"
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
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT filename, applied_at 
FROM schema_migrations 
ORDER BY applied_at;
"

unset PGPASSWORD
