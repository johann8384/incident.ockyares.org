#!/bin/bash
# Script to remove consolidated migration files

echo "Removing consolidated migration files..."

# Remove the migration files that were consolidated into 01_init.sql
rm -f docker/database/init/02_schema.sql
rm -f docker/database/init/03_hospitals.sql  
rm -f docker/database/init/04_units.sql
rm -f docker/database/init/05_unit_status.sql

echo "Migration files removed. Only 01_init.sql remains with the consolidated schema."
echo "Please commit these deletions:"
echo "git add -A"
echo "git commit -m 'Remove consolidated migration files'"
