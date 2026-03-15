#!/bin/bash
# ===================================================================
# Healthcare AI - Database Initialization Script
# ===================================================================
# This script runs automatically when the PostgreSQL Docker container
# is first created with an empty data volume.
# ===================================================================

set -e

echo "════════════════════════════════════════════════════════════════"
echo "  Healthcare AI Database Initialization"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📦 Database: $POSTGRES_DB"
echo "👤 User: $POSTGRES_USER"
echo ""
echo "📋 Init scripts will run in order:"
echo "  1️⃣  01-init-database.sh (this script)"
echo "  2️⃣  02-schema.sql (organizations table)"
echo "  3️⃣  03-seed-data.sql (demo users)"
echo ""
echo "�?Database initialization starting..."
echo ""
