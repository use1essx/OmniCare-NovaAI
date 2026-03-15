#!/bin/bash
# Custom Live AI - Docker Startup Script
# Auto-setup database and start application

set -e  # Exit on error

echo "🚀 Starting Custom Live AI with Docker..."
echo "================================================"

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp env.example .env
    echo "✅ .env created!"
fi

# Create recordings directory if it doesn't exist
mkdir -p recordings logs uploads

echo ""
echo "🐳 Starting Docker containers..."
echo "   - PostgreSQL database (port 5433)"
echo "   - pgAdmin web interface (port 5051)"
echo "   - FastAPI application (port 8001)"
echo ""

# Check if image exists, build only if needed
if ! docker images | grep -q "custom_live_ai-app"; then
    echo "🔨 Building Docker image (first time)..."
    docker-compose build
else
    echo "✅ Using cached Docker image"
fi

# Start Docker Compose (without rebuild)
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo "✅ Custom Live AI is RUNNING!"
    echo "================================================"
    echo ""
    echo "📍 Access points:"
    echo "   🌐 Web UI:        http://localhost:8001"
    echo "   💓 Health Check:  http://localhost:8001/health"
    echo "   📊 API Docs:      http://localhost:8001/docs"
    echo "   🗄️  Database:      localhost:5433 (custom_live_ai)"
    echo "   🔧 pgAdmin:       http://localhost:5051"
    echo "       Email:        admin@example.com"
    echo "       Password:     admin"
    echo ""
    echo "👤 Test user created:"
    echo "   User ID: test_user_001"
    echo "   Name: Test User"
    echo ""
    echo "📝 Useful commands:"
    echo "   View logs:    docker-compose logs -f"
    echo "   View DB logs: docker-compose logs -f db"
    echo "   View app logs: docker-compose logs -f app"
    echo "   Stop:         docker-compose down"
    echo "   Restart:      docker-compose restart"
    echo "   Shell (DB):   docker-compose exec db psql -U custom_ai_user -d custom_live_ai"
    echo "   Shell (App):  docker-compose exec app bash"
    echo ""
    echo "🎉 Ready to record motion capture data!"
    echo "================================================"
    
    # Show recent logs
    echo ""
    echo "📋 Recent application logs:"
    docker-compose logs --tail=20 app
else
    echo ""
    echo "❌ Failed to start services!"
    echo "   Check logs: docker-compose logs"
    exit 1
fi


