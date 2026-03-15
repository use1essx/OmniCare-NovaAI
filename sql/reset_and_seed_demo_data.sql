-- ===================================================================
-- RESET AND SEED DEMO DATA
-- ===================================================================
-- This script clears all users and organizations, then creates
-- fresh demo data for development and testing.
-- ===================================================================

BEGIN;

-- ===================================================================
-- STEP 1: CLEAN UP EXISTING DATA
-- ===================================================================

-- Delete all users (this will cascade to related records)
DELETE FROM user_sessions;
DELETE FROM user_permissions;
DELETE FROM audit_logs;
DELETE FROM users;

-- Delete all organizations
DELETE FROM organizations;

-- Reset sequences
ALTER SEQUENCE users_id_seq RESTART WITH 1;
ALTER SEQUENCE organizations_id_seq RESTART WITH 1;

-- ===================================================================
-- STEP 2: CREATE ORGANIZATIONS
-- ===================================================================

-- Platform Organization (for super admin)
INSERT INTO organizations (id, name, type, description, email, is_active, is_verified, max_users, max_admins)
VALUES (1, 'Healthcare AI Platform', 'platform', 'Main platform for system administrators', 'platform@healthcare.ai', true, true, 100, 10);

-- Hospital
INSERT INTO organizations (id, name, type, description, email, is_active, is_verified, max_users, max_admins)
VALUES (2, 'General Hospital', 'hospital', 'General medical hospital with emergency services', 'admin@general-hospital.hk', true, true, 50, 5);

-- Clinic
INSERT INTO organizations (id, name, type, description, email, is_active, is_verified, max_users, max_admins)
VALUES (3, 'Community Health Center', 'clinic', 'Community health and wellness center', 'info@chc.hk', true, true, 30, 3);

-- NGO
INSERT INTO organizations (id, name, type, description, email, is_active, is_verified, max_users, max_admins)
VALUES (4, 'Mental Health Support NGO', 'ngo', 'Mental health support and counseling services', 'support@mhs-ngo.hk', true, true, 40, 4);

-- ===================================================================
-- STEP 3: CREATE DEMO USERS
-- ===================================================================

-- Password for ALL demo users: "admin"
-- Hash: simple_hash_21232f297a57a5a743894a0e4a801fc3

-- ------------------------------------------------------------------
-- SUPER ADMIN (Platform Level)
-- ------------------------------------------------------------------
INSERT INTO users (
    username, email, hashed_password, full_name,
    role, is_active, is_verified, is_admin, is_super_admin,
    organization_id, failed_login_attempts, created_at, updated_at
) VALUES (
    'admin',
    'admin@healthcare.ai',
    'simple_hash_21232f297a57a5a743894a0e4a801fc3',
    'System Administrator',
    'super_admin',
    true, true, true, true,
    1, -- Platform organization
    0,
    NOW(), NOW()
);

-- ------------------------------------------------------------------
-- GENERAL HOSPITAL USERS
-- ------------------------------------------------------------------

-- Hospital Admin
INSERT INTO users (
    username, email, hashed_password, full_name,
    role, is_active, is_verified, is_admin, is_super_admin,
    organization_id, department, failed_login_attempts, created_at, updated_at
) VALUES (
    'hospital_admin',
    'admin@general-hospital.hk',
    'simple_hash_21232f297a57a5a743894a0e4a801fc3',
    'Hospital Administrator',
    'admin',
    true, true, true, false,
    2, -- General Hospital
    'Administration',
    0,
    NOW(), NOW()
);

-- Doctor
INSERT INTO users (
    username, email, hashed_password, full_name,
    role, is_active, is_verified, is_admin, is_super_admin,
    organization_id, department, license_number, failed_login_attempts, created_at, updated_at
) VALUES (
    'dr_wong',
    'dr.wong@general-hospital.hk',
    'simple_hash_21232f297a57a5a743894a0e4a801fc3',
    'Dr. Wong Kar Wai',
    'doctor',
    true, true, false, false,
    2, -- General Hospital
    'Cardiology',
    'MD-123456',
    0,
    NOW(), NOW()
);

-- Nurse
INSERT INTO users (
    username, email, hashed_password, full_name,
    role, is_active, is_verified, is_admin, is_super_admin,
    organization_id, department, license_number, failed_login_attempts, created_at, updated_at
) VALUES (
    'nurse_chan',
    'nurse.chan@general-hospital.hk',
    'simple_hash_21232f297a57a5a743894a0e4a801fc3',
    'Nurse Chan Mei Ling',
    'nurse',
    true, true, false, false,
    2, -- General Hospital
    'Emergency',
    'RN-789012',
    0,
    NOW(), NOW()
);

-- Patient 1 (assigned to Dr. Wong)
INSERT INTO users (
    username, email, hashed_password, full_name,
    role, is_active, is_verified, is_admin, is_super_admin,
    organization_id, assigned_caregiver_id, failed_login_attempts, created_at, updated_at
) VALUES (
    'patient_li',
    'patient.li@example.com',
    'simple_hash_21232f297a57a5a743894a0e4a801fc3',
    'Li Ming',
    'user',
    true, true, false, false,
    2, -- General Hospital
    3, -- Assigned to Dr. Wong (user id 3)
    0,
    NOW(), NOW()
);

-- Patient 2 (assigned to Nurse Chan)
INSERT INTO users (
    username, email, hashed_password, full_name,
    role, is_active, is_verified, is_admin, is_super_admin,
    organization_id, assigned_caregiver_id, failed_login_attempts, created_at, updated_at
) VALUES (
    'patient_tang',
    'patient.tang@example.com',
    'simple_hash_21232f297a57a5a743894a0e4a801fc3',
    'Tang Siu Ming',
    'user',
    true, true, false, false,
    2, -- General Hospital
    4, -- Assigned to Nurse Chan (user id 4)
    0,
    NOW(), NOW()
);

-- ------------------------------------------------------------------
-- COMMUNITY HEALTH CENTER USERS
-- ------------------------------------------------------------------

-- Clinic Admin
INSERT INTO users (
    username, email, hashed_password, full_name,
    role, is_active, is_verified, is_admin, is_super_admin,
    organization_id, department, failed_login_attempts, created_at, updated_at
) VALUES (
    'clinic_admin',
    'admin@chc.hk',
    'simple_hash_21232f297a57a5a743894a0e4a801fc3',
    'Clinic Administrator',
    'admin',
    true, true, true, false,
    3, -- Community Health Center
    'Administration',
    0,
    NOW(), NOW()
);

-- Social Worker
INSERT INTO users (
    username, email, hashed_password, full_name,
    role, is_active, is_verified, is_admin, is_super_admin,
    organization_id, department, failed_login_attempts, created_at, updated_at
) VALUES (
    'sw_lee',
    'sw.lee@chc.hk',
    'simple_hash_21232f297a57a5a743894a0e4a801fc3',
    'Social Worker Lee Ka Man',
    'social_worker',
    true, true, false, false,
    3, -- Community Health Center
    'Community Services',
    0,
    NOW(), NOW()
);

-- Patient 3 (assigned to Social Worker)
INSERT INTO users (
    username, email, hashed_password, full_name,
    role, is_active, is_verified, is_admin, is_super_admin,
    organization_id, assigned_caregiver_id, failed_login_attempts, created_at, updated_at
) VALUES (
    'patient_cheng',
    'patient.cheng@example.com',
    'simple_hash_21232f297a57a5a743894a0e4a801fc3',
    'Cheng Wing Kuen',
    'user',
    true, true, false, false,
    3, -- Community Health Center
    8, -- Assigned to Social Worker (user id 8)
    0,
    NOW(), NOW()
);

-- ------------------------------------------------------------------
-- NGO USERS
-- ------------------------------------------------------------------

-- NGO Admin
INSERT INTO users (
    username, email, hashed_password, full_name,
    role, is_active, is_verified, is_admin, is_super_admin,
    organization_id, department, failed_login_attempts, created_at, updated_at
) VALUES (
    'ngo_admin',
    'admin@mhs-ngo.hk',
    'simple_hash_21232f297a57a5a743894a0e4a801fc3',
    'NGO Administrator',
    'admin',
    true, true, true, false,
    4, -- Mental Health Support NGO
    'Administration',
    0,
    NOW(), NOW()
);

-- Counselor
INSERT INTO users (
    username, email, hashed_password, full_name,
    role, is_active, is_verified, is_admin, is_super_admin,
    organization_id, department, failed_login_attempts, created_at, updated_at
) VALUES (
    'counselor_ng',
    'counselor.ng@mhs-ngo.hk',
    'simple_hash_21232f297a57a5a743894a0e4a801fc3',
    'Counselor Ng Wai Yin',
    'counselor',
    true, true, false, false,
    4, -- Mental Health Support NGO
    'Mental Health Services',
    0,
    NOW(), NOW()
);

-- Patient 4 (assigned to Counselor)
INSERT INTO users (
    username, email, hashed_password, full_name,
    role, is_active, is_verified, is_admin, is_super_admin,
    organization_id, assigned_caregiver_id, failed_login_attempts, created_at, updated_at
) VALUES (
    'patient_yuen',
    'patient.yuen@example.com',
    'simple_hash_21232f297a57a5a743894a0e4a801fc3',
    'Yuen Chi Shing',
    'user',
    true, true, false, false,
    4, -- Mental Health Support NGO
    11, -- Assigned to Counselor (user id 11)
    0,
    NOW(), NOW()
);

COMMIT;

-- ===================================================================
-- VERIFICATION
-- ===================================================================

SELECT '═══════════════════════════════════════════════════' as section;
SELECT '          DEMO DATA CREATED SUCCESSFULLY!' as title;
SELECT '═══════════════════════════════════════════════════' as section;

-- Show organizations
SELECT 
    '──────────── ORGANIZATIONS ────────────' as info
UNION ALL
SELECT 
    id || ' | ' || name || ' (' || type || ') | Users: ' || max_users
FROM organizations
ORDER BY id;

-- Show users by organization
SELECT 
    '──────────── USERS BY ORGANIZATION ────────────' as info
UNION ALL
SELECT 
    o.name || ' (' || COUNT(u.id) || ' users)'
FROM organizations o
LEFT JOIN users u ON u.organization_id = o.id
GROUP BY o.id, o.name
ORDER BY o.id;

-- Show all users with details
SELECT 
    '──────────── ALL DEMO USERS ────────────' as info;

SELECT 
    u.id,
    u.username,
    u.email,
    u.role,
    u.full_name,
    o.name as organization,
    CASE 
        WHEN u.assigned_caregiver_id IS NOT NULL THEN c.full_name
        ELSE NULL 
    END as caregiver
FROM users u
LEFT JOIN organizations o ON u.organization_id = o.id
LEFT JOIN users c ON u.assigned_caregiver_id = c.id
ORDER BY u.organization_id, u.role DESC, u.id;

-- Show login credentials
SELECT '═══════════════════════════════════════════════════' as section;
SELECT '          LOGIN CREDENTIALS (ALL USERS)' as title;
SELECT '═══════════════════════════════════════════════════' as section;
SELECT '' as info;
SELECT '  🔐 Password for ALL demo users: admin' as info;
SELECT '' as info;
SELECT '  Super Admin:' as info;
SELECT '    Username: admin' as info;
SELECT '    Password: admin' as info;
SELECT '' as info;
SELECT '  Organization Admins:' as info;
SELECT '    Username: hospital_admin, clinic_admin, ngo_admin' as info;
SELECT '    Password: admin' as info;
SELECT '' as info;
SELECT '  Caregivers:' as info;
SELECT '    Username: dr_wong, nurse_chan, sw_lee, counselor_ng' as info;
SELECT '    Password: admin' as info;
SELECT '' as info;
SELECT '  Patients:' as info;
SELECT '    Username: patient_li, patient_tang, patient_cheng, patient_yuen' as info;
SELECT '    Password: admin' as info;
SELECT '' as info;
SELECT '  🌐 Login URL: http://localhost:8000/live2d/auth' as info;
SELECT '═══════════════════════════════════════════════════' as section;

