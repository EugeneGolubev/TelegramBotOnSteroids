#!/bin/bash
cd "$(dirname "$0")"

# Activate your virtualenv
source ./mybotenv/bin/activate

# Run all tests with coverage and proper import path
PYTHONPATH=. pytest --cov=bot --cov-report=term --cov-report=html tests/

