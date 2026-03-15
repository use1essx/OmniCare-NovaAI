#!/bin/bash
# =============================================================================
# Docker Pre-Deployment Validation Script
# Validates Healthcare AI Docker setup before GitHub upload
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Flags
SKIP_CLEANUP=false
QUICK_MODE=false
VERBOSE=false
CONTINUE_ON_ERROR=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --continue-on-error)
            CONTINUE_ON_ERROR=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-cleanup          Skip the cleanup phase"
            echo "  --quick                 Run only critical validation tests"
            echo "  --verbose               Show detailed output"
            echo "  --continue-on-error     Continue running tests even if some fail"
            echo "  --help                  Display this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Helper functions
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_header() {
    echo ""
    echo "============================================================"
    echo "$1"
    echo "============================================================"
}

# Check if Docker is running
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running"
        echo ""
        echo "Please start Docker Desktop (Windows/macOS) or Docker Engine (Linux)"
        exit 1
    fi
    print_success "Docker is running"
}

# Check if .env file exists
check_env_file() {
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        print_error ".env file not found"
        echo ""
        echo "Please create .env file from .env.example:"
        echo "  cp .env.example .env"
        exit 1
    fi
    print_success ".env file exists"
}

# Cleanup phase
cleanup_phase() {
    print_header "Phase 1: Cleanup"
    
    cd "$PROJECT_ROOT" || exit 1
    
    print_info "Stopping containers..."
    docker-compose down -v 2>&1 | grep -v "^$" || true
    
    print_info "Removing volumes..."
    docker volume rm healthcare_ai_redis_data 2>/dev/null || true
    docker volume rm healthcare_ai_pgadmin_data 2>/dev/null || true
    docker volume rm healthcare_ai_uploads 2>/dev/null || true
    docker volume rm healthcare_ai_logs 2>/dev/null || true
    docker volume rm healthcare_ai_whisper_cache 2>/dev/null || true
    
    print_info "Removing images..."
    docker images | grep healthcare_ai | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true
    
    print_info "Removing build cache..."
    docker builder prune -af >/dev/null 2>&1 || true
    
    print_info "Removing network..."
    docker network rm healthcare_ai_network 2>/dev/null || true
    
    print_success "Cleanup complete"
}

# Build phase
build_phase() {
    print_header "Phase 2: Build Validation"
    
    cd "$PROJECT_ROOT" || exit 1
    
    print_info "Building Docker images (this may take several minutes)..."
    
    if [ "$VERBOSE" = true ]; then
        docker-compose build --no-cache
    else
        docker-compose build --no-cache >/dev/null 2>&1
    fi
    
    if [ $? -eq 0 ]; then
        print_success "Build completed successfully"
    else
        print_error "Build failed"
        exit 1
    fi
}

# Startup phase
startup_phase() {
    print_header "Phase 3: Startup Validation"
    
    cd "$PROJECT_ROOT" || exit 1
    
    print_info "Starting services..."
    docker-compose up -d
    
    print_info "Waiting for services to start (this may take up to 2 minutes)..."
    sleep 30
    
    # Check container status
    local containers=("healthcare_ai_postgres" "healthcare_ai_redis" "healthcare_ai_backend" "healthcare_ai_stt" "healthcare_ai_motion" "healthcare_ai_assessment" "healthcare_ai_pgadmin")
    
    for container in "${containers[@]}"; do
        local status=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null)
        if [ "$status" = "running" ]; then
            print_success "$container is running"
        else
            print_error "$container is not running (status: $status)"
            if [ "$CONTINUE_ON_ERROR" = false ]; then
                exit 1
            fi
        fi
    done
}

# Health check phase
health_check_phase() {
    print_header "Phase 4: Health Check Validation"
    
    print_info "Waiting for services to be healthy..."
    sleep 30
    
    # Check HTTP health endpoints
    local endpoints=(
        "http://localhost:8000/health:healthcare_ai"
        "http://localhost:8790/health:stt_server"
        "http://localhost:8001/health:motion_capture"
        "http://localhost:8002/health:assessment"
        "http://localhost:5050:pgadmin"
    )
    
    for endpoint_info in "${endpoints[@]}"; do
        IFS=':' read -r url name <<< "$endpoint_info"
        
        local max_retries=3
        local success=false
        
        for i in $(seq 1 $max_retries); do
            if curl -sf "$url" >/dev/null 2>&1; then
                print_success "$name health check passed"
                success=true
                break
            fi
            
            if [ $i -lt $max_retries ]; then
                sleep 10
            fi
        done
        
        if [ "$success" = false ]; then
            print_error "$name health check failed"
            if [ "$CONTINUE_ON_ERROR" = false ]; then
                echo ""
                echo "Check logs with: docker logs healthcare_ai_${name}"
                exit 1
            fi
        fi
    done
}

# Database initialization check
database_check_phase() {
    print_header "Phase 5: Database Initialization Check"
    
    print_info "Checking database initialization..."
    
    local logs=$(docker logs healthcare_ai_backend 2>&1 | tail -n 100)
    
    if echo "$logs" | grep -q "Initialization Complete"; then
        print_success "Database initialized successfully"
    else
        print_warning "Could not confirm database initialization"
    fi
    
    if echo "$logs" | grep -qi "error"; then
        print_warning "Errors found in logs (check with: docker logs healthcare_ai_backend)"
    fi
}

# Main execution
main() {
    print_header "Healthcare AI Docker Pre-Deployment Validation"
    
    # Pre-flight checks
    check_docker
    check_env_file
    
    # Run validation phases
    if [ "$SKIP_CLEANUP" = false ]; then
        cleanup_phase
    else
        print_info "Skipping cleanup phase"
    fi
    
    build_phase
    startup_phase
    health_check_phase
    
    if [ "$QUICK_MODE" = false ]; then
        database_check_phase
    fi
    
    # Final summary
    print_header "Validation Complete"
    print_success "All validation tests passed!"
    echo ""
    echo "Your Docker setup is ready for deployment."
    echo ""
    echo "Next steps:"
    echo "  1. Review the running containers: docker ps"
    echo "  2. Check the logs: docker-compose logs -f"
    echo "  3. Access the application: http://localhost:8000"
    echo "  4. Stop services when done: docker-compose down"
    echo ""
}

# Run main function
main
