#!/bin/bash
# Auto-run by postgres on first start
# Creates cmdb database and initializes schema

set -e

echo "🔧 Creating cmdb database..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres -c "CREATE DATABASE cmdb;"

echo "📋 Initializing cmdb schema..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname cmdb -f /docker-entrypoint-initdb.d/schema.sql

echo "✅ CMDB initialization complete"
