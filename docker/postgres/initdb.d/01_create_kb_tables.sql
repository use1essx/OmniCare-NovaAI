-- =============================================================================
-- Knowledge Base Tables Initialization
-- Creates kb_categories and document_category_tags tables
-- =============================================================================

-- Create kb_categories table
CREATE TABLE IF NOT EXISTS kb_categories (
    id SERIAL PRIMARY KEY,
    name_en VARCHAR(255) NOT NULL,
    name_zh VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    icon VARCHAR(50),
    description_en TEXT,
    description_zh TEXT,
    level INTEGER NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    parent_id INTEGER REFERENCES kb_categories(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    CONSTRAINT uq_kb_categories_slug_level UNIQUE (slug, level)
);

-- Create indexes for kb_categories
CREATE INDEX IF NOT EXISTS ix_kb_categories_slug ON kb_categories(slug);
CREATE INDEX IF NOT EXISTS ix_kb_categories_level ON kb_categories(level);
CREATE INDEX IF NOT EXISTS ix_kb_categories_parent_id ON kb_categories(parent_id);

-- Create document_category_tags table
CREATE TABLE IF NOT EXISTS document_category_tags (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES uploaded_documents(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES kb_categories(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    CONSTRAINT uq_document_category_tags UNIQUE (document_id, category_id)
);

-- Create indexes for document_category_tags
CREATE INDEX IF NOT EXISTS ix_document_category_tags_document_id ON document_category_tags(document_id);
CREATE INDEX IF NOT EXISTS ix_document_category_tags_category_id ON document_category_tags(category_id);
