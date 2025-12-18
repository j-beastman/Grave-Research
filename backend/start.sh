#!/bin/bash

# Exit on error
set -e

# Run the application
# We use the PORT environment variable provided by Railway
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
