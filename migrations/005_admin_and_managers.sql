-- ==============================================================================
-- MIGRATION 005: ADMIN PANEL, MANAGERS RBAC & CUSTOM KZT PRICING
-- ==============================================================================

-- 1. Таблица авторизованных менеджеров и администраторов Telegram
CREATE TABLE IF NOT EXISTS allowed_managers (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    username VARCHAR(100),
    role VARCHAR(50) DEFAULT 'manager' CHECK (role IN ('superadmin', 'admin', 'manager')),
    is_active BOOLEAN DEFAULT TRUE,
    created_by BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индекс для быстрого поиска по telegram_id
CREATE INDEX IF NOT EXISTS idx_allowed_managers_tg_id ON allowed_managers(telegram_id);

-- Первоначальное наполнение из списка разрешенных ID (суперадмины)
INSERT INTO allowed_managers (telegram_id, full_name, username, role, is_active)
VALUES 
    (5699064827, 'Главный Администратор (Директор)', 'tork_director', 'superadmin', true),
    (7390702902, 'Администратор Tork РК', 'tork_admin_kz', 'superadmin', true),
    (1248663402, 'Менеджер Tork Казахстан', 'tork_manager_kz', 'superadmin', true)
ON CONFLICT (telegram_id) DO UPDATE SET 
    role = EXCLUDED.role,
    is_active = true,
    updated_at = NOW();

-- 2. Добавление колонок в таблицу products
ALTER TABLE products 
ADD COLUMN IF NOT EXISTS custom_price_kzt NUMERIC(12, 2);

ALTER TABLE products 
ADD COLUMN IF NOT EXISTS is_active_in_catalog BOOLEAN DEFAULT TRUE;

COMMENT ON COLUMN products.custom_price_kzt IS 'Фиксированная цена в KZT (₸), переопределяющая автоматический расчет из EUR';
COMMENT ON COLUMN products.is_active_in_catalog IS 'Флаг активности товара в каталоге Mini App';

-- 3. Обновление представления v_products_active с приоритетом custom_price_kzt
DROP VIEW IF EXISTS v_products_active CASCADE;
CREATE VIEW v_products_active AS
SELECT 
    p.sku,
    p.name,
    p.category,
    p.product_type,
    p.system_code,
    p.design_line,
    p.color,
    p.traffic_level,
    p.dimensions_cm,
    p.refill_norms,
    p.image_clean_path,
    p.image_catalog_url,
    p.is_focus_item,
    p.description,
    p.price_eur,
    p.custom_price_kzt,
    p.priority_rank,
    p.margin_tier,
    p.segment_fit,
    p.is_promo,
    COALESCE(p.image_url, 'http://cdn/images/' || p.sku || '.png') AS image_url,
    COALESCE(
        p.custom_price_kzt,
        ROUND(p.price_eur * COALESCE(
            (SELECT rate FROM exchange_rates WHERE currency_from = 'EUR' AND currency_to = 'KZT' ORDER BY updated_at DESC LIMIT 1),
            617.9300
        ), 2)
    ) AS current_price_kzt,
    COALESCE(p.is_active_in_catalog, true) AS is_active_in_catalog
FROM products p;
