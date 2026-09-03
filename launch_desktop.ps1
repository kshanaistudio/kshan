Write-Host "Starting KSHAN Face Recognition Server..." -ForegroundColor Cyan
Set-Location -Path "d:\Face recognition"

# Start Django server in a background window
Start-Process -FilePath "python" -ArgumentList "manage.py runserver 8000" -WindowStyle Hidden

Start-Sleep -Seconds 3

# Launch in App Window mode (no address bar / tabs)
if (Get-Command msedge.exe -ErrorAction SilentlyContinue) {
    Start-Process "msedge.exe" "--app=http://127.0.0.1:8000/"
} elseif (Get-Command chrome.exe -ErrorAction SilentlyContinue) {
    Start-Process "chrome.exe" "--app=http://127.0.0.1:8000/"
} else {
    Start-Process "http://127.0.0.1:8000/"
}
