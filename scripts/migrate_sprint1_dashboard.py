#!/usr/bin/env python3
"""
Sprint 1 Database Migration & Seeding Script
Creates dashboard_users table, extends user_sessions_leads, and seeds initial RBAC users.
"""
import os
import sys
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt

# Determine project root and load .env if available
ROOT_DIR = Path(__file__).resolve().parent.parent
env_file = ROOT_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_DB = os.getenv("POSTGRES_DB", "tork_bot_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "tork_admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "tork_db_pass_2026")

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def run_migration():
    print(f"Connecting to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}...")
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )
    conn.autocommit = True
    cur = conn.cursor()

    print("Step 1: Creating table dashboard_users...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(150) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(150) NOT NULL,
            organization VARCHAR(150) NOT NULL,
            role VARCHAR(50) NOT NULL CHECK (role IN ('vendor_admin', 'distributor_manager')),
            distributor_id INT REFERENCES distributors(id) ON DELETE SET NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_dashboard_users_email ON dashboard_users(email);
    """)

    print("Step 2: Extending user_sessions_leads with order fields...")
    cur.execute("""
        ALTER TABLE user_sessions_leads 
        ADD COLUMN IF NOT EXISTS order_status VARCHAR(50) DEFAULT 'NEW' 
        CHECK (order_status IN ('NEW', 'IN_PROGRESS', 'INVOICE_SENT', 'TEST_DRIVE', 'COMPLETED', 'CANCELLED'));

        ALTER TABLE user_sessions_leads 
        ADD COLUMN IF NOT EXISTS manager_notes TEXT DEFAULT '';

        ALTER TABLE user_sessions_leads 
        ADD COLUMN IF NOT EXISTS kp_number VARCHAR(50);
    """)

    print("Step 3: Seeding initial RBAC dashboard users...")
    initial_password = "TorkKZ2026!"
    hashed_pwd = hash_password(initial_password)

    users_to_seed = [
        {
            "email": "admin@tork.kz",
            "full_name": "Администратор Tork Казахстан",
            "organization": "Essity / Tork Central Asia",
            "role": "vendor_admin",
            "distributor_id": None,
        },
        {
            "email": "astana@tork.kz",
            "full_name": "Менеджер Tork Астана",
            "organization": 'ТОО "Tork Kazakhstan Distribution Astana"',
            "role": "distributor_manager",
            "distributor_id": 1,
        },
        {
            "email": "almaty@tork.kz",
            "full_name": "Менеджер Tork Алматы",
            "organization": 'ТОО "Tork Distribution Almaty"',
            "role": "distributor_manager",
            "distributor_id": 2,
        },
        {
            "email": "shymkent@tork.kz",
            "full_name": "Менеджер Tork Шымкент",
            "organization": 'ТОО "Tork South Industrial KZ"',
            "role": "distributor_manager",
            "distributor_id": 3,
        },
    ]

    for u in users_to_seed:
        cur.execute("""
            INSERT INTO dashboard_users (email, password_hash, full_name, organization, role, distributor_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (email) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                full_name = EXCLUDED.full_name,
                organization = EXCLUDED.organization,
                role = EXCLUDED.role,
                distributor_id = EXCLUDED.distributor_id,
                is_active = TRUE;
        """, (
            u["email"],
            hashed_pwd,
            u["full_name"],
            u["organization"],
            u["role"],
            u["distributor_id"],
        ))
        print(f"  - User {u['email']} ({u['role']}, dist_id={u['distributor_id']}) seeded.")

    # Verification query
    cur.execute("SELECT id, email, full_name, role, distributor_id, is_active FROM dashboard_users ORDER BY id;")
    users = cur.fetchall()
    print("\nVerification: Current dashboard users in DB:")
    for user in users:
        print(f"  ID {user[0]}: {user[1]} | {user[2]} | Role: {user[3]} | Dist: {user[4]} | Active: {user[5]}")

    cur.close()
    conn.close()
    print("\nMigration completed successfully!")

if __name__ == "__main__":
    run_migration()
