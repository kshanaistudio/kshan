@echo off
title KSHAN Face Recognition Studio
cd /d "d:\Face recognition"
echo Starting KSHAN Face Recognition Django Server...
start "" python manage.py runserver 8000
timeout /t 3 /nobreak >nul
echo Opening Desktop App Window...
start msedge --app=http://127.0.0.1:8000/
exit
