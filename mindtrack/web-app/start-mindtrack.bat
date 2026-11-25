@echo off
title MindTrack Launcher
echo Starting MindTrack Backend (FastAPI on port 8080)...
start "MindTrack Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload"
timeout /t 3 /nobreak >nul
echo Starting MindTrack Frontend (Vite on port 5173)...
start "MindTrack Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
timeout /t 4 /nobreak >nul
echo Opening MindTrack in browser at http://localhost:5173...
start http://localhost:5173
