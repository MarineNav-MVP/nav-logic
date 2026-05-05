@echo off
title MarineNav System Launcher
chcp 65001 >nul
set ROOT_DIR=%~dp0
echo ==========================================
echo Starting MarineNav System...
echo ==========================================

echo [1/4] Checking Mosquitto (MQTT Broker)...
docker stop mosquitto_marinenav >nul 2>&1
docker rm mosquitto_marinenav >nul 2>&1
echo    Starting Mosquitto with local config...
docker run -d --name mosquitto_marinenav -p 1883:1883 -p 9001:9001 -v "%ROOT_DIR%sensor-bridge\mosquitto.conf:/mosquitto/config/mosquitto.conf" eclipse-mosquitto:latest
if %ERRORLEVEL% NEQ 0 (
    echo FAILED to start Docker. Is Docker Desktop running?
    pause
    exit /b
)

echo [2/4] Checking Python Virtual Environment...
if exist "%ROOT_DIR%venv\Scripts\activate.bat" goto VENV_FOUND

echo    Virtual environment not found. Creating 'venv'...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python not found in PATH. Please install Python 3.10+
    pause
    exit /b
)
python -m venv "%ROOT_DIR%venv"
echo    Installing dependencies (this may take a minute)...
"%ROOT_DIR%venv\Scripts\python.exe" -m pip install --upgrade pip
"%ROOT_DIR%venv\Scripts\pip.exe" install -r "%ROOT_DIR%requirements.txt"
echo    Dependencies installed!
goto START_SERVICES

:VENV_FOUND
echo    Virtual environment found.

:START_SERVICES
echo [3/4] Launching Core Services...
echo    Starting Sensor Bridge...
start "Sensor Bridge" /d "%ROOT_DIR%sensor-bridge" "%ROOT_DIR%venv\Scripts\python.exe" main.py
echo    Starting Vision Node...
start "Vision Node" /d "%ROOT_DIR%cv-core" "%ROOT_DIR%venv\Scripts\python.exe" scripts\mqtt_node.py
echo    Starting Fusion Core...
start "Fusion Core" /d "%ROOT_DIR%fusion-core" "%ROOT_DIR%venv\Scripts\python.exe" main.py
echo    Starting NavLogic Brain...
start "NavLogic Brain" /d "%ROOT_DIR%nav-logic" "%ROOT_DIR%venv\Scripts\python.exe" main.py

echo [4/4] Starting Web Dashboard Server...
start "Web Server" /d "%ROOT_DIR%sensor-bridge\web" "%ROOT_DIR%venv\Scripts\python.exe" -m http.server 8001

echo [*] Waiting for services to initialize...
timeout /t 5 /nobreak >nul

echo Opening Web Dashboard in default browser...
start http://localhost:8001

echo ==========================================
echo System is running! 
echo Close the newly opened terminal windows to stop the services.
echo ==========================================
pause
