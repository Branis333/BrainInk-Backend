#!/bin/bash
# Startup script for BrainInk Backend

echo "🚀 Starting BrainInk Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Initialize roles in database
echo "🏗️ Initializing database roles..."
python initialize_roles.py

# Start the server
echo "🌟 Starting FastAPI server..."
echo "📱 Server will be available at: http://localhost:8000"
echo "📖 API documentation: http://localhost:8000/docs"
echo "🛠️ Admin panel: http://localhost:8000/redoc"
echo ""
echo "Press Ctrl+C to stop the server"

uvicorn main:app --reload --host 0.0.0.0 --port 8000
