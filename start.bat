@echo off
title Smart Hospital Asset Tracking System (RTLS)
color 0B

echo ===============================================================================
echo            SMART HOSPITAL ASSET TRACKING SYSTEM (RTLS)
echo      Real-Time Location Tracking Using IoT and Computer Networks
echo ===============================================================================
echo.

:: Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.9+ from https://www.python.org/ and check "Add to PATH".
    pause
    exit /b 1
)

echo [*] Python detected.
echo [*] Checking dependencies...
pip install -r requirements.txt --quiet

echo.
echo ===============================================================================
echo [*] Starting Embedded MQTT Broker (RFC 3.1.1 on TCP/1883)...
echo [*] Starting Real-Time BLE Physics & Location Engine...
echo [*] Starting Flask Hospital Web Server...
echo.
echo [*] Live Dashboard      : http://127.0.0.1:5000/
echo [*] Hospital Floor Map  : http://127.0.0.1:5000/map
echo [*] Manage Movement     : http://127.0.0.1:5000/movement
echo [*] Equipment Requests  : http://127.0.0.1:5000/requests
echo [*] Add New Equipment   : http://127.0.0.1:5000/equipment/add
echo [*] Maintenance Mgmt   : http://127.0.0.1:5000/maintenance
echo [*] Notifications       : http://127.0.0.1:5000/notifications
echo [*] Reports & Analytics : http://127.0.0.1:5000/reports
echo [*] User Login & Roles  : http://127.0.0.1:5000/login
echo [*] Network Architecture: http://127.0.0.1:5000/network
echo [*] Asset Inventory     : http://127.0.0.1:5000/assets
echo ===============================================================================
echo.
echo Opening browser in 2 seconds...
start "" timeout /t 2 >nul & start http://127.0.0.1:5000/

python app.py
pause

