@echo off
title Nexus AI v2 - API + Dashboard
cd /d "%~dp0"
echo Starting FastAPI on http://127.0.0.1:8000 ...
start "Nexus API" cmd /k "python src\api.py"
timeout /t 2 /nobreak >nul
echo Starting Vite on http://127.0.0.1:5173 ...
cd frontend
npm run dev
