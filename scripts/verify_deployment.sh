#!/bin/bash
# =============================================================================
# Healthcare AI - Deployment Verification Script
# =============================================================================
# 
# This script verifies that all services are properly initialized and ready
# after deployment.
#
# Usage:
#   ./scripts/verify_deployment.sh
#
# Exit codes:
#   0 - All services healthy
#   1 - Some services unhealthy
#   2 - Critical services failed
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
MAX_RETRIES=30
RETRY_DELAY=2

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Healthcare AI - Deployment Verification               ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to check if service is responding
check_service() {
    local service_name=$1
    local url=$2
    local max_wait=${3:-30}
    
    echo -n "Checking ${service_name}... "
    
    for i in $(seq 1 $max_wait); do
        if curl -sf "${url}" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Ready${NC}"
            return 0
        fi
        sleep $RETRY_DELAY
    done
    
    echo -e "${RED}❌ Failed${NC}"
    return 1
}

# Function to check deployment endpoint
check_deployment() {
    local response=$(curl -sf "${BACKEND_URL}/api/v1/health/deployment" 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to connect to deployment endpoint${NC}"
        return 2
    fi
    
    echo "$response"
}

# Track failures
CRITICAL_FAILURES=0
WARNINGS=0

echo -e "${BLUE}🔍 Checking Infrastructure Services...${NC}"
echo ""

# Check PostgreSQL
if check_service "PostgreSQL" "${BACKEND_URL}/health/ready" 30; then
    :
else
    echo -e "${RED}   PostgreSQL is not ready${NC}"
    CRITICAL_FAILURES=$((CRITICAL_FAILURES + 1))
fi

# Check Redis
echo -n "Checking Redis... "
if docker exec healthcare_ai_redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ready${NC}"
else
    echo -e "${YELLOW}⚠️  Not responding (optional)${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""
echo -e "${BLUE}🔍 Checking Main Application...${NC}"
echo ""

# Check main backend
if check_service "Main Backend" "${BACKEND_URL}/health" 30; then
    :
else
    echo -e "${RED}   Main backend is not ready${NC}"
    CRITICAL_FAILURES=$((CRITICAL_FAILURES + 1))
fi

echo ""
echo -e "${BLUE}🔍 Checking Microservices...${NC}"
echo ""

# Check STT Service
echo -n "Checking STT Service... "
if curl -sf "http://localhost:8790/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ready${NC}"
else
    echo -e "${YELLOW}⚠️  Not responding (optional)${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check Motion Capture
echo -n "Checking Motion Capture... "
if curl -sf "http://localhost:8001/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ready${NC}"
else
    echo -e "${YELLOW}⚠️  Not responding (optional)${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

# Check Assessment Service
echo -n "Checking Assessment Service... "
if curl -sf "http://localhost:8002/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ready${NC}"
else
    echo -e "${YELLOW}⚠️  Not responding (optional)${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

echo ""
echo -e "${BLUE}🔍 Checking Database Initialization...${NC}"
echo ""

# Get comprehensive deployment status
DEPLOYMENT_STATUS=$(check_deployment)

if [ $? -eq 0 ]; then
    # Parse JSON response
    OVERALL_STATUS=$(echo "$DEPLOYMENT_STATUS" | grep -o '"overall_status":"[^"]*"' | cut -d'"' -f4)
    CHECKS_PASSED=$(echo "$DEPLOYMENT_STATUS" | grep -o '"checks_passed":[0-9]*' | cut -d':' -f2)
    CHECKS_TOTAL=$(echo "$DEPLOYMENT_STATUS" | grep -o '"checks_total":[0-9]*' | cut -d':' -f2)
    
    # Database tables
    echo -n "Database Tables... "
    if echo "$DEPLOYMENT_STATUS" | grep -q '"database_tables".*"status":"✅"'; then
        TABLE_COUNT=$(echo "$DEPLOYMENT_STATUS" | grep -o '"database_tables".*"count":[0-9]*' | grep -o '[0-9]*' | head -1)
        echo -e "${GREEN}✅ ${TABLE_COUNT} tables created${NC}"
    else
        echo -e "${RED}❌ Tables not created${NC}"
        CRITICAL_FAILURES=$((CRITICAL_FAILURES + 1))
    fi
    
    # Super admin
    echo -n "Super Admin User... "
    if echo "$DEPLOYMENT_STATUS" | grep -q '"super_admin".*"status":"✅"'; then
        echo -e "${GREEN}✅ Created${NC}"
    else
        echo -e "${RED}❌ Not created${NC}"
        CRITICAL_FAILURES=$((CRITICAL_FAILURES + 1))
    fi
    
    # Organizations
    echo -n "Organizations... "
    if echo "$DEPLOYMENT_STATUS" | grep -q '"organizations".*"status":"✅"'; then
        ORG_COUNT=$(echo "$DEPLOYMENT_STATUS" | grep -o '"organizations".*"count":[0-9]*' | grep -o '[0-9]*' | head -1)
        echo -e "${GREEN}✅ ${ORG_COUNT} seeded${NC}"
    else
        echo -e "${YELLOW}⚠️  Not fully seeded${NC}"
        WARNINGS=$((WARNINGS + 1))
    fi
    
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}                    DEPLOYMENT SUMMARY                      ${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    if [ "$OVERALL_STATUS" = "healthy" ]; then
        echo -e "${GREEN}🎉 Status: HEALTHY${NC}"
        echo -e "${GREEN}   All critical services are ready!${NC}"
        echo ""
        echo -e "   Checks Passed: ${CHECKS_PASSED}/${CHECKS_TOTAL}"
        echo ""
        echo -e "${GREEN}✅ Deployment successful!${NC}"
        echo ""
        echo -e "   You can now access:"
        echo -e "   • Live2D Chat: ${BACKEND_URL}/live2d"
        echo -e "   • Admin Dashboard: ${BACKEND_URL}/admin/dashboard"
        echo -e "   • API Docs: ${BACKEND_URL}/docs"
        echo ""
        echo -e "   Default credentials:"
        echo -e "   • Username: admin"
        echo -e "   • Password: admin"
        echo -e "   ${YELLOW}⚠️  Change password in production!${NC}"
        
        exit 0
        
    elif [ "$OVERALL_STATUS" = "degraded" ]; then
        echo -e "${YELLOW}⚠️  Status: DEGRADED${NC}"
        echo -e "${YELLOW}   Core services ready, some optional services unavailable${NC}"
        echo ""
        echo -e "   Checks Passed: ${CHECKS_PASSED}/${CHECKS_TOTAL}"
        echo -e "   Warnings: ${WARNINGS}"
        echo ""
        echo -e "${YELLOW}⚠️  Deployment partially successful${NC}"
        echo ""
        echo -e "   Core features available, but some features may not work."
        echo -e "   Check logs for details: docker-compose logs"
        
        exit 1
        
    else
        echo -e "${RED}❌ Status: UNHEALTHY${NC}"
        echo -e "${RED}   Critical services failed${NC}"
        echo ""
        echo -e "   Checks Passed: ${CHECKS_PASSED}/${CHECKS_TOTAL}"
        echo -e "   Critical Failures: ${CRITICAL_FAILURES}"
        echo ""
        echo -e "${RED}❌ Deployment failed${NC}"
        echo ""
        echo -e "   Troubleshooting:"
        echo -e "   1. Check logs: docker-compose logs"
        echo -e "   2. Verify .env configuration"
        echo -e "   3. Try clean rebuild: docker-compose down -v && docker-compose up -d"
        echo -e "   4. See: docs/setup/DATABASE_INITIALIZATION.md"
        
        exit 2
    fi
else
    echo -e "${RED}❌ Failed to get deployment status${NC}"
    echo ""
    echo -e "   The backend may still be starting up."
    echo -e "   Wait a few more seconds and try again."
    echo ""
    echo -e "   Or check logs: docker-compose logs healthcare_ai"
    
    exit 2
fi
