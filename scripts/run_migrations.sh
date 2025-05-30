#!/bin/bash

# Database Migration Runner
# Usage: ./run_migrations.sh [migration_number]
# If no migration number is specified, runs all pending migrations

set -e

# Database configuration from environment variables or defaults
DB_HOST="${DB_HOST:-postgis}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-emergency_ops}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-emergency_password}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if PostgreSQL is available
check_postgres() {
    print_status "Checking PostgreSQL connection..."
    
    if ! command -v psql &> /dev/null; then
        print_error "psql command not found. Please install PostgreSQL client."
        exit 1
    fi
    
    if ! PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c '\q' 2>/dev/null; then
        print_error "Cannot connect to PostgreSQL database."
        print_error "Host: $DB_HOST:$DB_PORT, Database: $DB_NAME, User: $DB_USER"
        exit 1
    fi
    
    print_success "PostgreSQL connection successful."
}

# Function to create migrations table if it doesn't exist
create_migrations_table() {
    print_status "Creating migrations tracking table..."
    
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" << 'EOF'
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) UNIQUE NOT NULL,
    applied_at TIMESTAMP DEFAULT NOW(),
    checksum VARCHAR(64)
);
EOF
    
    print_success "Migrations table ready."
}

# Function to get checksum of a file
get_checksum() {
    if command -v sha256sum &> /dev/null; then
        sha256sum "$1" | cut -d' ' -f1
    elif command -v shasum &> /dev/null; then
        shasum -a 256 "$1" | cut -d' ' -f1
    else
        # Fallback to md5 if sha256 not available
        md5sum "$1" | cut -d' ' -f1
    fi
}

# Function to check if migration has been applied
is_migration_applied() {
    local migration_name="$1"
    local count
    
    count=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT COUNT(*) FROM schema_migrations WHERE migration_name = '$migration_name';")
    
    [ "$count" -gt 0 ]
}

# Function to apply a single migration
apply_migration() {
    local migration_file="$1"
    local migration_name
    local checksum
    
    migration_name=$(basename "$migration_file" .sql)
    checksum=$(get_checksum "$migration_file")
    
    print_status "Applying migration: $migration_name"
    
    # Check if already applied
    if is_migration_applied "$migration_name"; then
        print_warning "Migration $migration_name already applied. Skipping."
        return 0
    fi
    
    # Apply the migration
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$migration_file"; then
        # Record successful migration
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c \
            "INSERT INTO schema_migrations (migration_name, checksum) VALUES ('$migration_name', '$checksum');"
        
        print_success "Migration $migration_name applied successfully."
        return 0
    else
        print_error "Migration $migration_name failed!"
        return 1
    fi
}

# Function to run all migrations
run_all_migrations() {
    local migrations_dir="./migrations"
    local migration_files
    
    if [ ! -d "$migrations_dir" ]; then
        print_error "Migrations directory not found: $migrations_dir"
        exit 1
    fi
    
    # Get all .sql files in migrations directory, sorted
    migration_files=$(find "$migrations_dir" -name "*.sql" | sort)
    
    if [ -z "$migration_files" ]; then
        print_warning "No migration files found in $migrations_dir"
        return 0
    fi
    
    print_status "Found migrations to process:"
    echo "$migration_files" | while read -r file; do
        echo "  - $(basename "$file")"
    done
    echo
    
    # Apply each migration
    local success_count=0
    local total_count=0
    
    while IFS= read -r migration_file; do
        total_count=$((total_count + 1))
        if apply_migration "$migration_file"; then
            success_count=$((success_count + 1))
        else
            print_error "Migration failed. Stopping migration process."
            exit 1
        fi
    done <<< "$migration_files"
    
    print_success "Applied $success_count/$total_count migrations successfully."
}

# Function to run specific migration
run_specific_migration() {
    local migration_number="$1"
    local migration_file="./migrations/${migration_number}_*.sql"
    
    # Find the migration file
    migration_file=$(find ./migrations -name "${migration_number}_*.sql" | head -1)
    
    if [ -z "$migration_file" ]; then
        print_error "Migration file not found for number: $migration_number"
        print_error "Looking for pattern: ${migration_number}_*.sql in ./migrations/"
        exit 1
    fi
    
    print_status "Running specific migration: $(basename "$migration_file")"
    apply_migration "$migration_file"
}

# Function to show migration status
show_migration_status() {
    print_status "Migration Status:"
    echo
    
    # Show applied migrations
    print_status "Applied migrations:"
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c \
        "SELECT migration_name, applied_at FROM schema_migrations ORDER BY applied_at;"
    
    echo
    
    # Show pending migrations
    print_status "Pending migrations:"
    local pending_found=false
    
    if [ -d "./migrations" ]; then
        find ./migrations -name "*.sql" | sort | while IFS= read -r migration_file; do
            migration_name=$(basename "$migration_file" .sql)
            if ! is_migration_applied "$migration_name"; then
                echo "  - $migration_name"
                pending_found=true
            fi
        done
        
        if [ "$pending_found" = false ]; then
            echo "  No pending migrations."
        fi
    else
        echo "  Migrations directory not found."
    fi
}

# Main script logic
main() {
    echo "=== Database Migration Runner ==="
    echo "Database: $DB_HOST:$DB_PORT/$DB_NAME"
    echo "User: $DB_USER"
    echo
    
    # Check prerequisites
    check_postgres
    create_migrations_table
    
    # Handle command line arguments
    case "${1:-}" in
        "status")
            show_migration_status
            ;;
        "")
            print_status "Running all pending migrations..."
            run_all_migrations
            ;;
        [0-9]*)
            print_status "Running specific migration: $1"
            run_specific_migration "$1"
            ;;
        *)
            echo "Usage: $0 [migration_number|status]"
            echo
            echo "Examples:"
            echo "  $0           # Run all pending migrations"
            echo "  $0 001       # Run specific migration 001"
            echo "  $0 status    # Show migration status"
            exit 1
            ;;
    esac
    
    echo
    print_success "Migration process completed!"
}

# Run the main function
main "$@"
