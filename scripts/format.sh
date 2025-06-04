#!/bin/bash
set -e

echo "🎨 Formatting code..."

# Install formatting tools
pip install black isort

echo "Running black formatter..."
black .

echo "Sorting imports with isort..."
isort .

echo "✅ Code formatting completed!"