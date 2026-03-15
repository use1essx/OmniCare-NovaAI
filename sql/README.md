# SQL Scripts Directory

Database setup and maintenance scripts for the Healthcare AI system.

## File Structure

```
sql/
├── 00_complete_database_setup.sql   # Master setup - creates ALL tables
├── 01_create_super_admin.sql        # Quick admin user fix
├── reset_and_seed_demo_data.sql     # Demo data for testing
├── README.md                        # This file
└── pgadmin_queries/                 # Admin reference queries
    ├── common_operations.sql        # Common admin operations
    └── healthcare_dashboard.sql     # Dashboard monitoring queries
```

## Quick Start

### Complete Database Setup (Recommended)

```bash
# Using psql
psql $DATABASE_URL < sql/00_complete_database_setup.sql

# Or in Docker
docker exec -it hiyori_postgres psql -U admin -d healthcare_ai_v2 -f /path/to/00_complete_database_setup.sql
```

This creates all 15+ tables with:
- Timestamps (`created_at`, `updated_at`) with auto-update triggers
- Organizations and RBAC permissions
- Foreign keys and constraints
- Performance indexes
- Default super admin user

### Quick Login Fix

If you just need to fix admin login:

```bash
psql $DATABASE_URL < sql/01_create_super_admin.sql
```

**Default Credentials:**
- Username: `admin`
- Password: `admin`
- ⚠️ Change password in production!

### Demo Data

For testing with sample data:

```bash
psql $DATABASE_URL < sql/reset_and_seed_demo_data.sql
```

## File Descriptions

| File | Purpose |
|------|---------|
| `00_complete_database_setup.sql` | Master script - creates all tables, triggers, indexes |
| `01_create_super_admin.sql` | Creates/resets super admin user |
| `reset_and_seed_demo_data.sql` | Seeds demo organizations, users, and test data |
| `pgadmin_queries/` | Reference queries for monitoring and admin tasks |

## Safety Notes

- All scripts are idempotent (safe to run multiple times)
- Use `IF NOT EXISTS` and `ON CONFLICT` clauses
- No data loss when re-running setup scripts

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Can't login | Run `01_create_super_admin.sql` |
| Missing tables | Run `00_complete_database_setup.sql` |
| Need test data | Run `reset_and_seed_demo_data.sql` |
