#!/bin/bash

echo "🧹 Running code quality checks with Docker..."

# Run flake8 in Docker
echo "Running flake8..."
docker run --rm -v "$(pwd):/app" -w /app python:3.11-slim bash -c "
    pip install --quiet flake8 && \
    echo 'Running flake8 error checks...' && \
    flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics && \
    echo 'Running flake8 style checks...' && \
    flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
"

# Run black check in Docker
echo "Checking code formatting with black..."
docker run --rm -v "$(pwd):/app" -w /app python:3.11-slim bash -c "
    pip install --quiet black && \
    black --check --diff . || echo '❌ Code formatting issues found. Run scripts/format.sh to fix.'
"

# Run isort check in Docker  
echo "Checking import sorting with isort..."
docker run --rm -v "$(pwd):/app" -w /app python:3.11-slim bash -c "
    pip install --quiet isort && \
    isort --check-only --diff . || echo '❌ Import sorting issues found. Run scripts/format.sh to fix.'
"

# Run mypy in Docker
echo "Running mypy type checking..."
docker run --rm -v "$(pwd):/app" -w /app python:3.11-slim bash -c "
    pip install --quiet mypy && \
    mypy . --ignore-missing-imports --no-strict-optional || echo '⚠️ Type checking issues found.'
"

# Run pylint in Docker
echo "Running pylint..."
docker run --rm -v "$(pwd):/app" -w /app python:3.11-slim bash -c "
    pip install --quiet pylint && \
    find . -name '*.py' -not -path './venv/*' -not -path './.venv/*' | xargs pylint --disable=C0114,C0115,C0116,R0903,R0913,R0914 || echo '⚠️ Pylint issues found.'
"

echo "✅ Code quality checks completed!"
