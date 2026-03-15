# Docker Pre-Deployment Validation

Automated validation system for the Healthcare AI Docker setup. This ensures your multi-container environment can be cleanly rebuilt and deployed without errors before uploading to GitHub.

## Features

- **Automated Cleanup**: Removes old Docker artifacts for clean rebuilds
- **Build Validation**: Verifies all images build successfully
- **Startup Validation**: Checks all containers start in correct order
- **Health Checks**: Validates all services are operational
- **Database Initialization**: Confirms migrations and seed data load correctly
- **Cross-Platform**: Works on Windows (PowerShell), macOS, and Linux (Bash)
- **Multiple Modes**: Quick mode, verbose output, continue-on-error

## Prerequisites

- Docker 20.10+ or Docker Desktop
- docker-compose 2.0+
- bash 4.0+ (Linux/macOS/WSL) or PowerShell 5.1+ (Windows)
- curl (Linux/macOS) - built-in on most systems

## Quick Start

### Linux / macOS / WSL

```bash
# Make script executable (first time only)
chmod +x scripts/validate_deployment.sh

# Run validation
./scripts/validate_deployment.sh
```

### Windows PowerShell

```powershell
# Run validation
.\scripts\validate_deployment.ps1
```

## Usage

### Basic Usage

```bash
# Full validation (recommended before GitHub upload)
./scripts/validate_deployment.sh

# Skip cleanup for faster testing
./scripts/validate_deployment.sh --skip-cleanup

# Quick mode (critical tests only)
./scripts/validate_deployment.sh --quick

# Verbose output (show all command output)
./scripts/validate_deployment.sh --verbose

# Continue on error (run all tests even if some fail)
./scripts/validate_deployment.sh --continue-on-error
```

### PowerShell Usage

```powershell
# Full validation
.\scripts\validate_deployment.ps1

# With options
.\scripts\validate_deployment.ps1 -SkipCleanup
.\scripts\validate_deployment.ps1 -Quick
.\scripts\validate_deployment.ps1 -Verbose
.\scripts\validate_deployment.ps1 -ContinueOnError
```

## Validation Phases

The validation system runs through these phases:

1. **Cleanup Phase** (optional with `--skip-cleanup`)
   - Stops all running containers
   - Removes containers, volumes, images, networks
   - Clears build cache
   - Ensures clean environment

2. **Build Validation**
   - Builds all Docker images from scratch
   - Verifies no build errors
   - Reports build time and image sizes

3. **Startup Validation**
   - Starts all services with docker-compose
   - Waits for containers to reach running status
   - Verifies correct startup order

4. **Health Check Validation**
   - Tests all HTTP health endpoints
   - Retries failed checks (up to 3 times)
   - Confirms all services are operational

5. **Database Initialization Check** (skipped in quick mode)
   - Verifies database migrations ran successfully
   - Checks seed data loaded correctly
   - Scans logs for initialization errors

## Exit Codes

- `0`: All validation tests passed
- `1`: Validation failed (check error messages)

## Troubleshooting

### Docker Not Running

**Error**: "Docker is not running"

**Solution**:
- Windows/macOS: Start Docker Desktop
- Linux: `sudo systemctl start docker`

### Port Already in Use

**Error**: Container fails to start due to port conflict

**Solution**:
```bash
# Find process using the port (example for port 8000)
# Linux/macOS:
lsof -i :8000

# Windows:
netstat -ano | findstr :8000

# Stop the process or change the port in .env
```

### Build Failures

**Error**: Docker image build fails

**Solution**:
1. Check your internet connection (for pulling base images)
2. Clear Docker cache: `docker builder prune -af`
3. Check requirements.txt for dependency conflicts
4. Run with `--verbose` to see detailed build output

### Health Check Failures

**Error**: Service health check fails

**Solution**:
```bash
# Check container logs
docker logs healthcare_ai_backend
docker logs healthcare_ai_postgres

# Check container status
docker ps -a

# Verify .env configuration
cat .env | grep DATABASE_PASSWORD
```

### Insufficient Memory

**Error**: Containers crash or fail to start

**Solution**:
- Increase Docker memory limit in Docker Desktop settings
- Recommended: At least 8GB for all services
- Close other applications to free memory

### Low Disk Space

**Error**: Build fails due to disk space

**Solution**:
```bash
# Clean Docker system
docker system prune -af --volumes

# Remove old images
docker image prune -af

# Check disk usage
df -h  # Linux/macOS
Get-PSDrive  # Windows PowerShell
```

## Configuration

### Environment Variables

The validation system reads configuration from your `.env` file. Ensure these are set:

- `DATABASE_NAME`
- `DATABASE_USER`
- `DATABASE_PASSWORD`
- `SECRET_KEY`
- `PGADMIN_EMAIL`
- `PGADMIN_PASSWORD`

### Validation Configuration

Advanced configuration is available in:
- `scripts/validation/config/validation_config.json` - Timeouts, retries, thresholds
- `scripts/validation/config/error_patterns.json` - Error detection patterns

## Best Practices

### Before GitHub Upload

1. Run full validation: `./scripts/validate_deployment.sh`
2. Verify all tests pass
3. Check for warnings in output
4. Review container logs if needed
5. Stop services: `docker-compose down`

### During Development

1. Use `--skip-cleanup` for faster iterations
2. Use `--quick` for rapid testing
3. Use `--verbose` when debugging issues
4. Use `--continue-on-error` to see all issues at once

### In CI/CD Pipelines

See `.github/workflows/docker-validation.yml` for GitHub Actions example.

## What Gets Validated

✅ Docker is running and accessible
✅ .env file exists with required variables
✅ All Docker images build successfully
✅ All containers start without errors
✅ All services pass health checks
✅ Database migrations run successfully
✅ Seed data loads correctly
✅ No critical errors in logs

## What Doesn't Get Validated

❌ AWS credentials (not tested to avoid costs)
❌ External API integrations
❌ Production-specific configurations
❌ SSL/HTTPS setup
❌ Load testing or performance

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review container logs: `docker logs <container_name>`
3. Run with `--verbose` for detailed output
4. Check Docker Desktop status and settings

## Files Created

The validation system creates these files:
- `scripts/reports/` - Validation reports (timestamped)
- Container logs are not saved (use `docker logs` to view)

## Cleanup

To remove validation artifacts:

```bash
# Stop all containers
docker-compose down -v

# Remove all Docker artifacts
docker system prune -af --volumes

# Remove validation reports
rm -rf scripts/reports/*
```

## Version

Version: 1.0.0
Last Updated: March 2026

---

**Built for Healthcare AI Platform** 🏥
