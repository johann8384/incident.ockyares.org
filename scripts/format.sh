#!/bin/bash

echo "🎨 Formatting code with Docker..."

# Create a temporary container with Python and formatting tools
echo "Running black formatter..."
docker run --rm -v "$(pwd):/app" -w /app python:3.11-slim bash -c "
    pip install --quiet black isort && \
    black . && \
    echo '✅ Black formatting completed'
"

echo "Sorting imports with isort..."
docker run --rm -v "$(pwd):/app" -w /app python:3.11-slim bash -c "
    pip install --quiet isort && \
    isort . && \
    echo '✅ Import sorting completed'
"

echo "✅ Code formatting completed!"
