# =============================================================================
# Healthcare AI - Quick Start Script (Windows PowerShell)
# =============================================================================

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Healthcare AI - Quick Start" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host ""

# Ask user what they want to do
Write-Host "What would you like to do?"
Write-Host "1) Clean build (removes all data, rebuilds from scratch)"
Write-Host "2) Regular start (uses existing data)"
Write-Host "3) Stop all containers"
Write-Host ""
$choice = Read-Host "Enter choice [1-3]"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "🧹 Cleaning up old containers and volumes..." -ForegroundColor Yellow
        docker-compose down -v
        
        Write-Host ""
        Write-Host "🔨 Building Docker images (this may take 10-15 minutes)..." -ForegroundColor Yellow
        docker-compose build --no-cache
        
        Write-Host ""
        Write-Host "🚀 Starting all services..." -ForegroundColor Yellow
        docker-compose up -d
        
        Write-Host ""
        Write-Host "⏳ Waiting for services to initialize (30 seconds)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 30
    }
    "2" {
        Write-Host ""
        Write-Host "🚀 Starting all services..." -ForegroundColor Yellow
        docker-compose up -d
        
        Write-Host ""
        Write-Host "⏳ Waiting for services to initialize (10 seconds)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }
    "3" {
        Write-Host ""
        Write-Host "🛑 Stopping all containers..." -ForegroundColor Yellow
        docker-compose down
        Write-Host "✅ All containers stopped" -ForegroundColor Green
        exit 0
    }
    default {
        Write-Host "Invalid choice. Exiting." -ForegroundColor Red
        exit 1
    }
}

# Check status
Write-Host ""
Write-Host "📊 Container Status:" -ForegroundColor Cyan
docker-compose ps

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "✅ Healthcare AI is ready!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Access points:"
Write-Host "  • Main App:    http://localhost:8000"
Write-Host "  • KB Sandbox:  http://localhost:8000/admin/kb-sandbox"
Write-Host "  • pgAdmin:     http://localhost:5050"
Write-Host "  • Health:      http://localhost:8000/health"
Write-Host ""
Write-Host "View logs:"
Write-Host "  docker-compose logs -f"
Write-Host ""
Write-Host "Stop services:"
Write-Host "  docker-compose down"
Write-Host ""
