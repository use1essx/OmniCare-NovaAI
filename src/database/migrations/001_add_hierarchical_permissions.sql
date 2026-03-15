-- Migration: Add Hierarchical Permissions Support
-- Date: 2025-10-17
-- Description: Add assigned_caregiver_id to users table to support patient assignment to caregivers

-- Add assigned_caregiver_id column to users table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS assigned_caregiver_id INTEGER;

-- Add foreign key constraint
ALTER TABLE users 
ADD CONSTRAINT fk_user_assigned_caregiver 
FOREIGN KEY (assigned_caregiver_id) REFERENCES users(id) ON DELETE SET NULL;

-- Add index for better query performance
CREATE INDEX IF NOT EXISTS idx_users_assigned_caregiver ON users(assigned_caregiver_id);

-- Create index on organization_id if not exists (for better query performance)
CREATE INDEX IF NOT EXISTS idx_users_organization_id ON users(organization_id);

-- Update role check constraint to include new roles
ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_user_role;
ALTER TABLE users 
ADD CONSTRAINT ck_user_role 
CHECK (role IN ('user', 'admin', 'doctor', 'nurse', 'social_worker', 'counselor', 'staff', 'medical_reviewer', 'data_manager', 'super_admin'));

-- Add comments for documentation
COMMENT ON COLUMN users.assigned_caregiver_id IS 'For patients: The ID of the doctor/nurse/social worker who manages this patient';
COMMENT ON COLUMN users.organization_id IS 'The organization this user belongs to';
COMMENT ON COLUMN users.created_by IS 'The ID of the user who created this account';

-- Migration complete

