@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo Campus AI Security Demo
echo Starting FastAPI service...
echo ========================================
echo.
python run.py
echo.
echo ========================================
echo Program exited. If there is an error above,
echo please check Python version and dependencies.
echo ========================================
pause
