@echo off
rem Starts the backend with this project's own Python, whichever venv is active.
cd /d "%~dp0backend"
if "%~1"=="" (set PORT=8000) else (set PORT=%~1)
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --reload-dir app --port %PORT%
