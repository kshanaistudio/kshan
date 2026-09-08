@echo off
title KSHAN AI Studio - Cloudflare Tunnel Launcher
cd /d "%~dp0"

echo ======================================================================
echo   🚀 KSHAN AI Photo Suite — Cloudflare Tunnel Launcher
echo ======================================================================
echo.

:: Check if cloudflared.exe exists, download if missing
if not exist "cloudflared.exe" (
    echo [1/3] Downloading official Cloudflare Tunnel client (cloudflared.exe)...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile 'cloudflared.exe'"
    echo    Done!
) else (
    echo [1/3] cloudflared.exe is already present.
)

:: Ensure Django is running on port 8000
echo.
echo [2/3] Starting Cloudflare Tunnel pointing to http://127.0.0.1:8000...
echo.
echo ----------------------------------------------------------------------
echo Look for the public URL below ending with .trycloudflare.com:
echo ----------------------------------------------------------------------
echo.

cloudflared.exe tunnel --url http://127.0.0.1:8000

pause
