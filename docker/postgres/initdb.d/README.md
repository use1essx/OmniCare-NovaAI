# PostgreSQL Initialization Scripts

These scripts run automatically when the PostgreSQL Docker container is first created with an empty data volume.

## Script Execution Order

PostgreSQL executes scripts in `/docker-entrypoint-initdb.d/` alphabetically:

| Script | Purpose |
|--------|---------|
| `01-init-database.sh` | Welcome message and logging |
| `02-schema.sql` | Creates organizations table and triggers |
| `03-seed-data.sql` | Seeds 4 demo organizations |
| `04-kb-categories.sql` | Creates KB categories tables (kb_categories, document_category_tags) |
| `05-seed-kb-categories.sql` | Seeds 4 age groups (Level 1 categories only) |
| `06-knowledge-documents-view.sql` | Creates knowledge_documents view (maps uploaded_documents) |
| `07-document-chunks-table.sql` | Creates document_chunks table for vector search |
| `08-validate-setup.sql` | Validates all tables/views were created successfully |

## Important Notes

1. **Scripts only run on FRESH database volumes**
   - If you use `docker-compose down` (without `-v`), the volume persists and scripts won't run again
   - Use `docker-compose down -v` to remove volumes and trigger re-initialization

2. **User seeding happens at app startup**
   - The Python app seeds demo users when `SEED_DEMO_DATA=true` (default)
   - This is more reliable than SQL because SQLAlchemy creates the users table

3. **Organizations table is created here**
   - Required before users table (foreign key dependency)
   - Other tables are created by SQLAlchemy models

4. **KB/RAG System Auto-Setup**
   - KB categories (4 age groups) are auto-seeded
   - knowledge_documents view is auto-created
   - document_chunks table is auto-created
   - Users add their own Level 2 and 3 categories via KB Sandbox

## Validation

After starting the system, validate the setup:

```bash
# Run validation script
./scripts/validate_kb_setup.sh

# Or manually check
docker exec healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -c "\dt"
docker exec healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -c "SELECT * FROM kb_categories;"
```

## Manual Reset

To reset the database completely:

```bash
cd healthcare_ai_live2d_unified

# Option 1: Remove volumes and rebuild
docker-compose down -v
docker-compose up -d

# Option 2: Manual SQL reset (preserves volume)
docker cp sql/reset_and_seed_demo_data.sql healthcare_ai_postgres:/tmp/
docker exec healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -f /tmp/reset_and_seed_demo_data.sql
docker-compose restart healthcare_ai
```

## Cloud Deployment

For cloud-hosted PostgreSQL (AWS RDS, Azure, etc.):

1. Run `02-schema.sql` manually to create the organizations table
2. Set `SEED_DEMO_DATA=true` in environment for initial setup
3. After setup, set `SEED_DEMO_DATA=false` in production

## Default Credentials

After initialization, login with:
- **URL**: `http://localhost:8000/live2d/auth`
- **Username**: `admin`
- **Password**: `admin`

See `docs/DEMO_USERS_CREDENTIALS.md` for all demo users.

