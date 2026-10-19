-- ==============================================================================
-- SPRINT 1 MIGRATION: DASHBOARD USERS & ORDER MANAGEMENT (RBAC)
-- ==============================================================================

-- 1. Таблица пользователей панели управления
CREATE TABLE IF NOT EXISTS dashboard_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    organization VARCHAR(150) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('vendor_admin', 'distributor_manager')),
    distributor_id INT REFERENCES distributors(id) ON DELETE SET NULL, -- NULL для вендора Tork
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dashboard_users_email ON dashboard_users(email);

-- 2. Расширение таблицы user_sessions_leads для управления заказами
ALTER TABLE user_sessions_leads 
ADD COLUMN IF NOT EXISTS order_status VARCHAR(50) DEFAULT 'NEW' 
CHECK (order_status IN ('NEW', 'IN_PROGRESS', 'INVOICE_SENT', 'TEST_DRIVE', 'COMPLETED', 'CANCELLED'));

ALTER TABLE user_sessions_leads 
ADD COLUMN IF NOT EXISTS manager_notes TEXT DEFAULT '';

ALTER TABLE user_sessions_leads 
ADD COLUMN IF NOT EXISTS kp_number VARCHAR(50);
