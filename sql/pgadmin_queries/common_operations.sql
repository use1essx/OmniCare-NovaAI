-- ===================================================================
-- Healthcare AI V2 - Common Operations Query Templates
-- ===================================================================
-- Frequently used SQL operations for Healthcare AI administration
-- Copy and paste these queries in pgAdmin Query Tool
-- ===================================================================

-- ===================================================================
-- 1. USER MANAGEMENT
-- ===================================================================

-- Create New Admin User
INSERT INTO users (
    email, 
    username, 
    hashed_password, 
    full_name, 
    is_active, 
    is_admin, 
    role,
    department
) VALUES (
    'new.admin@healthcare-ai.com',  -- Replace with actual email
    'new_admin',                    -- Replace with actual username
    '$2b$12$...',                   -- Replace with hashed password
    'New Admin User',               -- Replace with actual name
    true,
    true,
    'admin',
    'IT Administration'
);

-- Update User Role
UPDATE users 
SET role = 'medical_reviewer',  -- Options: 'user', 'admin', 'medical_reviewer', 'data_manager'
    is_admin = false,
    updated_at = NOW()
WHERE email = 'user@healthcare-ai.com';  -- Replace with actual email

-- Deactivate User Account
UPDATE users 
SET is_active = false,
    updated_at = NOW()
WHERE email = 'user@healthcare-ai.com';  -- Replace with actual email

-- Reset Failed Login Attempts
UPDATE users 
SET failed_login_attempts = 0,
    account_locked_until = NULL,
    updated_at = NOW()
WHERE email = 'user@healthcare-ai.com';  -- Replace with actual email

-- List All Admin Users
SELECT 
    id,
    email,
    username,
    full_name,
    role,
    department,
    is_active,
    last_login,
    created_at
FROM users 
WHERE is_admin = true OR role IN ('admin', 'medical_reviewer', 'data_manager')
ORDER BY last_login DESC;

-- ===================================================================
-- 2. CONVERSATION ANALYSIS
-- ===================================================================

-- Find Conversations by Date Range
SELECT 
    id,
    session_id,
    LEFT(user_input, 100) as user_input_preview,
    agent_type,
    urgency_level,
    language,
    user_satisfaction,
    created_at
FROM conversations 
WHERE created_at BETWEEN '2025-01-01' AND '2025-12-31'  -- Adjust date range
ORDER BY created_at DESC
LIMIT 100;

-- Find Emergency Conversations
SELECT 
    id,
    session_id,
    user_input,
    agent_response,
    agent_type,
    urgency_level,
    processing_time_ms,
    created_at
FROM conversations 
WHERE urgency_level = 'emergency'
ORDER BY created_at DESC
LIMIT 50;

-- Find Low Satisfaction Conversations
SELECT 
    id,
    session_id,
    LEFT(user_input, 100) as user_input_preview,
    LEFT(agent_response, 100) as agent_response_preview,
    agent_type,
    user_satisfaction,
    agent_confidence,
    created_at
FROM conversations 
WHERE user_satisfaction IS NOT NULL 
AND user_satisfaction <= 2  -- 1-2 star ratings
ORDER BY created_at DESC
LIMIT 50;

-- Agent Performance by Hour
SELECT 
    EXTRACT(hour FROM created_at) as hour_of_day,
    agent_type,
    COUNT(*) as conversation_count,
    ROUND(AVG(agent_confidence)::numeric, 3) as avg_confidence,
    ROUND(AVG(user_satisfaction)::numeric, 2) as avg_satisfaction,
    ROUND(AVG(processing_time_ms)::numeric, 0) as avg_processing_time
FROM conversations 
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY EXTRACT(hour FROM created_at), agent_type
ORDER BY hour_of_day, agent_type;

-- ===================================================================
-- 3. HK DATA MANAGEMENT
-- ===================================================================

-- Update HK Healthcare Data Quality Score
UPDATE hk_healthcare_data 
SET quality_score = 0.9,  -- New quality score (0.0 to 1.0)
    last_updated = NOW()
WHERE source_type = 'hospital_authority'  -- Adjust source type
AND facility_type = 'hospital';          -- Adjust facility type

-- Find Outdated HK Data
SELECT 
    source_type,
    facility_type,
    name_en,
    name_zh,
    last_updated,
    EXTRACT(EPOCH FROM (NOW() - last_updated))/3600 as hours_old,
    quality_score
FROM hk_healthcare_data 
WHERE last_updated < NOW() - INTERVAL '48 hours'  -- Older than 48 hours
ORDER BY last_updated ASC;

-- Add New HK Healthcare Facility
INSERT INTO hk_healthcare_data (
    source_type,
    facility_type,
    name_en,
    name_zh,
    address,
    district,
    phone,
    emergency_services,
    opening_hours,
    services_offered,
    quality_score,
    last_updated
) VALUES (
    'manual_entry',                    -- Source type
    'clinic',                         -- Facility type
    'New Medical Clinic',             -- English name
    '新醫療診所',                      -- Chinese name
    '123 Main Street, Central',       -- Address
    'Central and Western',            -- District
    '+852 2123 4567',                 -- Phone
    false,                            -- Emergency services
    '{"mon": "9:00-18:00", "tue": "9:00-18:00"}',  -- Opening hours (JSON)
    '["general_practice", "consultation"]',         -- Services (JSON array)
    0.8,                              -- Quality score
    NOW()                             -- Last updated
);

-- ===================================================================
-- 4. DOCUMENT MANAGEMENT
-- ===================================================================

-- Approve Pending Document
UPDATE uploaded_documents 
SET status = 'approved',
    approved_at = NOW(),
    approved_by = 1,  -- Replace with actual admin user ID
    updated_at = NOW()
WHERE id = 123;  -- Replace with actual document ID

-- Reject Document with Reason
UPDATE uploaded_documents 
SET status = 'rejected',
    rejection_reason = 'Content does not meet medical accuracy standards',  -- Add reason
    rejected_at = NOW(),
    rejected_by = 1,  -- Replace with actual admin user ID
    updated_at = NOW()
WHERE id = 123;  -- Replace with actual document ID

-- Find Documents by Category
SELECT 
    id,
    original_filename,
    file_type,
    category,
    description,
    quality_score,
    status,
    uploaded_by,
    created_at
FROM uploaded_documents 
WHERE category = 'medical_guidelines'  -- Categories: medical_guidelines, treatment_protocols, etc.
ORDER BY created_at DESC;

-- Update Document Quality Score
UPDATE uploaded_documents 
SET quality_score = 0.85,  -- New quality score
    updated_at = NOW()
WHERE id = 123;  -- Replace with actual document ID

-- ===================================================================
-- 5. SECURITY AND AUDIT
-- ===================================================================

-- Review Recent Security Events
SELECT 
    event_type,
    user_id,
    user_email,
    ip_address,
    user_agent,
    event_details,
    created_at
FROM audit_logs 
WHERE created_at > NOW() - INTERVAL '24 hours'  -- Last 24 hours
ORDER BY created_at DESC
LIMIT 100;

-- Find Multiple Failed Login Attempts
SELECT 
    user_email,
    ip_address,
    COUNT(*) as failed_attempts,
    MIN(created_at) as first_attempt,
    MAX(created_at) as last_attempt
FROM audit_logs 
WHERE event_type = 'login_failure'
AND created_at > NOW() - INTERVAL '1 hour'  -- Last hour
GROUP BY user_email, ip_address
HAVING COUNT(*) >= 3  -- 3 or more failed attempts
ORDER BY failed_attempts DESC;

-- Log Custom Security Event
INSERT INTO audit_logs (
    event_type,
    user_id,
    user_email,
    ip_address,
    user_agent,
    event_details,
    severity
) VALUES (
    'manual_security_check',           -- Event type
    1,                                -- User ID (admin performing check)
    'admin@healthcare-ai.com',        -- Admin email
    '192.168.1.100',                  -- IP address
    'pgAdmin Manual Entry',           -- User agent
    '{"action": "manual_review", "target": "suspicious_activity", "notes": "Reviewed and cleared"}',
    'medium'                          -- Severity: low, medium, high, critical
);

-- ===================================================================
-- 6. PERFORMANCE OPTIMIZATION
-- ===================================================================

-- Analyze Table Sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Find Missing Indexes (requires pg_stat_statements)
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats 
WHERE schemaname = 'public'
AND n_distinct > 100  -- Tables with high cardinality that might benefit from indexes
ORDER BY n_distinct DESC;

-- Vacuum and Analyze Specific Table
VACUUM ANALYZE conversations;  -- Replace with table name

-- ===================================================================
-- 7. DATA CLEANUP
-- ===================================================================

-- Clean Old Conversation Data (older than 6 months)
-- WARNING: This will permanently delete data. Make sure you have backups!
-- DELETE FROM conversations 
-- WHERE created_at < NOW() - INTERVAL '6 months';

-- Clean Old Audit Logs (older than 1 year)
-- WARNING: This will permanently delete audit data. Check compliance requirements!
-- DELETE FROM audit_logs 
-- WHERE created_at < NOW() - INTERVAL '1 year';

-- Clean Failed Upload Attempts
-- DELETE FROM uploaded_documents 
-- WHERE status = 'failed' 
-- AND created_at < NOW() - INTERVAL '7 days';

-- ===================================================================
-- 8. BACKUP VERIFICATION
-- ===================================================================

-- Check Database Size for Backup Planning
SELECT 
    pg_database.datname as database_name,
    pg_size_pretty(pg_database_size(pg_database.datname)) as size
FROM pg_database
WHERE pg_database.datname = 'healthcare_ai_v2';

-- Check Last Backup Information (if using custom backup logging)
-- SELECT 
--     backup_type,
--     backup_size,
--     backup_duration,
--     backup_status,
--     created_at
-- FROM backup_logs 
-- ORDER BY created_at DESC 
-- LIMIT 10;
