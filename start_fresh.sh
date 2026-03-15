#!/bin/bash
# =============================================================================
# Healthcare AI V2 - Fresh Start Script (Bash)
# =============================================================================
# This script completely removes old Docker containers, volumes, and images,
# then rebuilds and starts everything fresh.
#
# Usage: chmod +x start_fresh.sh && ./start_fresh.sh
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}Healthcare AI V2 - Fresh Start${NC}"
echo -e "${CYAN}=========================================${NC}"
echo ""

# Check if Docker is running
echo -e "${YELLOW}🔍 Checking Docker status...${NC}"
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    echo ""
    read -p "Press any key to exit..."
    exit 1
fi
echo -e "${GREEN}✅ Docker is running${NC}"

echo ""
echo -e "${YELLOW}⚠️  WARNING: This will completely remove:${NC}"
echo -e "${YELLOW}   - All containers${NC}"
echo -e "${YELLOW}   - All volumes (database data will be lost)${NC}"
echo -e "${YELLOW}   - All images${NC}"
echo -e "${YELLOW}   - All build cache${NC}"
echo ""

read -p "Are you sure you want to continue? (yes/no): " confirmation
if [ "$confirmation" != "yes" ]; then
    echo -e "${RED}❌ Operation cancelled${NC}"
    echo ""
    read -p "Press any key to exit..."
    exit 0
fi

echo ""
echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}Step 1: Stopping all containers...${NC}"
echo -e "${CYAN}=========================================${NC}"
docker-compose down -v
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Containers stopped and volumes removed${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: Some containers may not have been stopped${NC}"
fi

echo ""
echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}Step 2: Removing all images...${NC}"
echo -e "${CYAN}=========================================${NC}"
images=$(docker images -q)
if [ -n "$images" ]; then
    docker rmi -f $images
    echo -e "${GREEN}✅ All images removed${NC}"
else
    echo -e "${BLUE}ℹ️  No images to remove${NC}"
fi

echo ""
echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}Step 3: Cleaning Docker system...${NC}"
echo -e "${CYAN}=========================================${NC}"
docker system prune -af --volumes
echo -e "${GREEN}✅ Docker system cleaned${NC}"

echo ""
echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}Step 4: Cleaning local data folders...${NC}"
echo -e "${CYAN}=========================================${NC}"
if [ -d "data/vector_store" ]; then
    rm -rf data/vector_store/* 2>/dev/null
    echo -e "${GREEN}✅ Vector store cleaned${NC}"
fi
if [ -d "data/uploads" ]; then
    rm -rf data/uploads/* 2>/dev/null
    echo -e "${GREEN}✅ Uploads folder cleaned${NC}"
fi

echo ""
echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}Step 5: Building images (this may take 10-15 minutes)...${NC}"
echo -e "${CYAN}=========================================${NC}"
docker-compose build --no-cache
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Images built successfully${NC}"
else
    echo -e "${RED}❌ Build failed. Please check the error messages above.${NC}"
    echo ""
    read -p "Press any key to exit..."
    exit 1
fi

echo ""
echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}Step 6: Starting services...${NC}"
echo -e "${CYAN}=========================================${NC}"
docker-compose up -d
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Services started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start services. Please check the error messages above.${NC}"
    echo ""
    read -p "Press any key to exit..."
    exit 1
fi

echo ""
echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}Step 7: Waiting for services to be healthy...${NC}"
echo -e "${CYAN}=========================================${NC}"
echo -e "${YELLOW}⏳ Waiting 30 seconds for services to initialize...${NC}"
sleep 30

echo ""
echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN}Step 8: Checking service status...${NC}"
echo -e "${CYAN}=========================================${NC}"
docker-compose ps

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}✅ Fresh Start Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "${CYAN}🌐 Access your application at:${NC}"
echo -e "   - API: http://localhost:8000"
echo -e "   - API Docs: http://localhost:8000/docs"
echo -e "   - PgAdmin: http://localhost:5050"
echo ""
echo -e "${CYAN}🔐 Default credentials:${NC}"
echo -e "   - Username: admin"
echo -e "   - Password: admin"
echo ""
echo -e "${CYAN}📋 To view logs, run:${NC}"
echo -e "   docker-compose logs -f healthcare_ai"
echo ""
read -p "Press any key to exit..."
