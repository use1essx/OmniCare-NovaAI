-- =============================================================================
-- Knowledge Base Tables Creation Script
-- =============================================================================
-- This script creates the missing KB (Knowledge Base) tables required for
-- the KB Sandbox feature in the admin interface.
-- =============================================================================

-- Drop existing tables if they exist (in correct order due to foreign keys)
DROP TABLE IF EXISTS document_category_tags CASCADE;
DROP TABLE IF EXISTS kb_categories CASCADE;

-- =============================================================================
-- KB Categories Table
-- =============================================================================
-- Hierarchical category structure for knowledge base documents
-- Supports 3 levels: Age Groups → Categories → Topics
-- =============================================================================
CREATE TABLE kb_categories (
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
CREATE INDEX idx_kb_categories_level ON kb_categories(level);
CREATE INDEX idx_kb_categories_parent_id ON kb_categories(parent_id);
CREATE INDEX idx_kb_categories_slug ON kb_categories(slug);
CREATE INDEX idx_kb_categories_is_active ON kb_categories(is_active);

-- =============================================================================
-- Document Category Tags Table
-- =============================================================================
-- Many-to-many relationship between documents and categories
-- Only create if knowledge_documents table exists
-- =============================================================================
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'knowledge_documents') THEN
        CREATE TABLE IF NOT EXISTS document_category_tags (
            id SERIAL PRIMARY KEY,
            document_id INTEGER NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
            category_id INTEGER NOT NULL REFERENCES kb_categories(id) ON DELETE CASCADE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            
            -- Prevent duplicate tags
            CONSTRAINT unique_document_category UNIQUE (document_id, category_id)
        );

        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_document_category_tags_document_id ON document_category_tags(document_id);
        CREATE INDEX IF NOT EXISTS idx_document_category_tags_category_id ON document_category_tags(category_id);
        
        RAISE NOTICE '✅ document_category_tags table created';
    ELSE
        RAISE NOTICE '⚠️  knowledge_documents table does not exist, skipping document_category_tags';
    END IF;
END $$;

-- =============================================================================
-- Comments
-- =============================================================================
COMMENT ON TABLE kb_categories IS 'Hierarchical category structure for knowledge base (3 levels: Age Groups → Categories → Topics)';
COMMENT ON TABLE document_category_tags IS 'Many-to-many relationship between documents and categories';

COMMENT ON COLUMN kb_categories.level IS '1=Age Group, 2=Category, 3=Topic';
COMMENT ON COLUMN kb_categories.parent_id IS 'NULL for level 1, references parent category for levels 2-3';
COMMENT ON COLUMN kb_categories.slug IS 'URL-friendly identifier (e.g., elderly, health, elder-card)';
COMMENT ON COLUMN kb_categories.display_order IS 'Order for displaying categories within the same level/parent';

-- =============================================================================
-- Success Message
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE '✅ KB tables created successfully!';
    RAISE NOTICE '   - kb_categories';
    RAISE NOTICE '   - document_category_tags';
    RAISE NOTICE '';
    RAISE NOTICE 'Next step: Run seed script to populate categories';
    RAISE NOTICE '   docker exec healthcare_ai_backend python seed_kb_now.py';
END $$;
