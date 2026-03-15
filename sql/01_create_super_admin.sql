-- ===================================================================
-- Create or Update Super Admin User
-- ===================================================================
-- This script creates a super admin user or updates existing one
-- Username: admin
-- Password: admin (bcrypt hashed)
-- ⚠️  CHANGE PASSWORD IN PRODUCTION!
-- ===================================================================
-- NOTE: The password hash below is bcrypt for "admin"
-- To generate a new hash, run in Docker:
--   docker exec healthcare_ai_backend python -c "from src.security.auth import get_password_hash; print(get_password_hash('YOUR_PASSWORD'))"
-- ===================================================================

-- Check if user exists and update, otherwise create
DO $$
DECLARE
    -- Bcrypt hash for password "admin" (12 rounds)
    admin_password_hash TEXT := '$2b$12$BfnLGueQMeO8QO9t1plFVuALF38DEiUdNtWxHt44bk/qc3M1Ecozi';
BEGIN
    IF EXISTS (SELECT 1 FROM users WHERE username = 'admin') THEN
        -- Update existing admin user
        UPDATE users 
        SET hashed_password = admin_password_hash,
            failed_login_attempts = 0,
            account_locked_until = NULL,
            is_active = true,
            is_verified = true,
            is_admin = true,
            is_super_admin = true,
            role = 'super_admin',
            email = COALESCE(email, 'admin@healthcare.ai'),
            full_name = COALESCE(full_name, 'System Administrator'),
            updated_at = NOW()
        WHERE username = 'admin';
        
        RAISE NOTICE '✅ Admin user updated successfully';
    ELSE
        -- Create new super admin user
        INSERT INTO users (
            email,
            username,
            hashed_password,
            full_name,
            is_active,
            is_verified,
            is_admin,
            is_super_admin,
            role,
            failed_login_attempts,
            created_at,
            updated_at
        ) VALUES (
            'admin@healthcare.ai',
            'admin',
            admin_password_hash,
            'System Administrator',
            true,
            true,
            true,
            true,
            'super_admin',
            0,
            NOW(),
            NOW()
        );
        
        RAISE NOTICE '✅ Admin user created successfully';
    END IF;
END $$;

-- Verify the user
SELECT 
    id,
    username,
    email,
    full_name,
    role,
    is_admin,
    is_super_admin,
    is_active,
    created_at
FROM users 
WHERE username = 'admin';

-- Show login instructions
DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '═══════════════════════════════════════════════════';
    RAISE NOTICE '          SUPER ADMIN USER READY';
    RAISE NOTICE '═══════════════════════════════════════════════════';
    RAISE NOTICE '';
    RAISE NOTICE '  Username: admin';
    RAISE NOTICE '  Password: admin';
    RAISE NOTICE '  Email:    admin@healthcare.ai';
    RAISE NOTICE '  Role:     super_admin';
    RAISE NOTICE '';
    RAISE NOTICE '  Login URL: http://localhost:8000/live2d/auth';
    RAISE NOTICE '';
    RAISE NOTICE '  ⚠️  IMPORTANT: Change password in production!';
    RAISE NOTICE '';
    RAISE NOTICE '═══════════════════════════════════════════════════';
END $$;
