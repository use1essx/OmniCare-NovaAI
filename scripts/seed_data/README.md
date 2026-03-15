# Database Seed Data

This directory contains default database seed data that can be used to initialize a fresh database with pre-configured data.

## Quick Start

### Export Current Database Data

```bash
# From project root
docker-compose exec healthcare_ai python scripts/export_database_seed.py
```

### Seed a Fresh Database

```bash
# From project root
docker-compose exec healthcare_ai python scripts/seed_data/seed_default_data.py
```

## Files

- `default_data.json` - Raw exported data in JSON format
- `seed_default_data.py` - Python script to seed the database
- `README.md` - This file

## What Data is Included

The seed data includes:
- Organizations (hospitals, clinics, care facilities)
- Live2D Models (avatar configurations)
- Assessment Rules (health screening rules)
- Knowledge Base Categories (document organization)

## Usage Workflow

1. **On Device A (with data):**
   ```bash
   # Export data
   docker-compose exec healthcare_ai python scripts/export_database_seed.py
   
   # Commit to Git
   git add scripts/seed_data/
   git commit -m "Update seed data"
   git push origin Host
   ```

2. **On Device B (fresh setup):**
   ```bash
   # Pull latest code
   git pull origin Host
   
   # Start Docker
   docker-compose up -d
   
   # Seed database
   docker-compose exec healthcare_ai python scripts/seed_data/seed_default_data.py
   ```

## Security Notes

⚠️ **Important:** This seed data is committed to Git and will be public if your repository is public.

- ✅ Only include demo/test data
- ❌ Never include real user data
- ❌ Never include passwords or API keys
- ❌ Never include personal information (PII/PHI)

## Customization

To export additional tables, edit `scripts/export_database_seed.py` and add to the `EXPORT_TABLES` list:

```python
EXPORT_TABLES = [
    ('organizations', Organization),
    ('live2d_models', Live2DModel),
    # Add your tables here
    ('your_table', YourModel),
]
```

## Documentation

For detailed instructions, see: `docs/DATABASE_SEED_GUIDE.md`
