# PostgreSQL Docker Auto-Initialization

## 🤖 Automatic Setup

When you run `docker-compose up` for the **first time**, the PostgreSQL database will automatically:

- ✅ Create all tables with timestamps
- ✅ Add auto-update triggers to all tables
- ✅ Set up organizations table
- ✅ Configure foreign keys and relationships
- ✅ Add 30+ performance indexes
- ✅ Create super admin user (admin/admin)
- ✅ Verify data integrity

**No manual SQL execution needed!** 🎉

---

## 📁 How It Works

PostgreSQL Docker automatically runs scripts in `/docker-entrypoint-initdb.d/`:

```
docker/postgres/initdb.d/
├── 01-init-database.sh      # Initialization message
└── 02-complete-setup.sql    # Complete database setup
```

Scripts run in **alphabetical order** when the database is **first created**.

---

## 🚀 First Time Setup

### Step 1: Start Docker

```bash
docker-compose up -d
```

That's it! The database auto-setup runs automatically! 🎉

### Step 2: Check Logs

Watch the initialization:

```bash
docker-compose logs -f postgres
```

Look for:
```
════════════════════════════════════════════════════════════════
  Healthcare AI Database Initialization
════════════════════════════════════════════════════════════════

🚀 Starting automatic database setup...
📦 Database: healthcare_ai_v2
👤 User: admin

✅ Database initialization script will run next...

...

═══════════════════════════════════════════════════
     ✅ COMPLETE DATABASE SETUP FINISHED! ✅
═══════════════════════════════════════════════════
```

### Step 3: Login

Go to: `http://localhost:8000/live2d/auth`

- **Username:** `admin`
- **Password:** `admin`

✅ Done!

---

## 🔄 Re-initializing Existing Database

### ⚠️ Warning: This will DELETE all data!

If you already have a database and want to reinitialize it:

### Option 1: Using Helper Script (Recommended)

```bash
./docker/postgres/reinit-database.sh
```

This script will:
1. Stop containers
2. Delete database volume
3. Restart containers
4. Auto-setup runs again

### Option 2: Manual Steps

```bash
# Stop containers
docker-compose down

# Remove ONLY the database volume (keeps pgadmin data)
docker volume rm healthcare_ai_live2d_unified_postgres_data

# Start again (auto-setup runs)
docker-compose up -d

# Watch logs
docker-compose logs -f postgres
```

---

## 🛠️ Running Setup on Existing Database

If you have an existing database with data and want to add the auto-setup features without deleting data:

### Option 1: Use pgAdmin

1. Open pgAdmin: `http://localhost:5050`
2. Connect to `healthcare_ai_v2`
3. Open Query Tool
4. Run: `sql/00_complete_database_setup.sql`

### Option 2: Using Docker Exec

```bash
# Copy SQL file to container
docker cp sql/00_complete_database_setup.sql healthcare_ai_postgres:/tmp/

# Execute SQL
docker exec -it healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -f /tmp/00_complete_database_setup.sql
```

---

## 📊 Verification

Check if auto-setup ran successfully:

### Check Tables

```bash
docker exec -it healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -c "\dt"
```

Should show 15+ tables.

### Check Admin User

```bash
docker exec -it healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -c "SELECT username, role, is_super_admin FROM users WHERE username='admin';"
```

Should show:
```
 username |    role     | is_super_admin 
----------+-------------+----------------
 admin    | super_admin | t
```

### Check Auto-Features

```bash
docker exec -it healthcare_ai_postgres psql -U admin -d healthcare_ai_v2 -c "SELECT table_name FROM information_schema.columns WHERE column_name='updated_at' GROUP BY table_name ORDER BY table_name;"
```

Should show 11+ tables with `updated_at`.

---

## 🐛 Troubleshooting

### Auto-setup didn't run?

**Check:** Did you start with an existing database?

Init scripts only run when the database is **first created**. If you already have a `postgres_data` volume, the scripts won't run.

**Solution:** Reinitialize the database (see above).

### Can't login with admin/admin?

**Check logs:**
```bash
docker-compose logs postgres | grep "admin"
```

**Solution:** Run setup manually (see above).

### Tables don't have timestamps?

**Check:** Was the database created before adding init scripts?

**Solution:** Run `sql/00_complete_database_setup.sql` manually.

---

## 📁 Files

- `initdb.d/01-init-database.sh` - Initialization banner
- `initdb.d/02-complete-setup.sql` - Complete database setup
- `reinit-database.sh` - Helper script to reinitialize
- `README.md` - This file

---

## 🔗 Related Documentation

- `../../sql/README.md` - SQL scripts documentation
- `../../AUTO_SETUP_FEATURES.md` - Explanation of auto features
- `../../QUICK_FIX_LOGIN.md` - Quick reference
- `../../sql/HOW_TO_RUN_IN_PGADMIN.md` - pgAdmin guide

---

## 💡 Pro Tips

1. **First time setup:** Just run `docker-compose up -d` - everything auto-configures!
2. **Clean slate:** Use `./docker/postgres/reinit-database.sh` to start fresh
3. **Keep data:** Use pgAdmin to run setup scripts on existing database
4. **Check logs:** Always check `docker-compose logs postgres` if something seems wrong
5. **Backup first:** Before reinitializing, backup your data!

---

**The database now auto-sets up just like pgAdmin!** 🎉🤖

