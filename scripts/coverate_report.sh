#!/bin/bash

# Generate detailed coverage report
python -m pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
echo "Coverage report generated in htmlcov/index.html"
