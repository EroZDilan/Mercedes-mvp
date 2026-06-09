# Arrancar Stock Chatbot MVP en Windows
# Ejecutar desde la raiz del proyecto: .\scripts\start_windows.ps1
param(
    [string]$BackendPort = "8000",
    [string]$FrontendPort = "3000"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "=== Stock Chatbot MVP - Windows ===" -ForegroundColor Cyan
Write-Host "Raiz del proyecto: $root"

# Verificar venv
$venvPython = "$root\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
    python -m venv "$root\.venv"
    Write-Host "Instalando dependencias..." -ForegroundColor Yellow
    & "$root\.venv\Scripts\pip.exe" install -r "$root\backend\requirements.txt"
}

# Verificar node_modules del frontend
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "Instalando dependencias del frontend..." -ForegroundColor Yellow
    Set-Location "$root\frontend"
    npm install
    Set-Location $root
}

# Verificar .env
if (-not (Test-Path "$root\.env")) {
    Write-Host "AVISO: No se encontro .env, copiando .env.example..." -ForegroundColor Yellow
    Copy-Item "$root\.env.example" "$root\.env"
    Write-Host "Edita $root\.env antes de continuar (ALLOWED_ORIGIN, etc.)" -ForegroundColor Red
    Read-Host "Presiona Enter cuando hayas configurado el .env"
}

# Inicializar DB si no existe
$dbFile = "$root\stock_chatbot.db"
if (-not (Test-Path $dbFile)) {
    Write-Host "Inicializando base de datos..." -ForegroundColor Yellow
    Set-Location $root
    & "$root\.venv\Scripts\python.exe" -m backend.seed
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: El seed fallo. Revisa los logs." -ForegroundColor Red
        exit 1
    }
    Write-Host "Base de datos lista." -ForegroundColor Green
}

# Arrancar backend en ventana nueva
Write-Host "Arrancando backend en http://localhost:$BackendPort ..." -ForegroundColor Green
$backendCmd = "cd '$root'; .venv\Scripts\Activate.ps1; python -m uvicorn 'backend.main:app' --host 0.0.0.0 --port $BackendPort --reload; Read-Host 'Backend detenido. Enter para cerrar'"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

# Esperar a que el backend levante
Write-Host "Esperando que el backend levante..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Arrancar frontend en esta ventana
Write-Host "Arrancando frontend en http://localhost:$FrontendPort ..." -ForegroundColor Green
$env:BACKEND_URL = "http://localhost:$BackendPort"
Set-Location "$root\frontend"
npm run dev
