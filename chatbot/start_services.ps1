# Start Qdrant and Redis as background processes
# Run this once before starting the API server

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Qdrant
$qdrantExe  = Join-Path $projectRoot "qdrant\qdrant.exe"
$qdrantData = Join-Path $projectRoot "qdrant\storage"
New-Item -ItemType Directory -Force -Path $qdrantData | Out-Null

Write-Host "Starting Qdrant on port 6333..." -ForegroundColor Cyan
$qdrant = Start-Process -FilePath $qdrantExe `
    -WorkingDirectory (Join-Path $projectRoot "qdrant") `
    -WindowStyle Minimized `
    -PassThru
Write-Host "Qdrant PID: $($qdrant.Id)"

Start-Sleep -Seconds 2

# Redis
$redisExe = Join-Path $projectRoot "redis\redis-server.exe"

Write-Host "Starting Redis on port 6379..." -ForegroundColor Cyan
$redis = Start-Process -FilePath $redisExe `
    -WindowStyle Minimized `
    -PassThru
Write-Host "Redis PID: $($redis.Id)"

Start-Sleep -Seconds 1

# Health check
Write-Host ""
Write-Host "Checking services..." -ForegroundColor Yellow

try {
    $resp = Invoke-WebRequest -Uri "http://localhost:6333/healthz" -UseBasicParsing -TimeoutSec 5
    Write-Host "Qdrant: OK (status $($resp.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "Qdrant: not responding yet - give it a few seconds" -ForegroundColor Yellow
}

$redisCli = Join-Path $projectRoot "redis\redis-cli.exe"
$ping = & $redisCli PING 2>&1
if ($ping -eq "PONG") {
    Write-Host "Redis:  OK (PONG)" -ForegroundColor Green
} else {
    Write-Host "Redis:  not responding yet" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Services started. Now run the API:" -ForegroundColor Green
Write-Host "  venv\Scripts\uvicorn main:app --reload --port 8000" -ForegroundColor White
Write-Host ""
Write-Host "To stop services later, run:" -ForegroundColor DarkGray
Write-Host "  Stop-Process -Name qdrant,redis-server -ErrorAction SilentlyContinue" -ForegroundColor DarkGray
