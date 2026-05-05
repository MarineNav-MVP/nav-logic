@echo off
title MarineNav System Stopper
chcp 65001 >nul
echo ==========================================
echo Stopping MarineNav System...
echo ==========================================

echo [1/2] Stopping Python processes...
taskkill /F /IM python.exe /T >nul 2>&1

echo [2/2] Stopping Mosquitto Docker container...
docker stop mosquitto_marinenav >nul 2>&1

echo ==========================================
echo System stopped.
echo ==========================================
pause
