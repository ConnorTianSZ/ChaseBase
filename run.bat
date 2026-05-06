@echo off
cd /d "%~dp0"

if not exist .env (
    copy .env.example .env
    echo [ChaseBase] .env created. Please fill in ANTHROPIC_API_KEY and restart.
    notepad .env
    exit /b
)

if not exist .venv (
    echo [ChaseBase] Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate

echo [ChaseBase] Installing dependencies...
pip install -r requirements.txt -q

echo [ChaseBase] Starting server at http://127.0.0.1:8000
start "" http://127.0.0.1:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

pause
