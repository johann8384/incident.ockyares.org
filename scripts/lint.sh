#!/bin/bash
set -e

echo "🧹 Running code quality checks..."

# Install linting tools
pip install flake8 black isort mypy pylint

echo "Running flake8..."
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

echo "Checking code formatting with black..."
black --check --diff . || echo "❌ Code formatting issues found. Run 'black .' to fix."

echo "Checking import sorting with isort..."
isort --check-only --diff . || echo "❌ Import sorting issues found. Run 'isort .' to fix."

echo "Running mypy type checking..."
mypy . --ignore-missing-imports --no-strict-optional || echo "⚠️ Type checking issues found."

echo "Running pylint..."
pylint **/*.py --disable=C0114,C0115,C0116,R0903,R0913,R0914 || echo "⚠️ Pylint issues found."

echo "✅ Code quality checks completed!"