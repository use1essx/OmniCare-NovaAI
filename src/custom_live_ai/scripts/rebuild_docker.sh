#!/bin/bash
# Custom Live AI - Force Rebuild Docker Image
# Use this when you update requirements or Dockerfile

set -e  # Exit on error

echo "🔨 FORCE REBUILD - Docker Image"
echo "================================================"
echo "⚠️  This will rebuild the entire image from scratch"
echo "   Use this when you update:"
echo "   • requirements_docker.txt"
echo "   • Dockerfile"
echo "   • System dependencies"
echo ""

read -p "Continue with rebuild? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Rebuild cancelled"
    exit 0
fi

echo ""
echo "🗑️  Removing old images..."
docker-compose down
docker rmi custom_live_ai-app:latest 2>/dev/null || true

echo ""
echo "🔨 Building fresh image..."
export DOCKER_BUILDKIT=1
docker-compose build --no-cache

echo ""
echo "✅ Rebuild complete!"
echo ""
echo "🚀 Starting services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo "✅ Custom Live AI is RUNNING with fresh build!"
    echo "================================================"
    echo ""
    echo "📍 Access points:"
    echo "   🌐 Web UI:        http://localhost:8001"
    echo "   💓 Health Check:  http://localhost:8001/health"
    echo "   📊 API Docs:      http://localhost:8001/docs"
    echo ""
    echo "📋 Recent logs:"
    docker-compose logs --tail=20 app
else
    echo ""
    echo "❌ Failed to start services after rebuild!"
    echo "   Check logs: docker-compose logs"
    exit 1
fi

