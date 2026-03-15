#!/bin/bash
# ===================================================================
# OmniCare Healthcare AI - Database Initialization Orchestrator
# ===================================================================
# This script runs automatically when the PostgreSQL Docker container
# is first created with an empty data volume.
# ===================================================================

set -e

echo "════════════════════════════════════════════════════════════════"
echo "  OmniCare Healthcare AI - Database Initialization"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📦 Database: $POSTGRES_DB"
echo "👤 User: $POSTGRES_USER"
echo ""
echo "📋 Initialization Steps:"
echo "  1️⃣  Create extensions and helper functions"
echo "  2️⃣  Create organizations table"
echo "  3️⃣  Insert seed data (4 organizations)"
echo "  4️⃣  Application will create remaining tables"
echo "  5️⃣  Super admin user will be created automatically"
echo ""
echo "🚀 Starting initialization..."
echo ""
