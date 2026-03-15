-- ===================================================================
-- OmniCare Healthcare AI - Database Initialization
-- ===================================================================
-- This script initializes the database with required extensions,
-- functions, and seed data.
--
-- Tables are created by SQLAlchemy on application startup.
-- This script only creates prerequisites and seed data.
--
-- Run automatically by Docker on first container start.
-- Safe to run multiple times (idempotent).
--
-- ===================================================================

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

-- ===================================================================
-- SECTION 1: PostgreSQL Extensions and Helper Functions
-- ===================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Create trigger function for auto-updating updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ===================================================================
-- SECTION 2: Organizations Table (Required before users)
-- ===================================================================

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
    CONSTRAINT ck_organization_type CHECK (type IN ('hospital', 'clinic', 'ngo', 'platform', 'social_service'))
);

CREATE INDEX IF NOT EXISTS idx_organizations_name ON organizations(name);
CREATE INDEX IF NOT EXISTS idx_organizations_type ON organizations(type);
CREATE INDEX IF NOT EXISTS idx_organizations_is_active ON organizations(is_active);

DROP TRIGGER IF EXISTS organizations_updated_at ON organizations;
CREATE TRIGGER organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ===================================================================
-- SECTION 3: Seed Data
-- ===================================================================

-- Seed Organizations (UPSERT for idempotency)
INSERT INTO organizations (id, name, type, description, email, is_active, is_verified, max_users, max_admins)
VALUES 
    (1, 'Healthcare AI Platform', 'platform', 'Main platform for system administrators', 'platform@healthcare.ai', true, true, 100, 10),
    (2, 'General Hospital', 'hospital', 'General medical hospital with emergency services', 'admin@general-hospital.hk', true, true, 50, 5),
    (3, 'Community Health Center', 'clinic', 'Community health and wellness center', 'info@chc.hk', true, true, 30, 3),
    (4, 'Mental Health Support NGO', 'ngo', 'Mental health support and counseling services', 'support@mhs-ngo.hk', true, true, 40, 4)
ON CONFLICT (name) DO UPDATE SET
    type = EXCLUDED.type,
    description = EXCLUDED.description,
    email = EXCLUDED.email,
    is_active = EXCLUDED.is_active,
    is_verified = EXCLUDED.is_verified,
    updated_at = NOW();

-- Reset sequence
SELECT setval('organizations_id_seq', COALESCE((SELECT MAX(id) FROM organizations), 0) + 1, false);

-- ===================================================================
-- SECTION 4: Success Report
-- ===================================================================

DO $$ 
DECLARE
    org_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO org_count FROM organizations;
    
    RAISE NOTICE '';
    RAISE NOTICE '═══════════════════════════════════════════════════';
    RAISE NOTICE '  ✅ DATABASE PREREQUISITES READY';
    RAISE NOTICE '═══════════════════════════════════════════════════';
    RAISE NOTICE '';
    RAISE NOTICE '✅ Extensions created (uuid-ossp, pg_trgm)';
    RAISE NOTICE '✅ Helper functions created';
    RAISE NOTICE '✅ Organizations table created';
    RAISE NOTICE '✅ Seed data inserted (% organizations)', org_count;
    RAISE NOTICE '';
    RAISE NOTICE '⏭️  Next Steps:';
    RAISE NOTICE '   1. Application will create remaining tables via SQLAlchemy';
    RAISE NOTICE '   2. Super admin user will be created automatically';
    RAISE NOTICE '';
    RAISE NOTICE '═══════════════════════════════════════════════════';
END $$;


-- ===================================================================
-- SECTION: Knowledge Base Tables
-- ===================================================================
-- KB Categories and Document Tagging System
-- Created: 2026-02-24
-- ===================================================================

-- KB Categories Table (Hierarchical 3-level structure)
CREATE TABLE IF NOT EXISTS kb_categories (
    id SERIAL PRIMARY KEY,
    name_en VARCHAR(255) NOT NULL,
    name_zh VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    icon VARCHAR(50),
    description_en TEXT,
    description_zh TEXT,
    level INTEGER NOT NULL CHECK (level IN (1, 2, 3)),
    display_order INTEGER NOT NULL DEFAULT 0,
    parent_id INTEGER REFERENCES kb_categories(id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT level_parent_check CHECK (
        (level = 1 AND parent_id IS NULL) OR
        (level > 1 AND parent_id IS NOT NULL)
    )
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_kb_categories_level ON kb_categories(level);
CREATE INDEX IF NOT EXISTS idx_kb_categories_parent_id ON kb_categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_kb_categories_slug ON kb_categories(slug);
CREATE INDEX IF NOT EXISTS idx_kb_categories_is_active ON kb_categories(is_active);

-- Document Category Tags Table (Many-to-many relationship)
CREATE TABLE IF NOT EXISTS document_category_tags (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL REFERENCES kb_categories(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Prevent duplicate tags
    CONSTRAINT unique_document_category UNIQUE (document_id, category_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_document_category_tags_document_id ON document_category_tags(document_id);
CREATE INDEX IF NOT EXISTS idx_document_category_tags_category_id ON document_category_tags(category_id);

-- Comments
COMMENT ON TABLE kb_categories IS 'Hierarchical category structure for knowledge base (3 levels: Age Groups → Categories → Topics)';
COMMENT ON TABLE document_category_tags IS 'Many-to-many relationship between documents and categories';
COMMENT ON COLUMN kb_categories.level IS '1=Age Group, 2=Category, 3=Topic';
COMMENT ON COLUMN kb_categories.parent_id IS 'NULL for level 1, references parent category for levels 2-3';
COMMENT ON COLUMN kb_categories.slug IS 'URL-friendly identifier (e.g., elderly, health, elder-card)';
COMMENT ON COLUMN kb_categories.display_order IS 'Order for displaying categories within the same level/parent';

-- ===================================================================
-- END OF KNOWLEDGE BASE TABLES
-- ===================================================================
