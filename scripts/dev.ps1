# Launches the backend (uvicorn, :8000) and frontend (vite, :5173) in separate windows.
$root = Split-Path $PSScriptRoot -Parent

Start-Process -FilePath "$root\backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:create_app", "--factory", "--port", "8000" `
    -WorkingDirectory "$root\backend"

Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", "npm run dev" `
    -WorkingDirectory "$root\frontend"

Write-Host "Backend: http://localhost:8000  Frontend: http://localhost:5173"
