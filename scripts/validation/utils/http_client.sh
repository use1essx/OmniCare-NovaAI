#!/bin/bash
# =============================================================================
# HTTP Client Functions
# Provides health check and API testing functions
# =============================================================================

# Check health endpoint with retry logic
check_health_endpoint() {
    local url=$1
    local max_retries=${2:-3}
    local retry_delay=${3:-10}
    
    for i in $(seq 1 $max_retries); do
        if command -v curl >/dev/null 2>&1; then
            response=$(curl -sf -w "\n%{http_code}" "$url" 2>/dev/null)
            status_code=$(echo "$response" | tail -n1)
            
            if [ "$status_code" = "200" ]; then
                return 0
            fi
        fi
        
        if [ $i -lt $max_retries ]; then
            sleep $retry_delay
        fi
    done
    
    return 1
}

# HTTP GET request
http_get() {
    local url=$1
    if command -v curl >/dev/null 2>&1; then
        curl -sf "$url" 2>/dev/null
    fi
}

# HTTP POST request
http_post() {
    local url=$1
    local data=$2
    if command -v curl >/dev/null 2>&1; then
        curl -sf -X POST -H "Content-Type: application/json" -d "$data" "$url" 2>/dev/null
    fi
}

# Measure response time
measure_response_time() {
    local url=$1
    if command -v curl >/dev/null 2>&1; then
        curl -sf -w "%{time_total}" -o /dev/null "$url" 2>/dev/null
    fi
}
