-- ==============================================================================
-- TORK AI VISUALIZER & ASSISTANT (KAZAKHSTAN MVP 1.0)
-- PostgreSQL Initialization DDL & Seed Data (Strictly Kazakhstan / KZT)
-- ==============================================================================

-- 1. Справочник дистрибьюторов в Казахстане
CREATE TABLE IF NOT EXISTS distributors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    bin VARCHAR(12),
    city VARCHAR(100) NOT NULL,
    country VARCHAR(50) DEFAULT 'KZ' NOT NULL,
    currency VARCHAR(10) DEFAULT 'KZT' NOT NULL CHECK (currency = 'KZT'),
    address VARCHAR(255),
    contact_phone VARCHAR(50),
    contact_email VARCHAR(100),
    manager_tg_chat_id VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE
);

-- 2. Каталог продукции Tork (Essity)
CREATE TABLE IF NOT EXISTS products (
    sku VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(20) NOT NULL CHECK (category IN ('dispenser', 'refill')),
    product_type VARCHAR(30) NOT NULL CHECK (product_type IN ('hand_towel', 'soap', 'toilet_paper', 'bin', 'air_freshener')),
    system_code VARCHAR(10) NOT NULL,
    design_line VARCHAR(50),
    color VARCHAR(30) CHECK (color IN ('white', 'black', 'stainless_steel', 'none')),
    traffic_level VARCHAR(20) CHECK (traffic_level IN ('low', 'medium', 'high', 'any')),
    dimensions_cm JSONB,
    refill_norms JSONB,
    image_clean_path VARCHAR(255),
    image_catalog_url VARCHAR(255),
    is_focus_item BOOLEAN DEFAULT FALSE,
    description TEXT
);

-- 3. Региональные цены и остатки дистрибьюторов (KZT)
CREATE TABLE IF NOT EXISTS distributor_prices (
    id SERIAL PRIMARY KEY,
    distributor_id INT REFERENCES distributors(id) ON DELETE CASCADE,
    product_sku VARCHAR(50) REFERENCES products(sku) ON DELETE CASCADE,
    price NUMERIC(12, 2) NOT NULL,
    in_stock BOOLEAN DEFAULT TRUE,
    UNIQUE(distributor_id, product_sku)
);

-- 4. Сессии пользователей Telegram, стейт-машина и лиды
CREATE TABLE IF NOT EXISTS user_sessions_leads (
    id SERIAL PRIMARY KEY,
    tg_user_id BIGINT NOT NULL UNIQUE,
    tg_username VARCHAR(100),
    client_name VARCHAR(150),
    company_name VARCHAR(150),
    phone VARCHAR(50),
    distributor_id INT REFERENCES distributors(id) DEFAULT 1,
    business_segment VARCHAR(50),
    daily_traffic INT,
    current_step VARCHAR(50) DEFAULT 'START',
    renders_today INT DEFAULT 0,
    last_render_date DATE DEFAULT CURRENT_DATE,
    last_photo_file_id VARCHAR(255),
    selected_bundle JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для ускорения детерминированного подбора
CREATE INDEX IF NOT EXISTS idx_products_lookup 
ON products(category, product_type, color, system_code, is_focus_item);

CREATE INDEX IF NOT EXISTS idx_distributor_prices_lookup 
ON distributor_prices(distributor_id, product_sku, in_stock);

CREATE INDEX IF NOT EXISTS idx_user_sessions_tg_id 
ON user_sessions_leads(tg_user_id);


-- ==============================================================================
-- SEED DATA: 3 ДИСТРИБЬЮТОРА В КАЗАХСТАНЕ (АСТАНА, АЛМАТЫ, ШЫМКЕНТ)
-- ==============================================================================
INSERT INTO distributors (id, name, bin, city, country, currency, address, contact_phone, contact_email, manager_tg_chat_id, is_active)
VALUES
(
    1,
    'ТОО "Tork Kazakhstan Distribution Astana"',
    '210540032111',
    'Астана',
    'KZ',
    'KZT',
    'г. Астана, район Есиль, ул. Достык, 18, БЦ "Москва", офис 704',
    '+7 (7172) 79-55-01',
    'astana@tork-distrib.kz',
    '-100200300400',
    TRUE
),
(
    2,
    'ТОО "Tork Distribution Almaty"',
    '190340019882',
    'Алматы',
    'KZ',
    'KZT',
    'г. Алматы, пр. Аль-Фараби, 77/7, БЦ "Esentai Tower", блок 2',
    '+7 (727) 355-88-22',
    'almaty@tork-distrib.kz',
    '-100200300401',
    TRUE
),
(
    3,
    'ТОО "Tork South Industrial KZ"',
    '220140045671',
    'Шымкент',
    'KZ',
    'KZT',
    'г. Шымкент, Абайский р-н, ул. Байтерекова, 25, БЦ "Орда"',
    '+7 (7252) 99-44-11',
    'shymkent@tork-distrib.kz',
    '-100200300402',
    TRUE
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    bin = EXCLUDED.bin,
    city = EXCLUDED.city,
    address = EXCLUDED.address,
    contact_phone = EXCLUDED.contact_phone,
    contact_email = EXCLUDED.contact_email,
    manager_tg_chat_id = EXCLUDED.manager_tg_chat_id;

SELECT setval('distributors_id_seq', (SELECT MAX(id) FROM distributors));


-- ==============================================================================
-- SEED DATA: 8 БАЗОВЫХ ФОКУСНЫХ ПОЗИЦИЙ TORK (H1, S4, T8)
-- ==============================================================================
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line, 
    color, traffic_level, dimensions_cm, refill_norms, 
    image_clean_path, image_catalog_url, is_focus_item, description
)
VALUES
-- Система H1: Полотенца для рук в рулонах Matic Elevation
(
    '551000',
    'Диспенсер Tork Matic® для полотенец в рулонах белый (Elevation H1)',
    'dispenser',
    'hand_towel',
    'H1',
    'Elevation',
    'white',
    'any',
    '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb,
    NULL,
    '/data/assets/dispensers/551000.png',
    'https://www.tork.kz/product/551000/dispenser/hand-towel',
    TRUE,
    'Полистовой отбор рулонных полотенец. Идеален для санузлов с высокой проходимостью. Ударопрочный пластик.'
),
(
    '551008',
    'Диспенсер Tork Matic® для полотенец в рулонах черный (Elevation H1)',
    'dispenser',
    'hand_towel',
    'H1',
    'Elevation',
    'black',
    'any',
    '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb,
    NULL,
    '/data/assets/dispensers/551008.png',
    'https://www.tork.kz/product/551008/dispenser/hand-towel',
    TRUE,
    'Премиальный черный глянцевый диспенсер для рулонных полотенец системы H1. Защита от перерасхода до 37%.'
),
(
    '290067',
    'Полотенца в рулонах Tork Matic® ультрамягкие 2-сл. (Advanced H1)',
    'refill',
    'hand_towel',
    'H1',
    'Advanced',
    'none',
    'any',
    NULL,
    '{"portions_per_unit": 600, "daily_use_per_person": 2.5, "unit_name": "рулон"}'::jsonb,
    '/data/assets/dispensers/290067.png',
    'https://www.tork.kz/product/290067/refill/hand-towel',
    TRUE,
    'Мягкие белые полотенца с тиснением. 6 рулонов в коробе по 150 метров. Высокая впитываемость QuickDry.'
),
-- Система S4: Мыло-пена Elevation Intuition
(
    '561500',
    'Диспенсер для мыла-пены Tork с сенсором Intuition™ белый (Elevation S4)',
    'dispenser',
    'soap',
    'S4',
    'Elevation',
    'white',
    'any',
    '{"w": 11.3, "h": 28.6, "d": 10.5}'::jsonb,
    NULL,
    '/data/assets/dispensers/561500.png',
    'https://www.tork.kz/product/561500/dispenser/soap',
    TRUE,
    'Бесконтактный сенсорный дозатор мыла-пены. Обеспечивает высокий уровень гигиены и экономию расхода.'
),
(
    '561508',
    'Диспенсер для мыла-пены Tork с сенсором Intuition™ черный (Elevation S4)',
    'dispenser',
    'soap',
    'S4',
    'Elevation',
    'black',
    'any',
    '{"w": 11.3, "h": 28.6, "d": 10.5}'::jsonb,
    NULL,
    '/data/assets/dispensers/561508.png',
    'https://www.tork.kz/product/561508/dispenser/soap',
    TRUE,
    'Черный сенсорный диспенсер для мыла-пены Tork Elevation S4 Intuition. Сертифицирован по системе Easy-to-use.'
),
(
    '520501',
    'Мягкое мыло-пена Tork Премиум 1000 мл (Система S4)',
    'refill',
    'soap',
    'S4',
    'Premium',
    'none',
    'any',
    NULL,
    '{"portions_per_unit": 2500, "daily_use_per_person": 1.8, "unit_name": "картридж 1000 мл"}'::jsonb,
    '/data/assets/dispensers/520501.png',
    'https://www.tork.kz/product/520501/refill/soap',
    TRUE,
    'Герметичный одноразовый картридж со встроенной помпой 1000 мл (2500 доз мыла-пены).'
),
-- Система T8: Туалетная бумага SmartOne Elevation
(
    '680000',
    'Диспенсер для туалетной бумаги Tork SmartOne® белый (Elevation T8)',
    'dispenser',
    'toilet_paper',
    'T8',
    'Elevation',
    'white',
    'any',
    '{"w": 26.9, "h": 26.9, "d": 15.6}'::jsonb,
    NULL,
    '/data/assets/dispensers/680000.png',
    'https://www.tork.kz/product/680000/dispenser/toilet-paper',
    TRUE,
    'Ударопрочный диспенсер с полистовой подачей туалетной бумаги. Снижает расход бумаги до 40%.'
),
(
    '680008',
    'Диспенсер для туалетной бумаги Tork SmartOne® черный (Elevation T8)',
    'dispenser',
    'toilet_paper',
    'T8',
    'Elevation',
    'black',
    'any',
    '{"w": 26.9, "h": 26.9, "d": 15.6}'::jsonb,
    NULL,
    '/data/assets/dispensers/680008.png',
    'https://www.tork.kz/product/680008/dispenser/toilet-paper',
    TRUE,
    'Черный антивандальный диспенсер Tork SmartOne T8. Надежная защита рулона от внешних воздействий.'
),
(
    '472242',
    'Туалетная бумага в рулонах Tork SmartOne® 2-сл. (Advanced T8)',
    'refill',
    'toilet_paper',
    'T8',
    'Advanced',
    'none',
    'any',
    NULL,
    '{"portions_per_unit": 1150, "daily_use_per_person": 4.0, "unit_name": "рулон"}'::jsonb,
    '/data/assets/dispensers/472242.png',
    'https://www.tork.kz/product/472242/refill/toilet-paper',
    TRUE,
    '2-слойная туалетная бумага с центральной вытяжкой, 1150 листов в рулоне. Быстро растворяется в воде.'
)
ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    image_clean_path = EXCLUDED.image_clean_path,
    image_catalog_url = EXCLUDED.image_catalog_url,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description;


-- ==============================================================================
-- SEED DATA: ПРАЙС-ЛИСТ В ТЕНГЕ (KZT) ДЛЯ ВСЕХ 3 ДИСТРИБЬЮТОРОВ (ID 1, 2, 3)
-- ==============================================================================
-- Базовые согласованные цены Tork в Казахстане (в тенге с НДС)
INSERT INTO distributor_prices (distributor_id, product_sku, price, in_stock)
SELECT dist.id, p.sku, p.price, TRUE
FROM (VALUES (1), (2), (3)) AS dist(id)
CROSS JOIN (
    VALUES
        ('551000', 42500.00::numeric),
        ('551008', 42500.00::numeric),
        ('290067',  7850.00::numeric),
        ('561500', 38900.00::numeric),
        ('561508', 38900.00::numeric),
        ('520501',  5450.00::numeric),
        ('680000', 29800.00::numeric),
        ('680008', 29800.00::numeric),
        ('472242',  4600.00::numeric)
) AS p(sku, price)
ON CONFLICT (distributor_id, product_sku) DO UPDATE SET
    price = EXCLUDED.price,
    in_stock = EXCLUDED.in_stock;

