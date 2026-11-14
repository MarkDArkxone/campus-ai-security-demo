@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo Campus AI Security Demo
echo Installing Python dependencies...
echo ========================================
echo.
python -m pip install -r requirements.txt
echo.
echo ========================================
echo Dependency installation finished.
echo If there is an error above, please check
echo Python version, pip, and network connection.
echo ========================================
pause
