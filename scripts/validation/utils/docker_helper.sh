#!/bin/bash
# =============================================================================
# Docker Helper Functions
# Provides Docker interface functions for validation system
# =============================================================================

# Stop all containers from healthcare_ai_network
docker_stop_containers() {
    echo "Stopping containers..."
    cd healthcare_ai_live2d_unified 2>/dev/null || true
    docker-compose down -v 2>&1
    cd .. 2>/dev/null || true
}

# Build Docker images with no cache
docker_build_images() {
    echo "Building Docker images..."
    cd healthcare_ai_live2d_unified 2>/dev/null || cd .
    docker-compose build --no-cache 2>&1
    local result=$?
    cd .. 2>/dev/null || true
    return $result
}

# Start Docker services
docker_start_services() {
    echo "Starting Docker services..."
    cd healthcare_ai_live2d_unified 2>/dev/null || cd .
    docker-compose up -d 2>&1
    local result=$?
    cd .. 2>/dev/null || true
    return $result
}

# Get container status
docker_get_container_status() {
    local container_name=$1
    docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null
}

# Get container logs
docker_get_container_logs() {
    local container_name=$1
    local lines=${2:-100}
    docker logs --tail "$lines" "$container_name" 2>&1
}

# Get volume info
docker_get_volume_info() {
    local volume_name=$1
    docker volume inspect "$volume_name" 2>/dev/null
}

# Get resource stats
docker_get_resource_stats() {
    local container_name=$1
    docker stats --no-stream --format "{{.CPUPerc}},{{.MemUsage}}" "$container_name" 2>/dev/null
}

# Remove all healthcare_ai artifacts
docker_cleanup_all() {
    echo "Cleaning up Docker artifacts..."
    
    # Stop and remove containers
    cd healthcare_ai_live2d_unified 2>/dev/null || cd .
    docker-compose down -v 2>&1 || true
    cd .. 2>/dev/null || true
    
    # Remove volumes
    docker volume rm healthcare_ai_redis_data 2>/dev/null || true
    docker volume rm healthcare_ai_pgadmin_data 2>/dev/null || true
    docker volume rm healthcare_ai_uploads 2>/dev/null || true
    docker volume rm healthcare_ai_logs 2>/dev/null || true
    docker volume rm healthcare_ai_whisper_cache 2>/dev/null || true
    
    # Remove images
    docker images | grep healthcare_ai | awk '{print $3}' | xargs -r docker rmi -f 2>/dev/null || true
    
    # Remove build cache
    docker builder prune -af 2>&1 || true
    
    # Remove network
    docker network rm healthcare_ai_network 2>/dev/null || true
    
    echo "Cleanup complete"
}

# Check if Docker is running
docker_is_running() {
    docker info >/dev/null 2>&1
    return $?
}

# Wait for container to be healthy
docker_wait_for_healthy() {
    local container_name=$1
    local timeout=${2:-30}
    local elapsed=0
    
    while [ $elapsed -lt $timeout ]; do
        local health=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null)
        if [ "$health" = "healthy" ]; then
            return 0
        fi
        
        local status=$(docker_get_container_status "$container_name")
        if [ "$status" = "running" ] && [ -z "$health" ]; then
            # Container is running but has no health check defined
            return 0
        fi
        
        sleep 2
        elapsed=$((elapsed + 2))
    done
    
    return 1
}
