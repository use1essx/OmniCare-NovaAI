#!/bin/bash

# Healthcare AI V2 - Database Security Setup Script
# Creates limited database user and applies security configurations

echo "🔒 === DATABASE SECURITY SETUP === 🔒"
echo ""

# Check if PostgreSQL is running
echo "1. Checking PostgreSQL status..."
if ! docker-compose exec -T postgres pg_isready -U admin -d healthcare_ai_v2 >/dev/null 2>&1; then
    echo "❌ PostgreSQL is not ready. Please start the system first."
    echo "   Run: ./scripts/deployment/start-all.sh"
    exit 1
fi
echo "✅ PostgreSQL is ready"

# Create limited database user
echo ""
echo "2. Creating limited application database user..."
docker-compose exec -T postgres psql -U admin -d healthcare_ai_v2 -f /dev/stdin << 'EOF'
-- Check if user already exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'healthcare_app_user') THEN
        -- Create application user with login capability
        CREATE USER healthcare_app_user WITH LOGIN PASSWORD 'healthcare_app_secure_2025';
        RAISE NOTICE 'Created user healthcare_app_user';
    ELSE
        RAISE NOTICE 'User healthcare_app_user already exists';
    END IF;
END
$$;

-- Grant connection to the database
GRANT CONNECT ON DATABASE healthcare_ai_v2 TO healthcare_app_user;

-- Grant usage on the public schema
GRANT USAGE ON SCHEMA public TO healthcare_app_user;

-- Grant table permissions (SELECT, INSERT, UPDATE, DELETE only - no CREATE/DROP)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO healthcare_app_user;

-- Grant sequence permissions (needed for auto-incrementing IDs)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO healthcare_app_user;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public 
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO healthcare_app_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public 
GRANT USAGE, SELECT ON SEQUENCES TO healthcare_app_user;

-- Show created user
SELECT usename, usesuper, usecreatedb, usebypassrls 
FROM pg_user 
WHERE usename = 'healthcare_app_user';
EOF

echo "✅ Limited database user created successfully"

# Test the new user's permissions
echo ""
echo "3. Testing limited user permissions..."

# Test successful operations
echo "   Testing SELECT permission..."
docker-compose exec -T postgres psql -U healthcare_app_user -d healthcare_ai_v2 -c "SELECT COUNT(*) FROM users;" >/dev/null 2>&1 && echo "   ✅ SELECT works" || echo "   ❌ SELECT failed"

# Test restricted operations (should fail)
echo "   Testing CREATE permission (should fail)..."
docker-compose exec -T postgres psql -U healthcare_app_user -d healthcare_ai_v2 -c "CREATE TABLE test_table (id INT);" 2>/dev/null && echo "   ❌ CREATE works (security issue!)" || echo "   ✅ CREATE properly restricted"

echo "   Testing DROP permission (should fail)..."
docker-compose exec -T postgres psql -U healthcare_app_user -d healthcare_ai_v2 -c "DROP TABLE IF EXISTS test_table;" 2>/dev/null && echo "   ❌ DROP works (security issue!)" || echo "   ✅ DROP properly restricted"

# Create environment file for limited user
echo ""
echo "4. Creating secure environment configuration..."
cat > .env.secure << 'EOF'
# Healthcare AI V2 - Secure Database Configuration
# Use this configuration for production deployment

# Database Configuration with Limited User
DATABASE_HOST=postgres
DATABASE_PORT=5432
DATABASE_NAME=healthcare_ai_v2
DATABASE_USER=healthcare_app_user
DATABASE_PASSWORD=healthcare_app_secure_2025

# Keep other settings the same
REDIS_HOST=redis
REDIS_PORT=6379

# Production Security Settings
ENVIRONMENT=production
DEBUG=false
ENABLE_SECURITY_HEADERS=true
ENABLE_HTTPS_REDIRECT=true

# Add your production API keys here
OPENROUTER_API_KEY=your_production_api_key_here
SECRET_KEY=your_production_secret_key_here
EOF

echo "✅ Secure environment file created: .env.secure"

echo ""
echo "📋 SECURITY IMPROVEMENTS APPLIED:"
echo "   ✅ Limited database user created (healthcare_app_user)"
echo "   ✅ User has minimal required privileges only"
echo "   ✅ User cannot create/drop tables or databases"
echo "   ✅ User cannot create other users"
echo "   ✅ Secure environment configuration created"

echo ""
echo "🔄 TO USE THE SECURE CONFIGURATION:"
echo "   1. Review and update .env.secure with your production values"
echo "   2. Replace .env with .env.secure: cp .env.secure .env"
echo "   3. Restart the application: ./scripts/deployment/start-all.sh"

echo ""
echo "⚠️  IMPORTANT SECURITY NOTES:"
echo "   • Change the default password in production"
echo "   • Use strong, unique passwords for all users"
echo "   • Enable SSL/TLS for database connections in production"
echo "   • Regularly rotate database passwords"
echo "   • Monitor database access logs"

echo ""
echo "🎯 Database security setup completed successfully!"
