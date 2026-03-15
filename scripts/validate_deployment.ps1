# =============================================================================
# Docker Pre-Deployment Validation Script (PowerShell)
# Validates Healthcare AI Docker setup before GitHub upload
# =============================================================================

param(
    [switch]$SkipCleanup,
    [switch]$Quick,
    [switch]$Verbose,
    [switch]$ContinueOnError,
    [switch]$Help
)

# Show help
if ($Help) {
    Write-Host "Usage: .\validate_deployment.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -SkipCleanup          Skip the cleanup phase"
    Write-Host "  -Quick                Run only critical validation tests"
    Write-Host "  -Verbose              Show detailed output"
    Write-Host "  -ContinueOnError      Continue running tests even if some fail"
    Write-Host "  -Help                 Display this help message"
    exit 0
}

# Helper functions
function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Cyan
}

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "============================================================"
    Write-Host $Message
    Write-Host "============================================================"
}

# Check if Docker is running
function Test-Docker {
    try {
        docker info | Out-Null
        Write-Success "Docker is running"
        return $true
    } catch {
        Write-ErrorMsg "Docker is not running"
        Write-Host ""
        Write-Host "Please start Docker Desktop"
        return $false
    }
}

# Check if .env file exists
function Test-EnvFile {
    $scriptDir = Split-Path -Parent $PSScriptRoot
    $envPath = Join-Path $scriptDir ".env"
    if (Test-Path $envPath) {
        Write-Success ".env file exists"
        return $true
    } else {
        Write-ErrorMsg ".env file not found"
        Write-Host ""
        Write-Host "Please create .env file from .env.example:"
        Write-Host "  Copy-Item .env.example .env"
        return $false
    }
}

# Cleanup phase
function Invoke-Cleanup {
    Write-Header "Phase 1: Cleanup"
    
    $scriptDir = Split-Path -Parent $PSScriptRoot
    Push-Location $scriptDir
    
    Write-Info "Stopping containers..."
    docker-compose down -v 2>&1 | Out-Null
    
    Write-Info "Removing volumes..."
    docker volume rm healthcare_ai_redis_data 2>$null
    docker volume rm healthcare_ai_pgadmin_data 2>$null
    docker volume rm healthcare_ai_uploads 2>$null
    docker volume rm healthcare_ai_logs 2>$null
    docker volume rm healthcare_ai_whisper_cache 2>$null
    
    Write-Info "Removing images..."
    docker images | Select-String "healthcare_ai" | ForEach-Object {
        $imageId = ($_ -split '\s+')[2]
        docker rmi -f $imageId 2>$null
    }
    
    Write-Info "Removing build cache..."
    docker builder prune -af 2>&1 | Out-Null
    
    Write-Info "Removing network..."
    docker network rm healthcare_ai_network 2>$null
    
    Pop-Location
    
    Write-Success "Cleanup complete"
}

# Build phase
function Invoke-Build {
    Write-Header "Phase 2: Build Validation"
    
    $scriptDir = Split-Path -Parent $PSScriptRoot
    Push-Location $scriptDir
    
    Write-Info "Building Docker images (this may take several minutes)..."
    
    if ($Verbose) {
        docker-compose build --no-cache
    } else {
        docker-compose build --no-cache 2>&1 | Out-Null
    }
    
    Pop-Location
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Build completed successfully"
        return $true
    } else {
        Write-ErrorMsg "Build failed"
        return $false
    }
}

# Startup phase
function Invoke-Startup {
    Write-Header "Phase 3: Startup Validation"
    
    $scriptDir = Split-Path -Parent $PSScriptRoot
    Push-Location $scriptDir
    
    Write-Info "Starting services..."
    docker-compose up -d
    
    Pop-Location
    
    Write-Info "Waiting for services to start (this may take up to 2 minutes)..."
    Start-Sleep -Seconds 30
    
    # Check container status
    $containers = @(
        "healthcare_ai_postgres",
        "healthcare_ai_redis",
        "healthcare_ai_backend",
        "healthcare_ai_stt",
        "healthcare_ai_motion",
        "healthcare_ai_assessment",
        "healthcare_ai_pgadmin"
    )
    
    $allRunning = $true
    foreach ($container in $containers) {
        $status = docker inspect --format='{{.State.Status}}' $container 2>$null
        if ($status -eq "running") {
            Write-Success "$container is running"
        } else {
            Write-ErrorMsg "$container is not running (status: $status)"
            $allRunning = $false
            if (-not $ContinueOnError) {
                return $false
            }
        }
    }
    
    return $allRunning
}

# Health check phase
function Invoke-HealthCheck {
    Write-Header "Phase 4: Health Check Validation"
    
    Write-Info "Waiting for services to be healthy..."
    Start-Sleep -Seconds 30
    
    # Check HTTP health endpoints
    $endpoints = @{
        "http://localhost:8000/health" = "healthcare_ai"
        "http://localhost:8790/health" = "stt_server"
        "http://localhost:8001/health" = "motion_capture"
        "http://localhost:8002/health" = "assessment"
        "http://localhost:5050" = "pgadmin"
    }
    
    $allHealthy = $true
    foreach ($endpoint in $endpoints.Keys) {
        $name = $endpoints[$endpoint]
        $maxRetries = 3
        $success = $false
        
        for ($i = 1; $i -le $maxRetries; $i++) {
            try {
                $response = Invoke-WebRequest -Uri $endpoint -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
                if ($response.StatusCode -eq 200) {
                    Write-Success "$name health check passed"
                    $success = $true
                    break
                }
            } catch {
                if ($i -lt $maxRetries) {
                    Start-Sleep -Seconds 10
                }
            }
        }
        
        if (-not $success) {
            Write-ErrorMsg "$name health check failed"
            $allHealthy = $false
            if (-not $ContinueOnError) {
                Write-Host ""
                Write-Host "Check logs with: docker logs healthcare_ai_$name"
                return $false
            }
        }
    }
    
    return $allHealthy
}

# Database initialization check
function Invoke-DatabaseCheck {
    Write-Header "Phase 5: Database Initialization Check"
    
    Write-Info "Checking database initialization..."
    
    $logs = docker logs healthcare_ai_backend 2>&1 | Select-Object -Last 100
    
    if ($logs -match "Initialization Complete") {
        Write-Success "Database initialized successfully"
    } else {
        Write-Warning "Could not confirm database initialization"
    }
    
    if ($logs -match "(?i)error") {
        Write-Warning "Errors found in logs (check with: docker logs healthcare_ai_backend)"
    }
}

# Main execution
function Main {
    Write-Header "Healthcare AI Docker Pre-Deployment Validation"
    
    # Pre-flight checks
    if (-not (Test-Docker)) {
        exit 1
    }
    
    if (-not (Test-EnvFile)) {
        exit 1
    }
    
    # Run validation phases
    if (-not $SkipCleanup) {
        Invoke-Cleanup
    } else {
        Write-Info "Skipping cleanup phase"
    }
    
    if (-not (Invoke-Build)) {
        exit 1
    }
    
    if (-not (Invoke-Startup)) {
        exit 1
    }
    
    if (-not (Invoke-HealthCheck)) {
        exit 1
    }
    
    if (-not $Quick) {
        Invoke-DatabaseCheck
    }
    
    # Final summary
    Write-Header "Validation Complete"
    Write-Success "All validation tests passed!"
    Write-Host ""
    Write-Host "Your Docker setup is ready for deployment."
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Review the running containers: docker ps"
    Write-Host "  2. Check the logs: docker-compose logs -f"
    Write-Host "  3. Access the application: http://localhost:8000"
    Write-Host "  4. Stop services when done: docker-compose down"
    Write-Host ""
}

# Run main function
Main
