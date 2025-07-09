@echo off
REM Startup script for BrainInk Backend (Windows)

echo 🚀 Starting BrainInk Backend...

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate

REM Install dependencies
echo 📚 Installing dependencies...
pip install -r requirements.txt

REM Initialize roles in database
echo 🏗️ Initializing database roles...
python initialize_roles.py

REM Start the server
echo 🌟 Starting FastAPI server...
echo 📱 Server will be available at: http://localhost:8000
echo 📖 API documentation: http://localhost:8000/docs
echo 🛠️ Admin panel: http://localhost:8000/redoc
echo.
echo Press Ctrl+C to stop the server

uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause
