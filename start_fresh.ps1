# =============================================================================
# Healthcare AI V2 - Fresh Start Script (PowerShell)
# =============================================================================
# This script completely removes old Docker containers, volumes, and images,
# then rebuilds and starts everything fresh.
#
# Usage: Right-click and select "Run with PowerShell" or run: .\start_fresh.ps1
# =============================================================================

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Healthcare AI V2 - Fresh Start" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "🔍 Checking Docker status..." -ForegroundColor Yellow
try {
    docker info | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host ""
Write-Host "⚠️  WARNING: This will completely remove:" -ForegroundColor Yellow
Write-Host "   - All containers" -ForegroundColor Yellow
Write-Host "   - All volumes (database data will be lost)" -ForegroundColor Yellow
Write-Host "   - All images" -ForegroundColor Yellow
Write-Host "   - All build cache" -ForegroundColor Yellow
Write-Host ""

$confirmation = Read-Host "Are you sure you want to continue? (yes/no)"
if ($confirmation -ne "yes") {
    Write-Host "❌ Operation cancelled" -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 0
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Step 1: Stopping all containers..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
docker-compose down -v
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Containers stopped and volumes removed" -ForegroundColor Green
} else {
    Write-Host "⚠️  Warning: Some containers may not have been stopped" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Step 2: Removing all images..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
$images = docker images -q
if ($images) {
    docker rmi -f $images
    Write-Host "✅ All images removed" -ForegroundColor Green
} else {
    Write-Host "ℹ️  No images to remove" -ForegroundColor Blue
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Step 3: Cleaning Docker system..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
docker system prune -af --volumes
Write-Host "✅ Docker system cleaned" -ForegroundColor Green

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Step 4: Cleaning local data folders..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
if (Test-Path "data/vector_store") {
    Remove-Item -Recurse -Force "data/vector_store/*" -ErrorAction SilentlyContinue
    Write-Host "✅ Vector store cleaned" -ForegroundColor Green
}
if (Test-Path "data/uploads") {
    Remove-Item -Recurse -Force "data/uploads/*" -ErrorAction SilentlyContinue
    Write-Host "✅ Uploads folder cleaned" -ForegroundColor Green
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Step 5: Building images (this may take 10-15 minutes)..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
docker-compose build --no-cache
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Images built successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Build failed. Please check the error messages above." -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Step 6: Starting services..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
docker-compose up -d
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Services started successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to start services. Please check the error messages above." -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Step 7: Waiting for services to be healthy..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "⏳ Waiting 30 seconds for services to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Step 8: Checking service status..." -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
docker-compose ps

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "✅ Fresh Start Complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Access your application at:" -ForegroundColor Cyan
Write-Host "   - API: http://localhost:8000" -ForegroundColor White
Write-Host "   - API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "   - PgAdmin: http://localhost:5050" -ForegroundColor White
Write-Host ""
Write-Host "🔐 Default credentials:" -ForegroundColor Cyan
Write-Host "   - Username: admin" -ForegroundColor White
Write-Host "   - Password: admin" -ForegroundColor White
Write-Host ""
Write-Host "📋 To view logs, run:" -ForegroundColor Cyan
Write-Host "   docker-compose logs -f healthcare_ai" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
