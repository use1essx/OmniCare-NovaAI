#!/bin/bash
# ===================================================================
# Healthcare AI - Database Reinitialization Script
# ===================================================================
# This script completely resets the database and runs the auto-setup
# again. Use this when you want a fresh start.
# ⚠️  WARNING: This will DELETE all existing data!
# ===================================================================

set -e

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Healthcare AI - Database Reinitialization"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "⚠️  WARNING: This will DELETE all data in the database!"
echo ""
echo "This script will:"
echo "  1. Stop all containers"
echo "  2. Remove the database volume"
echo "  3. Restart containers (database auto-setups)"
echo ""

# Confirm
read -p "Are you sure you want to continue? (type 'yes' to confirm): " -r
echo ""

if [[ ! $REPLY =~ ^yes$ ]]; then
    echo "❌ Cancelled. No changes made."
    exit 0
fi

echo "🔄 Starting reinitialization..."
echo ""

# Change to project root
cd "$(dirname "$0")/../.."

# Step 1: Stop containers
echo "▶ Step 1/3: Stopping containers..."
docker-compose down
echo "✅ Containers stopped"
echo ""

# Step 2: Remove database volume
echo "▶ Step 2/3: Removing database volume..."

# Get the volume name (it might have a prefix based on directory name)
VOLUME_NAME=$(docker volume ls -q | grep postgres_data | head -n 1)

if [ -z "$VOLUME_NAME" ]; then
    echo "ℹ️  No postgres volume found. Will create fresh."
else
    echo "   Removing volume: $VOLUME_NAME"
    docker volume rm "$VOLUME_NAME"
    echo "✅ Database volume removed"
fi
echo ""

# Step 3: Start containers
echo "▶ Step 3/3: Starting containers (auto-setup will run)..."
docker-compose up -d
echo "✅ Containers started"
echo ""

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 5

# Check if database is healthy
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if docker-compose ps postgres | grep -q "healthy"; then
        echo "✅ Database is healthy!"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo "   Waiting... ($ATTEMPT/$MAX_ATTEMPTS)"
    sleep 2
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo "⚠️  Database health check timeout. Check logs with:"
    echo "   docker-compose logs postgres"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ Database Reinitialized Successfully!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📊 Check initialization logs:"
echo "   docker-compose logs postgres"
echo ""
echo "🔐 Login credentials:"
echo "   URL:      http://localhost:8000/live2d/auth"
echo "   Username: admin"
echo "   Password: admin"
echo ""
echo "🎉 Your database is now fresh and auto-configured!"
echo ""

