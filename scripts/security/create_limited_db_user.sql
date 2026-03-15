-- Healthcare AI V2 - Limited Database User Creation
-- Creates a restricted user for the application with minimal privileges

-- Create application user with login capability
CREATE USER healthcare_app_user WITH LOGIN PASSWORD 'healthcare_app_secure_2025';

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

-- Verify the user was created successfully
\du healthcare_app_user

-- Show granted permissions
\dp

-- Security note: This user cannot:
-- 1. Create or drop tables/databases
-- 2. Create other users
-- 3. Access system catalogs beyond basic operations
-- 4. Execute administrative functions
