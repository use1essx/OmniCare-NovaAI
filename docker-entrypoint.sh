#!/bin/bash
# =============================================================================
# Healthcare AI V2 - Docker Entrypoint Script
# Runs initialization tasks before starting the application
# =============================================================================

set -e

echo "============================================================"
echo "Healthcare AI V2 - Starting Initialization"
echo "============================================================"

# Wait for database to be ready
echo "⏳ Waiting for database..."
until python -c "
import asyncio
from src.database.connection import init_database

async def check():
    try:
        await init_database()
        print('✅ Database connection successful')
        return True
    except Exception as e:
        print(f'❌ Database not ready: {e}')
        return False

exit(0 if asyncio.run(check()) else 1)
" 2>/dev/null; do
    echo "   Database not ready, waiting 2 seconds..."
    sleep 2
done

# Run database migrations
echo ""
echo "📦 Running database migrations..."
alembic upgrade head || echo "⚠️  Migration failed or already up to date"

# Seed movement analysis rules (if not already seeded)
echo ""
echo "🏃 Seeding movement analysis rules..."
python scripts/seed_movement_analysis_rules.py 2>/dev/null || echo "⚠️  Movement rules already seeded or error occurred"

# Seed form documents (if not already seeded)
echo ""
echo "📋 Seeding form documents..."
python scripts/seed_form_documents.py 2>/dev/null || echo "⚠️  Forms already seeded or error occurred"

# Seed KB categories (if not already seeded)
echo ""
echo "📁 Seeding KB categories..."
python scripts/seed_kb_categories_fixed.py 2>/dev/null || echo "⚠️  KB categories already seeded or error occurred"

# Setup elderly benefits category structure
echo ""
echo "💰 Setting up elderly benefits categories..."
python scripts/setup_elderly_benefits_categories.py 2>/dev/null || echo "⚠️  Elderly benefits categories already setup or error occurred"

# Seed KB documents (if not already seeded)
echo ""
echo "📚 Seeding KB documents..."
python scripts/reseed_kb_documents.py 2>/dev/null || echo "⚠️  KB documents already seeded or error occurred"

echo ""
echo "============================================================"
echo "✅ Initialization Complete - Starting Application"
echo "============================================================"
echo ""

# Execute the main command (passed as arguments to this script)
exec "$@"
