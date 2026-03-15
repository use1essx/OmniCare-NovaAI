#!/bin/bash
# =============================================================================
# Healthcare AI - Quick Start Script (Mac/Linux)
# =============================================================================

echo "=========================================="
echo "Healthcare AI - Quick Start"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running!"
    echo "Please start Docker Desktop and try again."
    echo ""
    echo "Mac: open -a Docker"
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Ask user what they want to do
echo "What would you like to do?"
echo "1) Clean build (removes all data, rebuilds from scratch)"
echo "2) Regular start (uses existing data)"
echo "3) Stop all containers"
echo ""
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        echo ""
        echo "🧹 Cleaning up old containers and volumes..."
        docker-compose down -v
        
        echo ""
        echo "🔨 Building Docker images (this may take 10-15 minutes)..."
        docker-compose build --no-cache
        
        echo ""
        echo "🚀 Starting all services..."
        docker-compose up -d
        
        echo ""
        echo "⏳ Waiting for services to initialize (30 seconds)..."
        sleep 30
        ;;
    2)
        echo ""
        echo "🚀 Starting all services..."
        docker-compose up -d
        
        echo ""
        echo "⏳ Waiting for services to initialize (10 seconds)..."
        sleep 10
        ;;
    3)
        echo ""
        echo "🛑 Stopping all containers..."
        docker-compose down
        echo "✅ All containers stopped"
        exit 0
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

# Check status
echo ""
echo "📊 Container Status:"
docker-compose ps

echo ""
echo "=========================================="
echo "✅ Healthcare AI is ready!"
echo "=========================================="
echo ""
echo "Access points:"
echo "  • Main App:    http://localhost:8000"
echo "  • KB Sandbox:  http://localhost:8000/admin/kb-sandbox"
echo "  • pgAdmin:     http://localhost:5050"
echo "  • Health:      http://localhost:8000/health"
echo ""
echo "View logs:"
echo "  docker-compose logs -f"
echo ""
echo "Stop services:"
echo "  docker-compose down"
echo ""
