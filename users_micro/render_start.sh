#!/bin/bash

# Render deployment startup script
echo "🚀 Starting BrainInk Backend on Render..."

# Set production environment
export PYTHONUNBUFFERED=1
export PYTHONPATH=$PYTHONPATH:.

# Initialize database if needed
echo "📊 Initializing database..."
python startup.py || echo "⚠️ Database initialization had issues but continuing..."

# Start the server for production
echo "🌟 Starting FastAPI server on Render..."
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --log-level info