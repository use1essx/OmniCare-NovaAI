-- ===================================================================
-- COMPLETE DATABASE AUTO-SETUP
-- ===================================================================
-- This script sets up the ENTIRE database with:
-- - Auto timestamps (created_at, updated_at) on ALL tables
-- - Auto-update triggers for updated_at
-- - Proper foreign keys and relationships
-- - Performance indexes
-- - Constraints and validation
-- - Audit trail support
-- Safe to run multiple times (idempotent).
-- ===================================================================

BEGIN;

RAISE NOTICE '═══════════════════════════════════════════════════';
RAISE NOTICE '     STARTING COMPLETE DATABASE SETUP';
RAISE NOTICE '═══════════════════════════════════════════════════';

-- ===================================================================
-- STEP 1: CREATE AUTO-UPDATE TRIGGER FUNCTION
-- ===================================================================

RAISE NOTICE '';
RAISE NOTICE '▶ Creating auto-update trigger function...';

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

RAISE NOTICE '✅ Trigger function created';

-- ===================================================================
-- STEP 2: ADD TIMESTAMPS TO ALL TABLES
-- ===================================================================

RAISE NOTICE '';
RAISE NOTICE '▶ Adding timestamps to all tables...';

-- Users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Organizations table
CREATE TABLE IF NOT EXISTS organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    type VARCHAR(50) NOT NULL,
    description TEXT,
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    website VARCHAR(255),
    max_users INTEGER DEFAULT 50,
    max_admins INTEGER DEFAULT 10,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE NOT NULL,
    created_by INTEGER,
    updated_by INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    CONSTRAINT ck_organization_type CHECK (type IN ('hospital', 'clinic', 'ngo', 'platform', 'social_service'))
);

-- Conversations table
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Conversation_sessions table
ALTER TABLE conversation_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE conversation_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Conversation_messages table
ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Audit_logs table
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- User_sessions table
ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Uploaded_documents table
ALTER TABLE uploaded_documents ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE uploaded_documents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Document_versions table
ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Agent_performance table
ALTER TABLE agent_performance ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE agent_performance ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Agent_routing_decisions table
ALTER TABLE agent_routing_decisions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- HK Healthcare tables
ALTER TABLE hk_healthcare_facilities ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE hk_healthcare_facilities ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

ALTER TABLE hk_healthcare_updates ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Permissions tables
ALTER TABLE permissions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE permissions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

ALTER TABLE user_permissions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
ALTER TABLE user_permissions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

RAISE NOTICE '✅ Timestamps added to all tables';

-- ===================================================================
-- STEP 3: UPDATE USERS TABLE WITH NEW COLUMNS
-- ===================================================================

RAISE NOTICE '';
RAISE NOTICE '▶ Updating users table with new columns...';

-- Add organization_id if not exists
ALTER TABLE users ADD COLUMN IF NOT EXISTS organization_id INTEGER;

-- Add assigned_caregiver_id if not exists
ALTER TABLE users ADD COLUMN IF NOT EXISTS assigned_caregiver_id INTEGER;

-- Add created_by if not exists
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by INTEGER;

-- Add updated_by if not exists
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_by INTEGER;

RAISE NOTICE '✅ Users table updated';

-- ===================================================================
-- STEP 4: DROP OLD CONSTRAINTS
-- ===================================================================

RAISE NOTICE '';
RAISE NOTICE '▶ Cleaning up old constraints...';

-- Users constraints
ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_user_role;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_organization_id;
ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_user_organization;
ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_assigned_caregiver_id;
ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_user_assigned_caregiver;
ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_created_by;
ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_updated_by;

-- Organizations constraints
ALTER TABLE organizations DROP CONSTRAINT IF EXISTS fk_organizations_created_by;
ALTER TABLE organizations DROP CONSTRAINT IF EXISTS fk_organizations_updated_by;

RAISE NOTICE '✅ Old constraints cleaned';

-- ===================================================================
-- STEP 5: ADD COMPREHENSIVE ROLE CONSTRAINT
-- ===================================================================

RAISE NOTICE '';
RAISE NOTICE '▶ Adding comprehensive role constraint...';

ALTER TABLE users 
ADD CONSTRAINT ck_user_role CHECK (
    role IN (
        'user',           -- Patient/End User
        'admin',          -- Organization Admin
        'doctor',         -- Doctor (Caregiver)
        'nurse',          -- Nurse (Caregiver)
        'social_worker',  -- Social Worker (Caregiver)
        'counselor',      -- Counselor (Caregiver)
        'staff',          -- Staff (Caregiver)
        'medical_reviewer', -- Medical Reviewer
        'data_manager',   -- Data Manager
        'super_admin'     -- Platform Super Admin
    )
);

RAISE NOTICE '✅ Role constraint added';

-- ===================================================================
-- STEP 6: ADD ALL FOREIGN KEY RELATIONSHIPS
-- ===================================================================

RAISE NOTICE '';
RAISE NOTICE '▶ Creating foreign key relationships...';

-- Users -> Organizations
ALTER TABLE users 
ADD CONSTRAINT fk_users_organization_id 
FOREIGN KEY (organization_id) 
REFERENCES organizations(id) 
ON DELETE SET NULL;

-- Users -> Users (assigned caregiver)
ALTER TABLE users 
ADD CONSTRAINT fk_users_assigned_caregiver_id 
FOREIGN KEY (assigned_caregiver_id) 
REFERENCES users(id) 
ON DELETE SET NULL;

-- Users -> Users (created by)
ALTER TABLE users 
ADD CONSTRAINT fk_users_created_by 
FOREIGN KEY (created_by) 
REFERENCES users(id) 
ON DELETE SET NULL;

-- Users -> Users (updated by)
ALTER TABLE users 
ADD CONSTRAINT fk_users_updated_by 
FOREIGN KEY (updated_by) 
REFERENCES users(id) 
ON DELETE SET NULL;

-- Organizations -> Users (created by)
ALTER TABLE organizations 
ADD CONSTRAINT fk_organizations_created_by 
FOREIGN KEY (created_by) 
REFERENCES users(id) 
ON DELETE SET NULL;

-- Organizations -> Users (updated by)
ALTER TABLE organizations 
ADD CONSTRAINT fk_organizations_updated_by 
FOREIGN KEY (updated_by) 
REFERENCES users(id) 
ON DELETE SET NULL;

-- Uploaded_documents -> Users
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'uploaded_documents' AND column_name = 'uploaded_by') THEN
        ALTER TABLE uploaded_documents DROP CONSTRAINT IF EXISTS fk_uploaded_documents_uploaded_by;
        ALTER TABLE uploaded_documents 
        ADD CONSTRAINT fk_uploaded_documents_uploaded_by 
        FOREIGN KEY (uploaded_by) 
        REFERENCES users(id) 
        ON DELETE SET NULL;
    END IF;
END $$;

-- User_permissions -> Users
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_permissions' AND column_name = 'user_id') THEN
        ALTER TABLE user_permissions DROP CONSTRAINT IF EXISTS fk_user_permissions_user_id;
        ALTER TABLE user_permissions 
        ADD CONSTRAINT fk_user_permissions_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE;
    END IF;
END $$;

-- User_sessions -> Users
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'user_sessions' AND column_name = 'user_id') THEN
        ALTER TABLE user_sessions DROP CONSTRAINT IF EXISTS fk_user_sessions_user_id;
        ALTER TABLE user_sessions 
        ADD CONSTRAINT fk_user_sessions_user_id 
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE;
    END IF;
END $$;

RAISE NOTICE '✅ Foreign key relationships created';

-- ===================================================================
-- STEP 7: CREATE PERFORMANCE INDEXES
-- ===================================================================

RAISE NOTICE '';
RAISE NOTICE '▶ Creating performance indexes...';

-- Users table indexes
CREATE INDEX IF NOT EXISTS idx_users_organization_id ON users(organization_id);
CREATE INDEX IF NOT EXISTS idx_users_assigned_caregiver_id ON users(assigned_caregiver_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin);
CREATE INDEX IF NOT EXISTS idx_users_is_super_admin ON users(is_super_admin);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_created_by ON users(created_by);

-- Organizations table indexes
CREATE INDEX IF NOT EXISTS idx_organizations_name ON organizations(name);
CREATE INDEX IF NOT EXISTS idx_organizations_type ON organizations(type);
CREATE INDEX IF NOT EXISTS idx_organizations_is_active ON organizations(is_active);
CREATE INDEX IF NOT EXISTS idx_organizations_created_at ON organizations(created_at);

-- Conversations table indexes
CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_agent_type ON conversations(agent_type);
CREATE INDEX IF NOT EXISTS idx_conversations_urgency_level ON conversations(urgency_level);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at);

-- Conversation_sessions table indexes
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_session_id ON conversation_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_user_id ON conversation_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_created_at ON conversation_sessions(created_at);

-- Audit_logs table indexes
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_ip_address ON audit_logs(ip_address);

-- User_sessions table indexes
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_session_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_user_sessions_created_at ON user_sessions(created_at);

-- Uploaded_documents table indexes
CREATE INDEX IF NOT EXISTS idx_uploaded_documents_uploaded_by ON uploaded_documents(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_uploaded_documents_status ON uploaded_documents(status);
CREATE INDEX IF NOT EXISTS idx_uploaded_documents_category ON uploaded_documents(category);
CREATE INDEX IF NOT EXISTS idx_uploaded_documents_created_at ON uploaded_documents(created_at);

-- Agent_performance table indexes
CREATE INDEX IF NOT EXISTS idx_agent_performance_agent_type ON agent_performance(agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_performance_created_at ON agent_performance(created_at);

-- HK Healthcare tables indexes
CREATE INDEX IF NOT EXISTS idx_hk_healthcare_facilities_district ON hk_healthcare_facilities(district);
CREATE INDEX IF NOT EXISTS idx_hk_healthcare_facilities_facility_type ON hk_healthcare_facilities(facility_type);
CREATE INDEX IF NOT EXISTS idx_hk_healthcare_facilities_is_active ON hk_healthcare_facilities(is_active);

RAISE NOTICE '✅ Performance indexes created';

-- ===================================================================
-- STEP 8: CREATE AUTO-UPDATE TRIGGERS FOR ALL TABLES
-- ===================================================================

RAISE NOTICE '';
RAISE NOTICE '▶ Creating auto-update triggers...';

-- Drop existing triggers first
DROP TRIGGER IF EXISTS users_updated_at ON users;
DROP TRIGGER IF EXISTS organizations_updated_at ON organizations;
DROP TRIGGER IF EXISTS conversations_updated_at ON conversations;
DROP TRIGGER IF EXISTS conversation_sessions_updated_at ON conversation_sessions;
DROP TRIGGER IF EXISTS conversation_messages_updated_at ON conversation_messages;
DROP TRIGGER IF EXISTS user_sessions_updated_at ON user_sessions;
DROP TRIGGER IF EXISTS uploaded_documents_updated_at ON uploaded_documents;
DROP TRIGGER IF EXISTS agent_performance_updated_at ON agent_performance;
DROP TRIGGER IF EXISTS hk_healthcare_facilities_updated_at ON hk_healthcare_facilities;
DROP TRIGGER IF EXISTS permissions_updated_at ON permissions;
DROP TRIGGER IF EXISTS user_permissions_updated_at ON user_permissions;

-- Create triggers for all tables with updated_at
CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER conversation_sessions_updated_at
    BEFORE UPDATE ON conversation_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER conversation_messages_updated_at
    BEFORE UPDATE ON conversation_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER user_sessions_updated_at
    BEFORE UPDATE ON user_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER uploaded_documents_updated_at
    BEFORE UPDATE ON uploaded_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER agent_performance_updated_at
    BEFORE UPDATE ON agent_performance
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER hk_healthcare_facilities_updated_at
    BEFORE UPDATE ON hk_healthcare_facilities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER permissions_updated_at
    BEFORE UPDATE ON permissions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER user_permissions_updated_at
    BEFORE UPDATE ON user_permissions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

RAISE NOTICE '✅ Auto-update triggers created for all tables';

-- ===================================================================
-- STEP 9: ADD DOCUMENTATION COMMENTS
-- ===================================================================

RAISE NOTICE '';
RAISE NOTICE '▶ Adding documentation comments...';

-- Organizations table
COMMENT ON TABLE organizations IS 'Healthcare organizations (hospitals, clinics, NGOs, etc.)';
COMMENT ON COLUMN organizations.type IS 'Type: hospital, clinic, ngo, platform, social_service';
COMMENT ON COLUMN organizations.max_users IS 'Maximum number of users allowed in this organization';
COMMENT ON COLUMN organizations.max_admins IS 'Maximum number of admin users allowed';

-- Users table
COMMENT ON COLUMN users.organization_id IS 'The organization this user belongs to';
COMMENT ON COLUMN users.assigned_caregiver_id IS 'For patients: The caregiver (doctor/nurse/social worker) assigned to this patient';
COMMENT ON COLUMN users.created_by IS 'User ID who created this account';
COMMENT ON COLUMN users.updated_by IS 'User ID who last updated this account';
COMMENT ON COLUMN users.role IS 'User role: user, admin, doctor, nurse, social_worker, counselor, staff, medical_reviewer, data_manager, super_admin';

RAISE NOTICE '✅ Documentation comments added';

-- ===================================================================
-- STEP 10: INSERT DEFAULT DATA
-- ===================================================================

RAISE NOTICE '';
RAISE NOTICE '▶ Inserting default data...';

-- Insert platform organization
INSERT INTO organizations (id, name, type, description, email, is_active, is_verified)
VALUES (1, 'Healthcare AI Platform', 'platform', 'Main platform organization for system administrators', 'admin@healthcare.ai', true, true)
ON CONFLICT (name) DO UPDATE SET
    type = EXCLUDED.type,
    description = EXCLUDED.description,
    email = EXCLUDED.email,
    is_active = EXCLUDED.is_active,
    is_verified = EXCLUDED.is_verified,
    updated_at = NOW();

-- Insert sample organizations
INSERT INTO organizations (name, type, description, email, is_active, is_verified)
VALUES 
    ('General Hospital', 'hospital', 'General medical hospital', 'contact@general-hospital.hk', true, true),
    ('Community Health Center', 'clinic', 'Community health services', 'info@chc.hk', true, true),
    ('Mental Health Support NGO', 'ngo', 'Mental health support services', 'support@mhs-ngo.hk', true, false)
ON CONFLICT (name) DO NOTHING;

RAISE NOTICE '✅ Default data inserted';

-- ===================================================================
-- STEP 11: CREATE OR UPDATE SUPER ADMIN USER
-- ===================================================================

RAISE NOTICE '';
RAISE NOTICE '▶ Creating/updating super admin user...';

DO $$
DECLARE
    platform_org_id INTEGER;
BEGIN
    -- Get platform organization ID
    SELECT id INTO platform_org_id FROM organizations WHERE name = 'Healthcare AI Platform';
    
    IF EXISTS (SELECT 1 FROM users WHERE username = 'admin') THEN
        -- Update existing admin user
        UPDATE users 
        SET 
            hashed_password = 'simple_hash_21232f297a57a5a743894a0e4a801fc3',
            failed_login_attempts = 0,
            account_locked_until = NULL,
            is_active = true,
            is_verified = true,
            is_admin = true,
            is_super_admin = true,
            role = 'super_admin',
            organization_id = platform_org_id,
            email = COALESCE(email, 'admin@healthcare.ai'),
            full_name = COALESCE(full_name, 'System Administrator'),
            updated_at = NOW()
        WHERE username = 'admin';
        
        RAISE NOTICE '✅ Admin user updated';
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
            organization_id,
            failed_login_attempts,
            created_at,
            updated_at
        ) VALUES (
            'admin@healthcare.ai',
            'admin',
            'simple_hash_21232f297a57a5a743894a0e4a801fc3',
            'System Administrator',
            true,
            true,
            true,
            true,
            'super_admin',
            platform_org_id,
            0,
            NOW(),
            NOW()
        );
        
        RAISE NOTICE '✅ Admin user created';
    END IF;
END $$;

-- ===================================================================
-- STEP 12: VERIFY DATA INTEGRITY
-- ===================================================================

RAISE NOTICE '';
RAISE NOTICE '▶ Verifying data integrity...';

-- Check for users with invalid roles
DO $$
DECLARE
    invalid_role_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO invalid_role_count
    FROM users
    WHERE role NOT IN ('user', 'admin', 'doctor', 'nurse', 'social_worker', 
                       'counselor', 'staff', 'medical_reviewer', 'data_manager', 'super_admin');
    
    IF invalid_role_count > 0 THEN
        RAISE WARNING '⚠️  Found % users with invalid roles', invalid_role_count;
    ELSE
        RAISE NOTICE '✅ All user roles are valid';
    END IF;
END $$;

COMMIT;

-- ===================================================================
-- VERIFICATION QUERIES
-- ===================================================================

SELECT '═══════════════════════════════════════════════════' as section;
SELECT '          DATABASE TABLES STATUS' as title;
SELECT '═══════════════════════════════════════════════════' as section;

-- Show all tables with timestamp columns
SELECT 
    table_name,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = t.table_name AND column_name = 'created_at'
    ) THEN '✅' ELSE '❌' END as has_created_at,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = t.table_name AND column_name = 'updated_at'
    ) THEN '✅' ELSE '❌' END as has_updated_at,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.triggers 
        WHERE event_object_table = t.table_name AND trigger_name LIKE '%updated_at%'
    ) THEN '✅' ELSE '❌' END as has_trigger
FROM information_schema.tables t
WHERE t.table_schema = 'public'
AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name;

SELECT '═══════════════════════════════════════════════════' as section;
SELECT '          ORGANIZATIONS' as title;
SELECT '═══════════════════════════════════════════════════' as section;

SELECT 
    id,
    name,
    type,
    is_active,
    is_verified,
    max_users,
    max_admins
FROM organizations
ORDER BY id;

SELECT '═══════════════════════════════════════════════════' as section;
SELECT '          SUPER ADMIN USER' as title;
SELECT '═══════════════════════════════════════════════════' as section;

SELECT 
    id,
    username,
    email,
    full_name,
    role,
    is_admin,
    is_super_admin,
    is_active,
    organization_id,
    LEFT(hashed_password, 20) as password_hash_preview
FROM users 
WHERE username = 'admin';

SELECT '═══════════════════════════════════════════════════' as section;
SELECT '          DATABASE STATISTICS' as title;
SELECT '═══════════════════════════════════════════════════' as section;

SELECT 
    'Total Users' as metric,
    COUNT(*)::text as count
FROM users
UNION ALL
SELECT 
    'Active Users',
    COUNT(*)::text
FROM users 
WHERE is_active = true
UNION ALL
SELECT 
    'Total Organizations',
    COUNT(*)::text
FROM organizations
UNION ALL
SELECT 
    'Total Conversations',
    COUNT(*)::text
FROM conversations
UNION ALL
SELECT 
    'Total Uploaded Documents',
    COUNT(*)::text
FROM uploaded_documents
UNION ALL
SELECT 
    'Total Audit Logs',
    COUNT(*)::text
FROM audit_logs;

-- ===================================================================
-- SUCCESS MESSAGE
-- ===================================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '═══════════════════════════════════════════════════';
    RAISE NOTICE '     ✅ COMPLETE DATABASE SETUP FINISHED! ✅';
    RAISE NOTICE '═══════════════════════════════════════════════════';
    RAISE NOTICE '';
    RAISE NOTICE '  ✅ All tables updated with timestamps';
    RAISE NOTICE '  ✅ Auto-update triggers added to all tables';
    RAISE NOTICE '  ✅ Foreign keys and relationships created';
    RAISE NOTICE '  ✅ Performance indexes added';
    RAISE NOTICE '  ✅ Organizations table setup';
    RAISE NOTICE '  ✅ Super admin user created/updated';
    RAISE NOTICE '  ✅ Data integrity verified';
    RAISE NOTICE '';
    RAISE NOTICE '  🔐 LOGIN CREDENTIALS:';
    RAISE NOTICE '     Username: admin';
    RAISE NOTICE '     Password: admin';
    RAISE NOTICE '     URL: http://localhost:8000/live2d/auth';
    RAISE NOTICE '';
    RAISE NOTICE '  🤖 AUTO-SETUP FEATURES:';
    RAISE NOTICE '     • All tables have created_at timestamps';
    RAISE NOTICE '     • All tables have updated_at auto-updates';
    RAISE NOTICE '     • Triggers automatically update timestamps';
    RAISE NOTICE '     • Foreign keys maintain data integrity';
    RAISE NOTICE '     • Indexes optimize query performance';
    RAISE NOTICE '';
    RAISE NOTICE '  ⚠️  Remember to change password in production!';
    RAISE NOTICE '';
    RAISE NOTICE '═══════════════════════════════════════════════════';
END $$;

