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
-- MIGRATION V2: SCORING, RANKING, EXCHANGE RATES, NGINX CDN & 165 PRODUCTS
-- ==============================================================================

-- 1. Table exchange_rates
CREATE TABLE IF NOT EXISTS exchange_rates (
    id SERIAL PRIMARY KEY,
    currency_from VARCHAR(3) NOT NULL,
    currency_to VARCHAR(3) NOT NULL,
    rate NUMERIC(10, 4) NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(currency_from, currency_to)
);

INSERT INTO exchange_rates (currency_from, currency_to, rate)
VALUES ('EUR', 'KZT', 617.9300)
ON CONFLICT (currency_from, currency_to) DO UPDATE SET rate = EXCLUDED.rate, updated_at = NOW();

-- 2. Drop constraints if needed to support all categories
ALTER TABLE products DROP CONSTRAINT IF EXISTS products_product_type_check;
ALTER TABLE products DROP CONSTRAINT IF EXISTS products_color_check;

-- 3. Add new columns to products
ALTER TABLE products ADD COLUMN IF NOT EXISTS price_eur NUMERIC(12, 4);
ALTER TABLE products ADD COLUMN IF NOT EXISTS priority_rank INT DEFAULT 100;
ALTER TABLE products ADD COLUMN IF NOT EXISTS margin_tier VARCHAR(8) DEFAULT 'B';
ALTER TABLE products ADD COLUMN IF NOT EXISTS segment_fit TEXT[] DEFAULT '{}';
ALTER TABLE products ADD COLUMN IF NOT EXISTS is_promo BOOLEAN DEFAULT FALSE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT;

-- 4. Upsert all 165 products
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '551000', 'Tork Matic® диспенсер полотенец для рук в рулоне, белый, система H1', 'dispenser', 'hand_towel', 'H1', 'Elevation',
    'white', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    TRUE, 'Диспенсер Tork Matic® для полотенец для рук в рулонах серии Elevation — простая в обслуживании и экономичная система с полистовым отбором для туалетных комнат высокой проходимости. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших гостей.', 212.5483, 10,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/551000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '551008', 'Tork Matic® диспенсер полотенец для рук в рулоне, черный, система H1', 'dispenser', 'hand_towel', 'H1', 'Elevation',
    'black', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    TRUE, 'Диспенсер Tork Matic® для полотенец для рук в рулонах серии Elevation — простая в обслуживании и экономичная система с полистовым отбором для туалетных комнат высокой проходимости. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших гостей.', 212.5483, 10,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/551008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '290016', 'Tork Matic® мягкие бумажные полотенца для рук, белые, синий лиственный узор, система H1', 'refill', 'hand_towel', 'H1', 'Elevation',
    'white', 'high', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    TRUE, 'Мягкие полотенца Tork Matic® качества Premium с красивым тиснением в форме голубых листов отлично подходят для туалетных комнат премиум-класса. Полотенца QuickDry™ обладают более высокой прочностью и лучше сохраняют прочность во влажном состоянии в сравнении с обычными бумажными полотенцами. Предназначены для использования в диспенсерах Tork Matic® для полотенец в рулонах. Диспенсеры просты в обслуживании и оптимальны для туалетных комнат с большим количеством посетителей. Полистовой отбор позво', 6.9956, 10,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/290016.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '290067', 'Tork Matic® мягкие бумажные полотенца для рук, белые, серый лиственный узор, система H1', 'refill', 'hand_towel', 'H1', 'Elevation',
    'white', 'high', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    TRUE, 'Подарите вашим гостям комфорт с мягкими рулонными полотенцами для рук Tork Matic® качества Advanced. Полотенца, украшенные серыми фирменными листочками Tork, хорошо впитывают и приятные на ощупь, так как 1 слой бумаги QuickDry™ . Предназначены для использования в диспенсерах для полотенец в рулонах Tork Matic®. Диспенсеры просты в обслуживании и оптимальны для туалетных комнат с большим количеством посетителей. Полистовой отбор позволяет экономить время и контролировать расход полотенец.', 6.419, 10,
    'C', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/290067.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '290059', 'Tork Matic® бумажные полотенца для рук в больших рулонах, белые, система H1', 'refill', 'hand_towel', 'H1', 'Elevation',
    'white', 'high', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Мягкие полотенца в ультрадлинных рулонах Tork Matic® отлично подходят для туалетных комнат с высокой проходимостью в таких местах, как школы и аэропорты. Предназначены для использования в диспенсерах Tork Matic® для полотенец в рулонах. Диспенсеры просты в обслуживании и оптимальны для туалетных комнат с большим количеством посетителей.', 11.6198, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/290059.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '552000', 'Tork Xpress® диспенсер для листовых полотенец Multifold', 'dispenser', 'hand_towel', 'H2', 'Elevation',
    'white', 'medium', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork Xpress® диспенсер для листовых полотенец Multifold серии Elevation подходит для помещений с высокими требованиями к уровню комфорта и гигиены. Ультратонкий привлекательный дизайн, минимум отходов и полистовой отбор. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности и положительные впечатления ваших гостей.', 71.4265, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/552000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '552008', 'Tork Xpress® диспенсер для листовых полотенец Multifold', 'dispenser', 'hand_towel', 'H2', 'Elevation',
    'black', 'medium', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork Xpress® диспенсер для листовых полотенец Multifold серии Elevation подходит для помещений с высокими требованиями к уровню комфорта и гигиены. Ультратонкий привлекательный дизайн, минимум отходов и полистовой отбор. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности и положительные впечатления ваших гостей.', 71.4265, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/552008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '552100', 'Tork Xpress® мини-диспенсер для листовых полотенец Multifold', 'dispenser', 'hand_towel', 'H2', 'Elevation',
    'white', 'medium', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork Xpress® ​мини-диспенсер для листовых полотенец сложения Multifold серии Elevation подходит для помещений с высокими требованиями к уровню комфорта и гигиены. Этот тонкий и привлекательный диспенсер подходит для использования в туалетных комнатах с небольшой или средней проходимостью и ограниченным пространством, сокращая расход благодаря полистовому отбору. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших гостей.', 66.8971, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/552100.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '552108', 'Tork Xpress® мини-диспенсер для листовых полотенец Multifold', 'dispenser', 'hand_towel', 'H2', 'Elevation',
    'black', 'medium', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork Xpress® ​мини-диспенсер для листовых полотенец сложения Multifold серии Elevation подходит для помещений с высокими требованиями к уровню комфорта и гигиены. Этот тонкий и привлекательный диспенсер подходит для использования в туалетных комнатах с небольшой или средней проходимостью и ограниченным пространством, сокращая расход благодаря полистовому отбору. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших гостей.', 69.8139, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/552108.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '460004', 'Tork Xpress® диспенсер для полотенец Multifold', 'dispenser', 'hand_towel', 'H2', 'Image Line',
    'stainless_steel', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    TRUE, 'Современный дизайн, гладкая поверхность и четкие линии — безупречно впишется в интерьер вашей туалетной комнаты.
Производит изысканное впечатление и подчеркивает стильный интерьер.
Стильная поверхность из нержавеющей стали с защитным покрытием, на котором не остаются отпечатки пальцев, — всегда отлично выглядит и не пачкается.', 265.1459, 10,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/460004.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '460005', 'Tork Xpress® настольный диспенсер для полотенец Multifold', 'dispenser', 'hand_towel', 'H2', 'Image Line',
    'stainless_steel', 'medium', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Современный дизайн, гладкая поверхность и четкие линии — крючок для одежды безупречно впишется в интерьер вашей туалетной комнаты.
Производит изысканное впечатление и подчеркивает стильный интерьер.
Стильная поверхность из нержавеющей стали с защитным покрытием, на котором не остаются отпечатки пальцев, — всегда отлично выглядит и не пачкается.', 168.9146, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/460005.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '552200', 'Tork Xpress® настольный диспенсер для полотенец Multifold', 'dispenser', 'hand_towel', 'H2', 'Elevation',
    'white', 'medium', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork Xpress® настольный диспенсер для листовых полотенец Multifold серии Elevation — это прекрасная альтернатива стопкам полотенец на вашей раковине. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших гостей.', 100.6184, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/552200.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '552208', 'Tork Xpress® настольный диспенсер для полотенец Multifold', 'dispenser', 'hand_towel', 'H2', 'Elevation',
    'black', 'medium', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork Xpress® настольный диспенсер для листовых полотенец Multifold серии Elevation — это прекрасная альтернатива стопкам полотенец на вашей раковине. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших гостей.', 96.2313, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/552208.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '100297', 'Ультрамягкие листовые полотенца для рук Tork Xpress® Premium сложения Multifold, 100 л/пачка', 'refill', 'hand_towel', 'H2', 'Elevation',
    'white', 'high', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    TRUE, 'Большие экстрамягкие полотенца высокого качества Tork Xpress® сложения Multifold бережно высушивают руки и обеспечивают комфорт вашим гостям.  Для использования в диспенсерах Tork Xpress® для листовых полотенец Multifold, устанавливаемых в туалетных комнатах со средней проходимостью. Для установки диспенсера не требуется много места, он обеспечивает вашим гостям комфорт и высокий уровень гигиены.', 3.7942, 10,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/100297.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '100288', 'Tork Xpress® листовые полотенца Multifold мягкие, 110 л/пачка', 'refill', 'hand_towel', 'H2', 'Elevation',
    'white', 'high', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    TRUE, 'Большие и мягкие листовые полотенца Tork Xpress® сложения Multifold высокого качества бережно высушивают руки и обеспечивают комфорт вашим гостям. Для использования в диспенсерах Tork Xpress® для листовых полотенец сложения Multifold, устанавливаемых в туалетных комнатах со средней проходимостью. Для установки диспенсера не требуется много места, он обеспечивает вашим гостям комфорт и высокий уровень гигиены.', 3.0354, 10,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/100288.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '120454', 'Tork Xpress® спрессованные мягкие полотенца для рук сложения Multifold-M, 200 л/пачка', 'refill', 'hand_towel', 'H2', 'Elevation',
    'white', 'medium', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Увеличьте емкость диспенсеров меньшего размера, используя сжатые на 50% бумажные полотенца для рук. Эти большие бумажные полотенца для рук превосходно впитывают и отличаются высокой прочностью, поэтому гости используют меньше листов. Полистовой отбор помогает сократить отходы и повысить гигиену — гости касаются только листа, который используют. Сертификаты EU Ecolabel и FSC демонстрируют вашу приверженность принципам устойчивого развития. Для оптимальных впечатлений не используйте в сочетании с ', 3.2725, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/120454.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '100888', 'Tork Xpress® спрессованные мягкие полотенца для рук сложения Multifold-M, 170 л/пачка', 'refill', 'hand_towel', 'H2', 'Elevation',
    'white', 'medium', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Экономьте время на пополнении диспенсеров, используя сжимаемые на 50% полотенца для рук, которые удваивают емкость диспенсера. QuickDry™  Гостям понравятся эти мягкие и хорошо впитывающие полотенца для рук премиум-класса. Полистовой отбор помогает повысить гигиену и сократить отходы — гости касаются только полотенца, которое используют. Наши компактные диспенсеры не занимают много места для максимального удобства. Для оптимальных впечатлений не используйте в сочетании с Tork Xpress® настольными ', 4.6242, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/100888.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '100889', 'Tork Xpress® спрессованные мягкие полотенца для рук сложения Multifold-M, 225 л/пачка', 'refill', 'hand_towel', 'H2', 'Elevation',
    'white', 'medium', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Экономьте время на пополнении диспенсеров, используя сжимаемые на 50% полотенца для рук, которые удваивают емкость диспенсера. Гостям понравятся эти мягкие и хорошо впитывающие полотенца для рук премиум-класса. Полистовой отбор помогает повысить гигиену и сократить отходы — гости касаются только полотенца, которое используют. Наши компактные диспенсеры не занимают много места для максимального удобства. Для оптимальных впечатлений не используйте в сочетании с Tork Xpress® настольными диспенсерам', 3.486, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/100889.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '471146', 'Tork Xpress® листовые полотенца Multifold-Z, 190 л/пачка', 'refill', 'hand_towel', 'H2', 'Elevation',
    'white', 'medium', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork Xpress® листовые полотенца Multifold удовлетворяют базовые потребности в вытирании рук и гарантируют отличное соотношение цены и качества. Для использования в диспенсерах Tork Xpress® для листовых полотенец Multifold, устанавливаемых в туалетных комнатах со средней проходимостью. Для установки диспенсера не требуется много места, он обеспечивает вашим гостям комфорт и высокий уровень гигиены.', 2.7745, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/471146.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '471135', 'Tork Xpress® листовые полотенца для рук Multifold-Z, белые, система H2, 190 л/пачка', 'refill', 'hand_towel', 'H2', 'Elevation',
    'white', 'medium', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork Xpress® листовые полотенца Multifold мягкие высокого качества превосходно высушивают руки и обеспечивают комфорт вашим гостям. Для использования в диспенсерах Tork Xpress® для листовых полотенец Multifold, устанавливаемых в туалетных комнатах со средней проходимостью. Для установки диспенсера не требуется много места, он обеспечивает вашим гостям комфорт и высокий уровень гигиены.', 2.988, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/471135.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '553000', 'Tork диспенсер для листовых полотенец Singlefold сложения ZZ и С', 'dispenser', 'hand_towel', 'H3', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork диспенсер для листовых полотенец Singlefold сложения ZZ и С серии Elevation подходит для туалетных комнат с низкой и средней проходимостью. Он сокращает потребление полотенец и объем отходов благодаря надежной полистовой подаче. Диспенсеры серии Elevation имеют функциональный современный дизайн, который произведет приятное впечатление на ваших гостей.', 77.4735, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/553000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '553008', 'Tork диспенсер для листовых полотенец Singlefold сложения ZZ и С', 'dispenser', 'hand_towel', 'H3', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork диспенсер для листовых полотенец Singlefold сложения ZZ и С серии Elevation подходит для туалетных комнат с низкой и средней проходимостью. Он сокращает потребление полотенец и объем отходов благодаря надежной полистовой подаче. Диспенсеры серии Elevation имеют функциональный современный дизайн, который произведет приятное впечатление на ваших гостей.', 77.4735, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/553008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '553100', 'Tork мини-диспенсер для листовых полотенец Singlefold сложения ZZ и С', 'dispenser', 'hand_towel', 'H3', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork мини-диспенсер для листовых полотенец Singlefold сложения ZZ и С серии Elevation подходит для туалетных комнат с низкой и средней проходимостью. Он сокращает потребление полотенец и объем отходов благодаря надежной полистовой подаче. Диспенсеры серии Elevation имеют функциональный современный дизайн, который произведет приятное впечатление на ваших гостей.', 56.9372, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/553100.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '553108', 'Tork мини-диспенсер для листовых полотенец Singlefold сложения ZZ и С', 'dispenser', 'hand_towel', 'H3', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork мини-диспенсер для листовых полотенец Singlefold сложения ZZ и С серии Elevation подходит для туалетных комнат с низкой и средней проходимостью. Он сокращает потребление полотенец и объем отходов благодаря надежной полистовой подаче. Диспенсеры серии Elevation имеют функциональный современный дизайн, который произведет приятное впечатление на ваших гостей.', 62.1069, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/553108.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '100278', 'Tork листовые полотенца Singlefold-V, ультрамягкие, 200 л/пачка', 'refill', 'hand_towel', 'H3', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Подарите своим гостям комфорт благодаря ультрамягким листовым полотенцам Tork сложения Singlefold, категория качества Premium. QuickDry™  Они подходят для диспенсеров Tork для листовых полотенец Singlefold сложения ZZ и С, устанавливаемых в помещениях, к которым предъявляются высокие требования. Полистовой отбор позволяет контролировать расход полотенец и обеспечивает высокий уровень гигиены.', 5.1459, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/100278.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '290143', 'Tork мягкие листовые полотенца Singlefold-V, качество Advanced, 250 л/пачка', 'refill', 'hand_towel', 'H3', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork листовые полотенца Singlefold сложения ZZ удовлетворяют потребности в сушке рук и гарантируют качество в тех случаях, когда стоимость и характеристики одинаково важны. Для использования в диспенсерах Tork для листовых полотенец Singlefold сложения ZZ и С, прекрасном решении для туалетных комнат с высокими требованиями к гигиене. Полистовой отбор позволяет контролировать расход полотенец и обеспечивает высокий уровень гигиены.', 2.0059, 60,
    'C', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/290143.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '290163', 'Tork мягкие листовые полотенца для рук Singlefold-V, белые, система H3, 250 л/пачка', 'refill', 'hand_towel', 'H3', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork листовые полотенца Singlefold сложения ZZ удовлетворяют потребности в сушке рук и гарантируют качество в тех случаях, когда стоимость и характеристики одинаково важны. Для использования в диспенсерах Tork для листовых полотенец Singlefold сложения ZZ и С, прекрасном решении для туалетных комнат с высокими требованиями к гигиене. Полистовой отбор позволяет контролировать расход полотенец и обеспечивает высокий уровень гигиены.', 3.7942, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/290163.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '552500', 'Tork PeakServe® диспенсер листовых полотенец для рук с непрерывной подачей, белый, система H5', 'dispenser', 'hand_towel', 'H5', 'Elevation',
    'white', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork PeakServe®: новый стандарт бумажных полотенец для туалетных комнат с высокой проходимостью, где персоналу необходимо максимально сократить время уборки и поддерживать оптимальный поток посетителей. Совместим с Tork PeakServe® листовыми полотенцами с непрерывной подачей. Tork PeakServe — cистема с очень высокой емкостью (2100 полотенец). Дозирование полотенец происходит быстро и без задержек. Спрессованные пачки легко заправить в любое время, их удобно хранить и перевозить, благодаря чему пе', 182.2893, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/552500.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '552508', 'Tork PeakServe® диспенсер листовых полотенец для рук с непрерывной подачей, черный, система H5', 'dispenser', 'hand_towel', 'H5', 'Elevation',
    'black', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork PeakServe®: новый стандарт бумажных полотенец для туалетных комнат с высокой проходимостью, где персоналу необходимо максимально сократить время уборки и поддерживать оптимальный поток посетителей. Совместим с Tork PeakServe® листовыми полотенцами с непрерывной подачей. Tork PeakServe — cистема с очень высокой емкостью (2100 полотенец). Дозирование полотенец происходит быстро и без задержек. Спрессованные пачки легко заправить в любое время, их удобно хранить и перевозить, благодаря чему пе', 182.2893, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/552508.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '552550', 'Tork PeakServe® мини-диспенсер листовых полотенец для рук с непрерывной подачей, белый, система H5', 'dispenser', 'hand_towel', 'H5', 'Elevation',
    'white', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork PeakServe®: новый стандарт бумажных полотенец для туалетных комнат с высокой проходимостью, где персоналу необходимо максимально сократить время уборки и поддерживать оптимальный поток посетителей. Совместим с Tork PeakServe® листовыми полотенцами с непрерывной подачей. Tork PeakServe™ — cистема с очень высокой емкостью (1230 полотенец). Дозирование полотенец происходит быстро и без задержек. Спрессованные пачки легко заправить в любое время, их удобно хранить и перевозить, благодаря чему п', 146.1729, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/552550.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '552558', 'Tork PeakServe® мини-диспенсер для листовых полотенец с непрерывной подачей, система Н5, черный', 'dispenser', 'hand_towel', 'H5', 'Elevation',
    'black', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork PeakServe®: новый стандарт бумажных полотенец для туалетных комнат с высокой проходимостью, где персоналу необходимо максимально сократить время уборки и поддерживать оптимальный поток посетителей. Совместим с Tork PeakServe® листовыми полотенцами с непрерывной подачей. Tork PeakServe™ — cистема с очень высокой емкостью (1230 полотенец). Дозирование полотенец происходит быстро и без задержек. Спрессованные пачки легко заправить в любое время, их удобно хранить и перевозить, благодаря чему п', 146.1729, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/552558.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '100585', 'TorkTork PeakServe® листовые полотенца для рук, белые, непрерывная подача, система H5, 410 л/пачка', 'refill', 'hand_towel', 'H5', 'Elevation',
    'white', 'high', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork PeakServe®: новый стандарт бумажных полотенец для туалетных комнат с высокой проходимостью, где персоналу необходимо максимально оптимизировать время уборки и поддерживать надлежащий поток посетителей. Совместим с Tork PeakServe® листовыми полотенцами с непрерывной подачей. Диспенсер имеет высокую емкость — более 2100 полотенец. Подача полотенец происходит быстро и без задержек. Спрессованные пачки легко заправлять, хранить и перевозить, благодаря чему персонал может сосредоточиться на убор', 4.2211, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/100585.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '100589', 'Tork PeakServe® листовые полотенца для рук, белые, непрерывная подача, система H5, 270 л/пачка', 'refill', 'hand_towel', 'H5', 'Elevation',
    'white', 'high', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Подарите вашим гостям комфорт с полотенцами для рук Tork PeakServereg качества Advanced. Полотенца, украшенные тиснением в виде серых листочков, хорошо впитывают влагу и приятные на ощупь. Tork PeakServereg: новый стандарт бумажных полотенец для туалетных комнат с высокой проходимостью, где персоналу необходимо максимально сократить время уборки и поддерживать оптимальный поток посетителей. Совместимы с диспенсером Tork PeakServe — системой с очень высокой емкостью (более 2100 полотенец). Дозиро', 6.2605, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/100589.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '555000', 'Tork диспенсер для туалетной бумаги в мини-рулонах формата Jumbo, белый, система T2', 'dispenser', 'toilet_paper', 'T2', 'Elevation',
    'white', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    TRUE, 'Tork диспенсер для туалетной бумаги в мини-рулонах серии Elevation идеально подходит для туалетных комнат со средней и высокой проходимостью, где важны экономия времени и средств. Большая емкость диспенсера сокращает время обслуживания и гарантирует постоянное наличие бумаги. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших гостей.', 67.0157, 30,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/555000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '555008', 'Tork диспенсер для туалетной бумаги в мини-рулонах формата Jumbo, черный, система T2', 'dispenser', 'toilet_paper', 'T2', 'Elevation',
    'black', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    TRUE, 'Tork диспенсер для туалетной бумаги в мини-рулонах серии Elevation идеально подходит для туалетных комнат со средней и высокой проходимостью, где важны экономия времени и средств. Большая емкость диспенсера сокращает время обслуживания и гарантирует постоянное наличие бумаги. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших гостей.', 69.9325, 30,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/555008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '460006', 'Tork диспенсер для туалетной бумаги в мини-рулонах формата Jumbo, стальной, система T2', 'dispenser', 'toilet_paper', 'T2', 'Image Line',
    'stainless_steel', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    TRUE, 'Современный дизайн, гладкая поверхность и четкие линии — крючок для одежды безупречно впишется в интерьер вашей туалетной комнаты.
Он производит изысканное впечатление и подчеркивает стильный интерьер.
Изящная поверхность из нержавеющей стали с защитным покрытием, на котором не остаются отпечатки, всегда отлично выглядит и не пачкается.', 185.7515, 30,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/460006.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '120161', 'Tork туалетная бумага в мини-джамбо рулонах, 1 слой, 240 м/рулон', 'refill', 'toilet_paper', 'T2', 'Elevation',
    'white', 'medium', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork диспенсер для туалетной бумаги в мини-рулонах Universal — это экономия времени и средств, а также больше туалетной бумаги по сравнению со стандартными рулонами. Tork туалетная бумага в мини-рулонах Universal однослойная удовлетворяет базовые потребности, предлагая при этом хорошее соотношение цены и качества, подходит для помещений со средней и высокой посещаемостью.', 2.158, 60,
    'B', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/120161.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '120280', 'Tork туалетная бумага в мини-джамбо рулонах, 2 слоя, 170 м/рулон', 'refill', 'toilet_paper', 'T2', 'Elevation',
    'white', 'high', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    TRUE, 'Tork диспенсер для туалетной бумаги в мини-рулонах Advanced — это экономия времени и средств, а также больше туалетной бумаги по сравнению со стандартными рулонами. Двухслойная туалетная бумага Tork в мини-рулонах Advanced — оптимальное соотношение цены и качества, подходит для помещений со средней и высокой проходимостью.', 1.7526, 30,
    'C', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/120280.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '110253', 'Tork туалетная бумага в мини-рулонах мягкая, 2 слоя, 170 м/рулон', 'refill', 'toilet_paper', 'T2', 'Elevation',
    'white', 'high', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    TRUE, 'Tork диспенсер для туалетной бумаги в мини-рулонах — это экономия времени и средств, а также больше туалетной бумаги по сравнению со стандартными рулонами. Двухслойная туалетная бумага Tork в мини-рулонах превосходна на вид и на ощупь и подходит для помещений со средней и высокой проходимостью.', 2.0904, 30,
    'C', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/110253.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '556000', 'Tork диспенсер для листовой туалетной бумаги, белый, система T3', 'dispenser', 'toilet_paper', 'T3', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork диспенсер для листовой туалетной бумаги серии Elevation — это компактный диспенсер для туалетных комнат с низкой или средней посещаемостью. Благодаря гигиеничной полистовой подаче, она обеспечивает повышенную гигиену, что позволяет посетителям касаться только тех полотенец, которые они используют. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, лучшие в своем классе диспенсеры на каждый день.', 57.5064, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/556000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '556008', 'Tork диспенсер для листовой туалетной бумаги, черный, система T3', 'dispenser', 'toilet_paper', 'T3', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork диспенсер для листовой туалетной бумаги серии Elevation — это компактный диспенсер для туалетных комнат с низкой или средней посещаемостью. Благодаря гигиеничной полистовой подаче, она обеспечивает повышенную гигиену, что позволяет посетителям касаться только тех полотенец, которые они используют. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, лучшие в своем классе диспенсеры на каждый день.', 57.5064, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/556008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '114276', 'Tork ультрамягкая листовая туалетная бумага, белая, система T3, 252 л/пачка', 'refill', 'toilet_paper', 'T3', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Диспенсер для листовой туалетной бумаги Tork — гигиеничная полистовая подача позволяет снизить объем отходов и затраты на обслуживание. Ультрамягкая листовая туалетная бумага Tork Premium превосходна на вид и на ощупь. Эта система идеально подходит для помещений с низкой и средней проходимостью, особенно в медицинских учреждениях, а также в отелях и ресторанах', 2.2054, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/114276.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '114277', 'Tork мягкая листовая туалетная бумага, белая, система T3, 252 л/пачк', 'refill', 'toilet_paper', 'T3', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Диспенсер для листовой туалетной бумаги Tork — гигиеничная полистовая подача позволяет снизить объем отходов и затраты на обслуживание. Ультрамягкая листовая туалетная бумага Tork Premium превосходна на вид и на ощупь. Эта система идеально подходит для помещений с низкой и средней проходимостью, особенно в медицинских учреждениях, а также в отелях и ресторанах', 1.6363, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/114277.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '557000', 'Tork диспенсер для туалетной бумаги в рулонах, белый, система T4', 'dispenser', 'toilet_paper', 'T4', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork диспенсер для туалетной бумаги в стандартных рулонах серии Elevation подходит для туалетных комнат с низкой посещаемостью и снижает необходимость в техническом обслуживании, вмещая два рулона обычной т/б. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших гостей.', 60.7789, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/557000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '557008', 'Tork диспенсер для туалетной бумаги в рулонах, черный, система T4.', 'dispenser', 'toilet_paper', 'T4', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork диспенсер для туалетной бумаги в стандартных рулонах серии Elevation подходит для туалетных комнат с низкой посещаемостью и снижает необходимость в техническом обслуживании, вмещая два рулона обычной т/б. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших гостей.', 55.5144, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/557008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '680000', 'Tork SmartOne® диспенсер для туалетной бумаги в рулонах, белый, система T8', 'dispenser', 'toilet_paper', 'T8', 'Elevation',
    'white', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    TRUE, 'Tork SmartOne® диспенсер для туалетной бумаги в рулонах серии Elevation — современная и эффективная система, которая подходит для условий эксплуатации в туалетных комнатах с высокой проходимостью. Полистовая подача помогает сократить расход бумаги почти на 40% по сравнению с традиционными диспенсерами для туалетной бумаги в больших рулонах — одного рулона хватит надолго. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших гостей.', 59.1189, 20,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/680000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '680008', 'Tork SmartOne® диспенсер для туалетной бумаги в рулонах', 'dispenser', 'toilet_paper', 'T8', 'Elevation',
    'black', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    TRUE, 'Tork SmartOne® диспенсер для туалетной бумаги в рулонах серии Elevation — современная и эффективная система, которая подходит для условий эксплуатации в туалетных комнатах с высокой проходимостью. Полистовая подача помогает сократить расход бумаги почти на 40% по сравнению с традиционными диспенсерами для туалетной бумаги в больших рулонах — одного рулона хватит надолго. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших гостей.', 64.5731, 20,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/680008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '681000', 'Tork SmartOne® диспенсер для туалетной бумаги в мини-рулонах, белый, система T9', 'dispenser', 'toilet_paper', 'T9', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork SmartOne® диспенсер для туалетной бумаги в мини-рулонах серии Elevation — современная и эффективная система, которая подходит для условий эксплуатации в туалетных комнатах с низкой и средней проходимостью. Полистовая подача помогает сократить расход бумаги почти на 40% по сравнению с традиционными диспенсерами для туалетной бумаги в больших рулонах — одного рулона хватит надолго. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших го', 56.0835, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/681000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '681008', 'Tork SmartOne® диспенсер для туалетной бумаги в мини-рулонах, черный, система T9', 'dispenser', 'toilet_paper', 'T9', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork SmartOne® диспенсер для туалетной бумаги в мини-рулонах серии Elevation — современная и эффективная система, которая подходит для условий эксплуатации в туалетных комнатах с низкой и средней проходимостью. Полистовая подача помогает сократить расход бумаги почти на 40% по сравнению с традиционными диспенсерами для туалетной бумаги в больших рулонах — одного рулона хватит надолго. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, для лучших впечатлений ваших го', 54.4947, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/681008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '682000', 'Tork SmartOne® двойной диспенсер для туалетной бумаги в мини-рулонах, белый, система T9', 'dispenser', 'toilet_paper', 'T9', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Двойной диспенсер Tork SmartOne® для туалетной бумаги в мини-рулонах серии Elevation — современная и эффективная система, которая подходит для условий эксплуатации в туалетных комнатах с высокой проходимостью. Полистовая подача помогает сократить расход бумаги до 40 % по сравнению традиционными диспенсерами для туалетной бумаги в больших рулонах. Одновременное наличие двух рулонов гарантирует, что бумаги хватит надолго. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функционально', 82.5246, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/682000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '682008', 'Tork SmartOne® двойной диспенсер для туалетной бумаги в мини-рулонах, черный, система T9', 'dispenser', 'toilet_paper', 'T9', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Двойной диспенсер Tork SmartOne® для туалетной бумаги в мини-рулонах серии Elevation — современная и эффективная система, которая подходит для условий эксплуатации в туалетных комнатах с высокой проходимостью. Полистовая подача помогает сократить расход бумаги до 40 % по сравнению традиционными диспенсерами для туалетной бумаги в больших рулонах. Одновременное наличие двух рулонов гарантирует, что бумаги хватит надолго. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функционально', 82.5246, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/682008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '472242', 'Tork SmartOne® туалетная бумага в рулонах, белая, система T8', 'refill', 'toilet_paper', 'T8', 'Elevation',
    'white', 'high', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    TRUE, 'Tork SmartOne® туалетная бумага в рулонах — уникальная система, обеспечивающая гигиеничный полистовой отбор и до 40% экономии по сравнению с традиционными большими рулонами, что означает больший срок использования рулона. Рулоны высокой емкости Tork SmartOne® подходят для туалетных комнат с высокой посещаемостью, к которым предъявляются высокие требования.', 7.3988, 20,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/472242.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '472193', 'Tork SmartOne® туалетная бумага в мини-рулонах, белая, система T9', 'refill', 'toilet_paper', 'T9', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork SmartOne® туалетная бумага в мини-рулонах — уникальная система, обеспечивающая гигиеничный полистовой отбор и до 40% экономии по сравнению с традиционными большими рулонами. Мини-рулоны Tork SmartOne высокой емкости подходят для туалетных комнат с низкой и средней проходимостью, к которым предъявляются высокие требования.', 2.5972, 60,
    'C', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/472193.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '564500', 'Tork диспенсер для мыла и дезинфицирующих средств белый, 1Л', 'dispenser', 'soap', 'S4', 'Elevation',
    'white', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    TRUE, 'Tork диспенсер для мыла и дезинфицирующих средств подходит для любых помещений. Совместим с несколькими видами мыла, дезинфицирующих средств и лосьонов Tork в герметичных картриджах. Отвечает разным потребностям вашего бизнеса. Обеспечивает гигиену рук для всех благодаря надежному отбору средств, порциям разного размера и конструкции, сертифицированной как простая в использовании. Улучшите впечатления гостей, предлагая им наши самые универсальные диспенсеры для мыла и дезинфицирующих средств с ф', 43.0409, 10,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/564500.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '564508', 'Tork диспенсер для мыла и дезинфицирующих средств черный, 1Л', 'dispenser', 'soap', 'S4', 'Elevation',
    'black', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    TRUE, 'Tork диспенсер для мыла и дезинфицирующих средств подходит для любых помещений. Совместим с несколькими видами мыла, дезинфицирующих средств и лосьонов Tork в герметичных картриджах. Отвечает разным потребностям вашего бизнеса. Обеспечивает гигиену рук для всех благодаря надежному отбору средств, порциям разного размера и конструкции, сертифицированной как простая в использовании. Улучшите впечатления гостей, предлагая им наши самые универсальные диспенсеры для мыла и дезинфицирующих средств с ф', 43.0409, 10,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/564508.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '460010', 'Tork диспенсер для мыла-пены, металический, S4, 1Л', 'dispenser', 'soap', 'S4', 'Image Line',
    'stainless_steel', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    TRUE, 'Современный дизайн серии Image Design с четкими, плавными линиями безупречно впишется в любой интерьер. Создайте отличное впечатление, которое повысит высококачественный имидж вашего заведения. Стильная нержавеющая сталь с покрытием против отпечатков пальцев отлично выглядит и остается чистой. Может использоваться с широким спектром мыла, дезинфицирующих средств и лосьонов Tork в герметичных картриджах. Просты в использовании и сертифицированы для соблюдения гигиены рук для всех пользователей.', 114.5385, 10,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/460010.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '564100', 'Tork диспенсер для мыла и дезинфицирующих средств с локтевым приводом, белый, 1Л', 'dispenser', 'soap', 'S4', 'Elevation',
    'white', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Tork диспенсер для мыла и дезинфицирующих средств с локтевым приводом предназначен для помещений, в которых предъявляются более высокие требования к гигиене, и подходит для использования с большим ассортиментом мыла, дезинфицирующих средств и лосьонов Tork в герметичных флаконах в зависимости от потребностей вашей компании. Обеспечивает гигиену рук для всех благодаря надежному отбору средств, порциям разного размера и конструкции, сертифицированной как простая в использовании. Улучшите впечатлен', 65.9011, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/564100.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '564108', 'Tork диспенсер для мыла и дезинфицирующих средств с локтевым приводом, черный, 1Л', 'dispenser', 'soap', 'S4', 'Elevation',
    'black', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Tork диспенсер для мыла и дезинфицирующих средств с локтевым приводом предназначен для помещений, в которых предъявляются более высокие требования к гигиене, и подходит для использования с большим ассортиментом мыла, дезинфицирующих средств и лосьонов Tork в герметичных флаконах в зависимости от потребностей вашей компании. Обеспечивает гигиену рук для всех благодаря надежному отбору средств, порциям разного размера и конструкции, сертифицированной как простая в использовании. Улучшите впечатлен', 65.9011, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/564108.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '565200', 'Tork диспенсер мини для мыла и дезинфицирующих средств белый, 0,5Л', 'dispenser', 'soap', 'S5', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Tork мини-диспенсер для мыла и дезинфицирующих средств подходит для любых помещений. Совместим с несколькими видами мыла, дезинфицирующих средств и лосьонов Tork в герметичных картриджах. Отвечает разным потребностям вашего бизнеса. Обеспечивает гигиену рук для всех благодаря надежному отбору средств, порциям разного размера и конструкции, сертифицированной как простая в использовании. Улучшите впечатления гостей, предлагая им наши самые универсальные диспенсеры для мыла и дезинфицирующих средст', 40.7406, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/565200.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '565208', 'Tork диспенсер мини для мыла и дезинфицирующих средств черный, 0,5Л', 'dispenser', 'soap', 'S5', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Tork мини-диспенсер для мыла и дезинфицирующих средств подходит для любых помещений. Совместим с несколькими видами мыла, дезинфицирующих средств и лосьонов Tork в герметичных картриджах. Отвечает разным потребностям вашего бизнеса. Обеспечивает гигиену рук для всех благодаря надежному отбору средств, порциям разного размера и конструкции, сертифицированной как простая в использовании. Улучшите впечатления гостей, предлагая им наши самые универсальные диспенсеры для мыла и дезинфицирующих средст', 40.7406, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/565208.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '420701', 'Tork жидкое мыло ультрамягкое, S1, 1Л', 'refill', 'soap', 'S1', 'Elevation',
    'white', 'medium', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Обеспечьте дополнительный уход за сухой и чувствительной кожей с помощью Tork жидкого мыла-крема деликатного для рук. Благодаря восстанавливающим кожу ингредиентам и отсутствию отдушек это мыло ухаживает за кожей любого типа. Не вызывает аллергических реакций, сертифицировано Фондом европейского центра по исследованиям аллергии (ECARF). Для использования в диспенсерах для жидкого мыла и мыла-спрея Tork, которые сертифицированы как удобные в использовании и обеспечивают отличную гигиену рук для в', 4.7756, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/420701.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '420501', 'Tork жидкое мыло мягкое, S1, 1Л', 'refill', 'soap', 'S1', 'Elevation',
    'none', 'medium', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Обеспечивает уход за нормальной и сухой кожей, для ежедневного мытья рук. Tork жидкое мыло-гель с легким ароматом имеет тонкий аромат, содержит увлажняющие и восстанавливающие ингредиенты для бережного мытья рук. Подходит для сертифицированных диспенсеров для жидкого мыла-крема и мыла-спрея Tork, которые удобны в использовании и обеспечивают высокий уровень гигиены рук.', 5.0511, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/420501.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '420601', 'Tork жидкое мыло-гель для тела и волос, S1, 1Л', 'refill', 'soap', 'S1', 'Elevation',
    'none', 'medium', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Tork крем-мыло для душа жемчужного цвета с  увлажняющей  формулой и освежающим универсальным ароматом. Подходит для отелей, школ и спортивных учреждений. Бережно очищает и смягчает кожу. Подходит для сертифицированных диспенсеров для жидкого мыла-крема и мыла-спрея Tork, которые удобны в использовании и обеспечивают высокий уровень гигиены рук.', 4.6608, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/420601.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '420502', 'Tork жидкое мыло мягкое, мини, S2, 0,5Л', 'refill', 'soap', 'S2', 'Elevation',
    'none', 'medium', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Обеспечивает уход за нормальной и сухой кожей, для ежедневного мытья рук. Tork жидкое мыло-гель с легким ароматом, мини имеет тонкий аромат, содержит увлажняющие и восстанавливающие ингредиенты для бережного мытья рук. Для использования в Tork мини-диспенсерах для жидкого мыла. Они просты в обслуживании и обеспечивают высокий уровень гигиены рук.', 4.0638, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], TRUE, 'http://cdn/images/420502.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '420602', 'Tork  жидкое мыло-гель для тела и волос, мини, S2, 0,5Л', 'refill', 'soap', 'S2', 'Elevation',
    'none', 'medium', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Tork крем-мыло для душа жемчужного цвета с  увлажняющей  формулой и освежающим универсальным ароматом. Подходит для отелей, школ и спортивных учреждений. Бережно очищает и смягчает кожу. Подходит для сертифицированных диспенсеров для жидкого мыла-крема и мыла-спрея Tork, которые удобны в использовании и обеспечивают высокий уровень гигиены рук.', 3.8572, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], TRUE, 'http://cdn/images/420602.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '400505', 'Tork жидкое мыло-гель с легким ароматом, разливное, 5Л', 'refill', 'soap', 'NA', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Предложите посетителям универсальное мыло со свежим ароматом, которое идеально подходит для нормальной и сухой кожи. Tork жидкое мыло-гель с легким ароматом содержит увлажняющие и восстанавливающие ингредиенты, которые бережно ухаживают за кожей во время мытья рук.', 25.5079, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], TRUE, 'http://cdn/images/400505.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '520701', 'Tork мыло-пена деликатное, S4, 1Л', 'refill', 'soap', 'S4', 'Elevation',
    'none', 'high', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    TRUE, 'Деликатное мыло-пена для рук Tork обеспечивает бережный уход за сухой и чувствительной кожей. Благодаря восстанавливающим кожу ингредиентам и отсутствию отдушек и красителей это мыло ухаживает за кожей любого типа. Не вызывает аллергических реакций, сертифицировано Фондом европейского центра по исследованиям аллергии (ECARF). Для использования в Tork диспенсерах для мыла и дезинфицирующих средств. Диспенсеры просты в обслуживании и обеспечивают высокий уровень гигиены рук.', 8.9083, 10,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/520701.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '520501', 'Tork мыло-пена с легким ароматом, S4, 1Л', 'refill', 'soap', 'S4', 'Elevation',
    'none', 'high', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    TRUE, 'Обеспечивает уход за нормальной и сухой кожей, для ежедневного мытья рук. Tork мыло-пена с легким ароматом имеет тонкий аромат, содержит увлажняющие и восстанавливающие ингредиенты и образует мягкую кремовую пену для бережного мытья рук. Для использования в Tork диспенсерах для мыла и дезинфицирующих средств. Диспенсеры Tork просты в обслуживании и обеспечивают высокий уровень гигиены рук.', 8.3572, 10,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/520501.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '524901', 'Tork мыло-пена люкс для рук, S4, 1Л', 'refill', 'soap', 'S4', 'Elevation',
    'none', 'high', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Подарите своим гостям роскошный уход за кожей с Tork Люксовым мылом-пеной. Формула с роскошным ароматом, обогащенная натуральным экстрактом магнолии и увлажняющими компонентами, обеспечивает приятное и нежное мытье рук. Для использования в Tork диспенсерах для мыла и дезинфицирующих средств. Доказано, что диспенсеры Tork просты в обслуживании и обеспечивают высокий уровень гигиены рук для всех пользователей.', 9.8037, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/524901.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '525502', 'Tork жидкое мыло-пена с легким ароматом, мини, S5, 525МЛ', 'refill', 'soap', 'S5', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Обеспечивает уход за нормальной и сухой кожей, для ежедневного мытья рук. Tork мыло-пена мягкое имеет тонкий аромат, содержит увлажняющие и восстанавливающие ингредиенты и образует мягкую кремовую пену для бережного мытья рук. Для использования в Tork мини-диспенсерах для мыла и дезинфицирующих средств. Диспенсеры Tork просты в обслуживании и обеспечивают высокий уровень гигиены рук.', 6.222, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/525502.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '525902', 'Tork люксовое мыло-пена для рук, мини, S5, 525МЛ', 'refill', 'soap', 'S5', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Подарите своим гостям роскошный уход за кожей с Tork Люксовым мылом-пеной. Формула с роскошным ароматом, обогащенная натуральным экстрактом магнолии и увлажняющими компонентами, обеспечивает приятное и нежное мытье рук. Для использования в Tork диспенсерах для мыла и дезинфицирующих средств. Доказано, что диспенсеры Tork просты в обслуживании и обеспечивают высокий уровень гигиены рук для всех пользователей.', 8.2195, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/525902.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '424701', 'Tork жидкое мыло деликатное, S4, 1Л', 'refill', 'soap', 'S4', 'Elevation',
    'none', 'high', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Деликатное мыло для рук Tork обеспечивает бережный уход за сухой и чувствительной кожей. Благодаря восстанавливающим кожу ингредиентам и отсутствию отдушек и красителей это мыло ухаживает за кожей любого типа. Не вызывает аллергических реакций, сертифицировано Фондом европейского центра по исследованиям аллергии (ECARF). Для использования в Tork диспенсерах для мыла и дезинфицирующих средств. Диспенсеры просты в обслуживании и обеспечивают высокий уровень гигиены рук.', 6.3368, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/424701.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '424501', 'Tork жидкое мыло с легким ароматом, S4, 1Л', 'refill', 'soap', 'S4', 'Elevation',
    'none', 'high', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Обеспечивает уход за нормальной и сухой кожей, для ежедневного мытья рук. Tork мыло-пена с легким ароматом имеет тонкий аромат, содержит увлажняющие и восстанавливающие ингредиенты и образует мягкую кремовую пену для бережного мытья рук. Для использования в Tork диспенсерах для мыла и дезинфицирующих средств. Диспенсеры Tork просты в обслуживании и обеспечивают высокий уровень гигиены рук.', 6.7042, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/424501.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '424911', 'Tork жидкое мыло люкс, S4, 1Л', 'refill', 'soap', 'S4', 'Elevation',
    'none', 'high', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Подарите своим гостям роскошный уход за кожей с Tork Люксовым мылом. Формула с роскошным ароматом, обогащенная натуральным экстрактом магнолии и увлажняющими компонентами, обеспечивает приятное и нежное мытье рук. Для использования в Tork диспенсерах для мыла и дезинфицирующих средств. Доказано, что диспенсеры Tork просты в обслуживании и обеспечивают высокий уровень гигиены рук для всех пользователей.', 7.944, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/424911.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '424601', 'Tork крем-гель для душа, S4, 1Л', 'refill', 'soap', 'S4', 'Elevation',
    'none', 'high', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Tork крем-гель для душа жемчужного цвета с  увлажняющей  формулой и освежающим универсальным ароматом. Подходит для отелей, школ и спортивных учреждений. Бережно очищает и смягчает кожу. Подходит для сертифицированных диспенсеров для жидкого мыла-крема и мыла-спрея Tork, которые удобны в использовании и обеспечивают высокий уровень гигиены рук.', 5.7169, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/424601.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '424661', 'Tork люксовое крем-мыло для тела и волос, S4, 1Л', 'refill', 'soap', 'S4', 'Elevation',
    'none', 'high', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Tork люксовое крем-мыло для тела и волос, мини — идеальное средство 3-в-1 для отелей, спа-центров и спортивных объектов. В состав входят аргановое масло и кондиционер, и средство выполняет три функции: освежающего шампуня, кондиционера и увлажняющего жидкого мыла-шампуня. Оно не только бережно очищает, но и увлажняет волосы, делая их мягкими и послушными. Подходит для диспенсеров Tork для мыла и дезинфицирующих средств, которые являются простыми в использовании и отлично поддерживают гигиену рук', 11.319, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/424661.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '424011', 'Tork нейтрализующее запахи жидкое мыло для рук, система S4, 1Л', 'refill', 'soap', 'S4', 'Elevation',
    'none', 'high', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Мыло для зоны кухни, которое помогает удалять с рук жир и неприятные запахи. Мыло без лишних ингредиентов: не содержит красителей и отдушек. Бережно воздействует на кожу и подходит для частого применения — проверено дерматологами. Подходит для использования в Tork диспенсерах для мыла и дезинфицирующих средств. Доказано, что диспенсеры Tork просты в обслуживании и обеспечивают высокий уровень гигиены рук для всех пользователей.', 7.7373, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/424011.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '424401', 'Tork жидкое мыло-очиститель для рук от жировых и технических загрязнений, S4, 1Л', 'refill', 'soap', 'S4', 'Elevation',
    'none', 'high', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Для удаления грязи, масла и жира. В состав Tork жидкого мыла-очистителя для рук от жировых и технических загрязнений входят расщепляющие жир высокоэффективные ингредиенты, которые бережно ухаживают за кожей. Без ароматизаторов и красителей — деликатно воздействует на кожу. Подходит для сертифицированных диспенсеров для жидкого мыла-крема и мыла-спрея Tork, которые удобны в использовании и обеспечивают высокий уровень гигиены рук.', 5.4414, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/424401.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '425702', 'Tork деликатное жидкое мыло-гель для рук, мини, S5, 525МЛ', 'refill', 'soap', 'S5', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Обеспечьте дополнительный уход за сухой и чувствительной кожей с помощью Tork жидкого мыла-крема деликатного. Благодаря восстанавливающим кожу ингредиентам и отсутствию отдушек это мыло ухаживает за кожей любого типа. Не вызывает аллергических реакций, сертифицировано Фондом европейского центра по исследованиям аллергии (ECARF). Для использования в Tork мини-диспенсерах для мыла и дезинфицирующих средств. Диспенсеры Tork просты в обслуживании и обеспечивают высокий уровень гигиены рук.', 5.7858, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/425702.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '425502', 'Tork жидкое мыло-гель для рук с легким ароматом, мини, S5, 525МЛ', 'refill', 'soap', 'S5', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Обеспечивает уход за нормальной и сухой кожей, для ежедневного мытья рук. Tork мыло-пена мягкое имеет тонкий аромат, содержит увлажняющие и восстанавливающие ингредиенты и образует мягкую кремовую пену для бережного мытья рук. Для использования в Tork мини-диспенсерах для мыла и дезинфицирующих средств. Диспенсеры Tork просты в обслуживании и обеспечивают высокий уровень гигиены рук.', 4.9822, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/425502.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '425662', 'Tork люксовое крем-мыло для тела и волос, мини, S5, 525МЛ', 'refill', 'soap', 'S5', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Tork люксовое крем-мыло для тела и волос, мини — идеальное средство 3-в-1 для отелей, спа-центров и спортивных объектов. В состав входят аргановое масло и кондиционер, и средство выполняет три функции: освежающего шампуня, кондиционера и увлажняющего жидкого мыла-шампуня. Оно не только бережно очищает, но и увлажняет волосы, делая их мягкими и послушными. Подходит для диспенсеров Tork для мыла и дезинфицирующих средств, которые являются простыми в использовании и отлично поддерживают гигиену рук', 6.6582, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/425662.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '425202', 'Tork деликатный увлажняющий лосьон для рук, мини, S5, 525МЛ', 'refill', 'soap', 'S5', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 3, "portions_per_unit": 1000}'::jsonb,
    FALSE, 'Tork деликатный увлажняющий лосьон для рук — идеальное средство для сухой кожи. Обеспечивает питание и мягкость кожи. Лосьон без отдушки с увлажняющими компонентами помогает поддерживать естественный баланс влажности кожи и помогает коже удерживать влагу. Для использования в Tork мини-диспенсерах для мыла и дезинфицирующих средств. Диспенсеры Tork просты в обслуживании и обеспечивают высокий уровень гигиены рук.', 11.1124, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/425202.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '270023', 'Tork диспенсер салфеток для лица, белый, система F1', 'dispenser', 'napkin', 'F1', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Современный дизайн с гладкой поверхностью и четкими линиями идеально впишется в интерьер туалетных комнат. Производит изысканное впечатление и подчеркивает высокий уровень вашего бизнеса.', 28.4093, 50,
    'A', ARRAY['Medical']::TEXT[], FALSE, 'http://cdn/images/270023.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '460013', 'Tork диспенсер салфеток для лица, нержавеющая сталь, система F1', 'dispenser', 'napkin', 'F1', 'Image Line',
    'stainless_steel', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Современный дизайн, гладкая поверхность и четкие линии — крючок для одежды безупречно впишется в интерьер вашей туалетной комнаты.
Он производит изысканное впечатление и подчеркивает стильный интерьер.
Изящная поверхность из нержавеющей стали с защитным покрытием, на котором не остаются отпечатки, всегда отлично выглядит и не пачкается.', 77.023, 50,
    'A', ARRAY['Medical']::TEXT[], FALSE, 'http://cdn/images/460013.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '140280', 'Tork салфетки косметические для лица ультрамягкие, в прямоугольной упаковке, 100 л/упаковка', 'refill', 'napkin', 'F1', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Ультрамягкие салфетки для лица Tork упакованы в элегантный плоский короб для комфорта ваших гостей. Короб с салфетками для лица Tork совместим с диспенсером Tork и может быть установлен в любом месте, где это необходимо.', 1.8971, 50,
    'A', ARRAY['Medical']::TEXT[], TRUE, 'http://cdn/images/140280.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '140278', 'Tork салфетки косметические для лица ультрамягкие, в кубе, 100 л/упаковка', 'refill', 'napkin', 'F1', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Ультрамягкие салфетки для лица Tork выпускаются в современной упаковке в форме куба, который можно разместить в любом удобном месте, проявив максимальную заботу о комфорте гостей, благодаря премиальному виду и эффективности использования.', 1.9208, 50,
    'A', ARRAY['Medical']::TEXT[], TRUE, 'http://cdn/images/140278.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '562500', 'Tork держатель для твердого освежителя воздуха, белый, система A2, 4 шт/упаковка (цена за упаковку)', 'dispenser', 'air_freshener', 'A2', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork держатель для твердого освежителя воздуха — компактная и удобная для установки система, предназначенная для размещения и использования твердого освежителя воздуха Tork в любом месте туалетной комнаты.', 10.2681, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/562500.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '236015', 'Tork твердый освежитель воздуха, цветочный аромат', 'refill', 'hand_towel', 'A2', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Добавьте приятный аромат в туалетную комнату с Tork освежителем воздуха в пластинах. Пропитанная резиновая пластина источает свежий цветочный аромат, ее легко разместить в любом месте.', 50.5345, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], TRUE, 'http://cdn/images/236015.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '236014', 'Tork твердый освежитель воздуха, цитрусовый аромат', 'refill', 'air_freshener', 'A2', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Добавьте приятный аромат в туалетную комнату с Tork освежителем воздуха в пластинах. Пропитанная резиновая пластина источает свежий цветочный аромат, ее легко разместить в любом месте.', 50.5345, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], TRUE, 'http://cdn/images/236014.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '344080', 'Tork компактный диспенсер для покрытий на сиденье унитаза, белый, система V1', 'dispenser', 'seat_cover', 'V1', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork диспенсер для бумажных покрытий на унитаз обеспечивает гигиеничный полистовой отбор сидений.', 45.2937, 50,
    'A', ARRAY['Industrial', 'Medical']::TEXT[], FALSE, 'http://cdn/images/344080.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '344088', 'Tork компактный диспенсер для покрытий на сиденье унитаза, черный, система V1', 'dispenser', 'seat_cover', 'V1', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork диспенсер для бумажных покрытий на унитаз обеспечивает гигиеничный полистовой отбор сидений.', 49.3962, 50,
    'A', ARRAY['Industrial']::TEXT[], FALSE, 'http://cdn/images/344088.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '750160', 'Tork индивидуальные бумажные покрытия на унитаз, 250 шт/пачка', 'refill', 'seat_cover', 'V1', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Сделайте помещение комфортнее для ваших гостей с индивидуальными бумажными покрытиями на унитаз Tork и обеспечьте дополнительную гигиену в туалетных комнатах.', 10.6476, 50,
    'A', ARRAY['Industrial', 'Medical']::TEXT[], TRUE, 'http://cdn/images/750160.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '563000', 'Tork корзина для мусора 50л (крышка в комплект не входит)', 'dispenser', 'bin', 'B1', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork корзина для мусора на 50 л серии Elevation подходит для любых туалетных комнат. Может навешиваться на стену или размещаться на полу в зависимости от площади помещения или ваших потребностей. Диспенсеры серии Elevation имеют функциональный современный дизайн, который произведет приятное впечатление на ваших гостей.', 211.1255, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/563000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '563008', 'Tork корзина для мусора 50л (крышка в комплект не входит)', 'dispenser', 'bin', 'B1', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Tork корзина для мусора на 50 л серии Elevation подходит для любых туалетных комнат. Может навешиваться на стену или размещаться на полу в зависимости от площади помещения или ваших потребностей. Диспенсеры серии Elevation имеют функциональный современный дизайн, который произведет приятное впечатление на ваших гостей.', 211.1255, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/563008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '460011', 'Tork корзина для мусора 50л , металическая, без крышки', 'dispenser', 'bin', 'B1', 'Image Line',
    'stainless_steel', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Современный дизайн, гладкая поверхность и четкие линии — крючок для одежды безупречно впишется в интерьер вашей туалетной комнаты.
Он производит изысканное впечатление и подчеркивает стильный интерьер.
Изящная поверхность из нержавеющей стали с защитным покрытием, на котором не остаются отпечатки, всегда отлично выглядит и не пачкается.', 461.5924, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/460011.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '226100', 'Tork корзина для мусора 20л, без крышки', 'dispenser', 'bin', 'B2', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, '20-литровая корзина для мусора Tork подходит для любых туалетных комнат, легко монтируется на стене в любом месте.', 81.6709, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/226100.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '564000', 'Tork корзина для мусора 5л', 'dispenser', 'bin', 'B3', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, '5-литровая корзина для мусора Tork серии Elevation — компактное решение для небольших туалетных кабинок, офисных кухонь и любых мест с ограниченной площадью.  Полностью скрытый мешок для мусора придает корзине опрятный вид. Крышка с доводчиком делает использование корзины еще более комфортным. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, лучшие в своем классе диспенсеры на каждый день.', 64.2886, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/564000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '564008', 'Tork корзина для мусора 5л', 'dispenser', 'bin', 'B3', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, '5-литровая корзина для мусора Tork серии Elevation — компактное решение для небольших туалетных кабинок, офисных кухонь и любых мест с ограниченной площадью.  Полностью скрытый мешок для мусора придает корзине опрятный вид. Крышка с доводчиком делает использование корзины еще более комфортным. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, лучшие в своем классе диспенсеры на каждый день.', 64.2886, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/564008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '566000', 'Tork держатель для гигиенических пакетов', 'dispenser', 'accessory', 'B5', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Держатель для гигиенических пакетов Tork серии Elevation — аккуратное и удобное решение для любой туалетной комнаты, обеспечивающее гигиеничную утилизацию отходов. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, лучшие в своем классе диспенсеры на каждый день.', 14.2047, 50,
    'A', ARRAY['Medical']::TEXT[], FALSE, 'http://cdn/images/566000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '566008', 'Tork держатель для гигиенических пакетов', 'dispenser', 'accessory', 'B5', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Держатель для гигиенических пакетов Tork серии Elevation — аккуратное и удобное решение для любой туалетной комнаты, обеспечивающее гигиеничную утилизацию отходов. Диспенсеры Tork Elevation — это уникальное сочетание дизайна и функциональности, лучшие в своем классе диспенсеры на каждый день.', 14.2047, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/566008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '460014', 'Tork крючок для одежды/сумок (продажа упаковками, в коробе 12 упак.х10шт)', 'dispenser', 'accessory', 'NA', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Современный дизайн, гладкая поверхность и четкие линии — крючок для одежды безупречно впишется в интерьер вашей туалетной комнаты.
Он производит изысканное впечатление и подчеркивает стильный интерьер.
Изящная поверхность из нержавеющей стали с защитным покрытием, на котором не остаются отпечатки, всегда отлично выглядит и не пачкается.', 95.5673, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/460014.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '558000', 'Tork Elevation мини-диспенсер для полотенец с ЦВ', 'dispenser', 'hand_towel', 'M1', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Диспенсер Tork Мини с центральной вытяжкой — компактное и универсальное решение для тех случаев, когда необходима и протирка рук, и уборка поверхностей. Обеспечивает быструю протирку поверхностей благодаря функции неограниченной подачи, которая позволяет отбирать необходимое для выполнения работы количество листов. Диспенсеры Elevation имеют функциональный и современный дизайн.', 70.5491, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/558000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '558008', 'Tork Elevation мини-диспенсер для полотенец с ЦВ', 'dispenser', 'hand_towel', 'M1', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Диспенсер Tork Мини с центральной вытяжкой — компактное и универсальное решение для тех случаев, когда необходима и протирка рук, и уборка поверхностей. Обеспечивает быструю протирку поверхностей благодаря функции неограниченной подачи, которая позволяет отбирать необходимое для выполнения работы количество листов. Диспенсеры Elevation имеют функциональный и современный дизайн.', 73.9164, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Office']::TEXT[], FALSE, 'http://cdn/images/558008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '559000', 'Tork Elevation диспенсер для полотенец с ЦВ', 'dispenser', 'hand_towel', 'M2', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Диспенсер Tork c центральной вытяжкой серии Elevation — универсальное решение для тех случаев, когда необходима и протирка рук, и уборка поверхностей. Обеспечивает быструю протирку поверхностей благодаря функции неограниченной подачи, которая позволяет отбирать необходимое для выполнения работы количество листов. Диспенсеры Elevation имеют функциональный и современный дизайн.', 91.9865, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/559000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '559008', 'Tork Elevation диспенсер для полотенец с ЦВ', 'dispenser', 'hand_towel', 'M2', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Диспенсер Tork c центральной вытяжкой серии Elevation — универсальное решение для тех случаев, когда необходима и протирка рук, и уборка поверхностей. Обеспечивает быструю протирку поверхностей благодаря функции неограниченной подачи, которая позволяет отбирать необходимое для выполнения работы количество листов. Диспенсеры Elevation имеют функциональный и современный дизайн.', 96.3499, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/559008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '473191', 'Tork Reflex™ диспенсер с центральной вытяжкой черный, M4', 'dispenser', 'hand_towel', 'M4', 'Elevation',
    'black', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Диспенсер с центральной вытяжкой Tork Reflex™ черный, M4, идеально подходит для загруженных рабочих мест, где требуется очень надежное оборудование, которое прекрасно впишется в существующий рабочий поток. Наш прочный диспенсер с центральной вытяжкой Tork Reflex™, оснащенный вращающейся насадкой для удобного доступа к протирочной бумаге, подойдет для любого рабочего места. Очищая руки и поверхности, вы поддерживаете гигиену. При полистовом отборе пользователи касаются только листа, который берут', 25.0, 100,
    'C', ARRAY['HoReCa', 'Industrial', 'Office']::TEXT[], FALSE, 'http://cdn/images/473191.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '473180', 'Tork Reflex™ диспенсер с центральной подачей, система M4, сочетание белого и бирюзового', 'dispenser', 'hand_towel', 'M4', 'Elevation',
    'none', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Диспенсер Tork Reflex™ с центральной вытяжкой — идеальное решение для рабочих зон, где требуется как протирка рук, так и уборка поверхностей, разработанное с учетом вашего рабочего процесса. Вы касаетесь только той салфетки, которую собираетесь использовать, благодаря полистовому отбору бумаги с любого угла с вращающегося клапана. Диспенсер прост в использовании, гигиеничный и надежный. Полистовой отбор снижает расход материала до 37% по сравнению с системой Tork® с центральной вытяжкой.', 79.6552, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Office']::TEXT[], FALSE, 'http://cdn/images/473180.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '473190', 'Tork ReflexТМ диспенсер для полотенец с ЦВ', 'dispenser', 'hand_towel', 'M4', 'Elevation',
    'white', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Диспенсер Tork Reflex™ с центральной вытяжкой — идеальное решение для рабочих зон, где требуется как протирка рук, так и уборка поверхностей, разработанное с учетом вашего рабочего процесса. Вы касаетесь только той салфетки, которую собираетесь использовать, благодаря полистовому отбору бумаги с любого угла с вращающегося клапана. Диспенсер прост в использовании, гигиеничный и надежный. Полистовой отбор снижает расход материала до 37% по сравнению с системой Tork® с центральной вытяжкой.', 79.5841, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/473190.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '473186', 'Tork Reflex™ переносной диспенсер с центральной подачей, сочетание белого и бирюзового, система M4', 'dispenser', 'hand_towel', 'M4', 'Elevation',
    'white', 'high', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Переносной диспенсер Tork® Reflex™ с полистовым отбором для рулонов с центральной вытяжкой — это решение, которое всегда под рукой. Диспенсер прост в использовании, гигиеничный и надежный. Полистовой отбор снижает расход материала до 37% по сравнению с системой Tork® с центральной вытяжкой. Идеально подходит для использования в сфере гостеприимства, клининга и других мобильных сред. Благодаря прочной ручке диспенсер легко носить с собой или вешать на тележку. Поставляется с одним двухслойным бел', 92.9825, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical', 'Office']::TEXT[], FALSE, 'http://cdn/images/473186.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '101221', 'Протирочная бумага Tork в рулонах малого размера, белая, формат Plus, система M1', 'refill', 'hand_towel', 'M1', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Двухслойная протирочная бумага Tork Плюс для универсального использования идеально подходит для удаления жидкости и протирки рук. Совместима с диспенсерами Tork® Мини с центральной вытяжкой, она представляет собой компактное универсальное решение для производственных помещений, где требуется протирать и руки, и поверхности.', 5.0748, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/101221.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '120123', 'Tork базовая протирочная бумага, центральная подача, белая, система M1', 'refill', 'hand_towel', 'M1', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Однослойная базовая протирочная бумага Tork идеально подходит для протирки поверхностей и высушивания рук. Сохраняет прочность во влажном состоянии. Совместима с диспенсерами Tork® Mini, она представляет собой компактное универсальное решение для производственных помещений, где требуется протирать и руки, и поверхности.', 3.6757, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/120123.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '130034', 'Tork протирочная бумага с центральной подачей, белая, система M2', 'refill', 'hand_towel', 'M2', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Однослойная универсальная протирочная бумага Tork белая обладает высокой прочностью и впитываемостью, благодаря чему она идеально подходит для протирки поверхностей и рук. Бумага совместима с диспенсерами Tork® с центральной вытяжкой это универсальное решение высокой емкости для производственных помещений, где требуется протирать руки и поверхности.', 8.5133, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/130034.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '130044', 'Tork Плюс протирочная бумага в рулоне с ЦВ', 'refill', 'hand_towel', 'M2', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Идеально подходит для удаления жидкости, легкой уборки и вытирания рук. Бумага качества QuickDry обладает более высоким уровнем впитываемости и лучше сохраняет прочность во влажном состоянии, чем обычная бумага.', 10.6239, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/130044.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '473242', 'Tork ReflexTM протир. бумага в рулоне с ЦВ, 1 слой, 895 л/рулон', 'refill', 'hand_towel', 'M4', 'Elevation',
    'white', 'high', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Однослойная многофункциональная протирочная бумага Tork Reflex™ идеально подходит для протирки поверхностей и вытирания рук благодаря своей прочности и высокой впитывающей способности. Эту бумагу можно использовать в диспенсере Tork Reflex™ с центральной подачей листов, который оптимизирует рабочий процесс вашей команды, сокращает расход бумаги и минимизирует риск перекрестного загрязнения.', 6.8413, 60,
    'C', ARRAY['HoReCa', 'Industrial', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/473242.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '473412', 'Tork RefleхТМ протир. бумага в рулоне с ЦВ, премиальное качество бумаги QuiqDry (полистовая подача)', 'refill', 'hand_towel', 'M4', 'Elevation',
    'white', 'high', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Однослойная универсальная протирочная бумага Tork Reflex™ идеально подходит для протирки поверхностей и рук благодаря высокой прочности и отличной впитываемости. Эту бумагу можно использовать в диспенсере Tork Reflex™ с центральной вытяжкой и полистовой подачей, который обеспечивает эффективность рабочего процесса, снижает расход и сводит к минимуму риск перекрестного заражения.', 4.2019, 60,
    'C', ARRAY['HoReCa', 'Industrial', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/473412.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '473480', 'Tork ReflexTM протир. бумага в рулоне с ЦВ )', 'refill', 'hand_towel', 'M4', 'Elevation',
    'none', 'high', NULL, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Однослойная многофункциональная протирочная бумага Tork Reflex™ идеально подходит для протирки поверхностей и вытирания рук благодаря своей прочности и высокой впитывающей способности. Эту бумагу можно использовать в диспенсере Tork Reflex™ с центральной подачей листов, который оптимизирует рабочий процесс вашей команды, сокращает расход бумаги и минимизирует риск перекрестного загрязнения.', 5.7222, 60,
    'C', ARRAY['HoReCa', 'Industrial', 'Office']::TEXT[], TRUE, 'http://cdn/images/473480.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '652000', 'Tork Performance напольный диспенсер для материалов в рулоне', 'dispenser', 'wiper', 'W1', 'Performance',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Напольный диспенсер Tork для протирочных материалов в рулонах разработан для обеспечения безопасности и надежности с функциями удобного отрыва и загрузки. Tork Performance — новое поколение диспенсеров, созданных для эффективной протирки. Правильное сочетание диспенсеров и протирочных материалов позволяет повысить производительность, снижая при этом общие эксплуатационные затраты.', 316.5815, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical']::TEXT[], FALSE, 'http://cdn/images/652000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '652008', 'Tork Performance напольный диспенсер для материалов в рулоне', 'dispenser', 'wiper', 'W1', 'Performance',
    'none', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Напольный диспенсер Tork для протирочных материалов в рулонах разработан для обеспечения безопасности и надежности с функциями удобного отрыва и загрузки. Tork Performance — новое поколение диспенсеров, созданных для эффективной протирки. Правильное сочетание диспенсеров и протирочных материалов позволяет повысить производительность, снижая при этом общие эксплуатационные затраты.', 316.5815, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], FALSE, 'http://cdn/images/652008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '652100', 'Tork Performance настенный диспенсер для материалов в рулоне', 'dispenser', 'wiper', 'W1', 'Performance',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Настенный диспенсер Tork для протирочных материалов в рулонах разработан для обеспечения эффективности и надежности с функциями удобной загрузки и возможностью брать необходимое количество бумаги только одной рукой. Tork Performance — новое поколение диспенсеров, созданных для эффективной протирки. Правильное сочетание диспенсеров и протирочных материалов позволяет повысить производительность, снижая при этом общие эксплуатационные затраты.', 160.9467, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical']::TEXT[], FALSE, 'http://cdn/images/652100.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '652108', 'Tork Performance настенный диспенсер для материалов в рулоне', 'dispenser', 'wiper', 'W1', 'Performance',
    'none', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Настенный диспенсер Tork для протирочных материалов в рулонах разработан для обеспечения эффективности и надежности с функциями удобной загрузки и возможностью брать необходимое количество бумаги только одной рукой. Tork Performance — новое поколение диспенсеров, созданных для эффективной протирки. Правильное сочетание диспенсеров и протирочных материалов позволяет повысить производительность, снижая при этом общие эксплуатационные затраты.', 160.9467, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], FALSE, 'http://cdn/images/652108.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '653000', 'Tork Performance диспенсер Макси для материалов в рулоне (съемная втулка)', 'dispenser', 'wiper', 'W2', 'Performance',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Диспенсер Tork Макси с центральной вытяжкой серии Performance — обеспечивает эффективность и ускоряет процесс уборки благодаря отбору бумажных листов одной рукой. Tork Performance — новое поколение диспенсеров, созданных для эффективной уборки. Правильное сочетание диспенсеров и протирочных материалов позволяет повысить производительность, снижая при этом общие эксплуатационные затраты.', 146.3389, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical']::TEXT[], FALSE, 'http://cdn/images/653000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '653008', 'Tork Performance диспенсер Макси для материалов в рулоне (съемная втулка)', 'dispenser', 'wiper', 'W2', 'Performance',
    'none', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Диспенсер Tork Макси с центральной вытяжкой серии Performance — обеспечивает эффективность и ускоряет процесс уборки благодаря отбору бумажных листов одной рукой. Tork Performance — новое поколение диспенсеров, созданных для эффективной уборки. Правильное сочетание диспенсеров и протирочных материалов позволяет повысить производительность, снижая при этом общие эксплуатационные затраты.', 146.3389, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], FALSE, 'http://cdn/images/653008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '654000', 'Tork Performance диспенсер для материалов в салфетках', 'dispenser', 'napkin', 'W4', 'Performance',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Диспенсеры Tork для сложенных салфеток серии Performance защищают продукт от грязи и обеспечивают полистовую подачу в целях снижения потребления и отходов. Tork Performance — новое поколение диспенсеров, созданных для эффективной протирки. Правильное сочетание диспенсеров и протирочных материалов позволяет повысить производительность, снижая при этом общие эксплуатационные затраты.', 74.6041, 50,
    'A', ARRAY['Industrial', 'Medical']::TEXT[], FALSE, 'http://cdn/images/654000.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '654008', 'Tork Performance диспенсер для материалов в салфетках', 'dispenser', 'napkin', 'W4', 'Performance',
    'none', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Диспенсеры Tork для сложенных салфеток серии Performance защищают листы от грязи и обеспечивают полистовую подачу в целях снижения потребления и отходов. Tork Performance — новое поколение диспенсеров, созданных для эффективной протирки. Правильное сочетание диспенсеров и протирочных материалов позволяет повысить производительность, снижая при этом общие эксплуатационные затраты.', 83.568, 50,
    'A', ARRAY['Industrial']::TEXT[], FALSE, 'http://cdn/images/654008.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '130060', 'Tork протирочная бумага повышенной прочности, белая, система W1', 'refill', 'wiper', 'W1', 'Performance',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Протирочная бумага Tork повышенной прочности эффективно впитывает влагу, жир и масло и сохраняет высокую прочность во влажном состоянии. Бумага может использоваться как в напольных, так и настенных диспенсерах для протирочных материалов в рулонах Tork, разработанных для безопасности, эффективности и надежности благодаря легкой загрузке и отрыву, а также возможности отбора нетканого материала только одной рукой.', 51.2459, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical']::TEXT[], FALSE, 'http://cdn/images/130060.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '130050', 'Tork протирочная бумага формата Plus, голубая, система W1', 'refill', 'wiper', 'W1', 'Performance',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Двухслойная универсальная протирочная бумага Tork Плюс идеально подходит для удаления жидкости и высушивания рук. Бумага может использоваться как в напольных, так и настенных диспенсерах для протирочных материалов в рулонах Tork, разработанных для безопасности, эффективности и надежности благодаря легкой загрузке и отрыву, а также с возможностью отбора нетканого материала только одной рукой.', 65.5928, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], TRUE, 'http://cdn/images/130050.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '130051', 'Tork Плюс протирочная бумага в рулоне', 'refill', 'wiper', 'W1', 'Performance',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Идеально подходит для удаления жидкости, легкой уборки и вытирания рук. Бумага качества QuickDry обладает более высоким уровнем впитываемости и лучше сохраняет прочность во влажном состоянии, чем обычная бумага.', 40.9303, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], FALSE, 'http://cdn/images/130051.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '130080', 'Tork протирочная бумага повышенной прочности для промышленных предприятий, голубая, cистема W1', 'refill', 'wiper', 'W1/2', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Протирочная бумага Tork повышенной прочности для удаления масла и жира трехслойная — это самая прочная бумага с повышенной впитываемостью. Плотный материал защищает руки от повреждений. Бумага может использоваться как в напольных, так и настенных диспенсерах для протирочных материалов в рулонах Tork, разработанных для безопасности, эффективности и надежности благодаря легкой загрузке и отрыву, а также возможности отбора нетканого материала только одной рукой.', 60.8738, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], FALSE, 'http://cdn/images/130080.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '130052', 'Tork протирочная бумага формата Plus, система W1/W2', 'refill', 'wiper', 'W1/2', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Двухслойная универсальная протирочная бумага Tork Плюс идеально подходит для удаления жидкости и высушивания рук. Эту бумагу можно использовать в безопасных, эффективных и надежных напольных или настенных диспенсерах Tork или в диспенсерах с центральной вытяжкой, разработанных для более удобного отбора листов одной рукой.', 20.4177, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], FALSE, 'http://cdn/images/130052.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '130081', 'Tork протирочная бумага повышенной прочности для промышленных предприятий, голубая, система W1/W2', 'refill', 'wiper', 'W1/2', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Протирочная бумага Tork повышенной прочности для удаления масла и жира трехслойная — это самая прочная бумага с повышенной впитываемостью. Плотный материал защищает руки от повреждений. Эту бумагу можно использовать в безопасных, эффективных и надежных напольных или настенных диспенсерах Tork или в диспенсерах с центральной вытяжкой, разработанных для более удобного отбора листов одной рукой.', 18.07, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], TRUE, 'http://cdn/images/130081.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '500137', 'Tork нетканный материал для легких работ, в комби рулоне, 150М, W1/W2/W3', 'refill', 'wiper', 'W3', 'Performance',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Идеальный материал для легкой уборки. Удаляйте пыль и грязь влажной или сухой салфеткой. Салфетку можно промывать и использовать многократно. Выберите рулон Combi-roll, чтобы получить салфетки меньшего размера и использовать ровно столько, сколько необходимо. Салфетки Tork Light-Duty Cleaning Cloth изготовлены с использованием технологии Tork exelCLEAN® и являются экологичным выбором, поскольку мы снизили выбросы CO2 при производстве exelCLEAN на 28% с 2011 года. Упаковка изготовлена ​​из перера', 25.0, 100,
    'C', ARRAY['HoReCa', 'Industrial', 'Medical']::TEXT[], FALSE, 'http://cdn/images/500137.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '510137', 'Tork нетканый материал в малом рулоне, 127М, (съемная втулка)', 'refill', 'wiper', 'W3', 'Performance',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Превосходно впитывает масло и воду, легко снимает жир и глубоко въевшуюся грязь
Подходит для использования с большинством химических растворителей: Удерживает и выводит растворители более эффективно, чем продукция из текстиля, что уменьшает расход
Может использоваться повторно, долговечный протирочный материал — прекрасно подойдет в качестве полотенца для уборки и замены ветоши', 54.6205, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical']::TEXT[], FALSE, 'http://cdn/images/510137.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '520304', 'Tork протирочный нетканый материал для промышленных предприятий, серый, 361М, система W1', 'refill', 'wiper', 'W1', 'Image Line',
    'stainless_steel', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Нетканый материал Tork для удаления масла и жира — идеальная замена различных видов ветоши. Этим мягким и эластичным материалом можно производить очистку труднодоступных мест и сложных деталей. Он не оставляет царапин на поверхностях, но при этом такой прочный, что позволяет эффективно удалять масло, жир и грязь и может использоваться с большинством растворителей. Используется с напольными и настенными диспенсерами Tork для протирочных материалов в рулонах для обеспечения безопасности, эффективн', 193.8465, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], TRUE, 'http://cdn/images/520304.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '520337', 'Tork нетканый материал для удаления масла и жира в малом рулоне, 127М, Система W3 (съемная втулка)', 'refill', 'wiper', 'W3', 'Image Line',
    'stainless_steel', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Подходит для использования с большинством химических растворителей: Удерживает и выводит растворители более эффективно, чем продукция из текстиля, что уменьшает расход
Превосходно впитывает масло и воду, легко снимает жир и глубоко въевшуюся грязь
Может использоваться повторно, долговечный протирочный материал — прекрасно подойдет в качестве полотенца для уборки и замены ветоши', 70.5773, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], FALSE, 'http://cdn/images/520337.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '190494', 'Tork безворсовый нетканый материал в большом рулоне', 'refill', 'wiper', 'W3', 'Performance',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Безворсовый нетканый материал Tork прочный и эластичный. Рулон упакован в защитную картонную коробку и может использоваться как в напольных, так и настенных диспенсерах Tork для протирочных материалов в рулонах, разработанных для безопасности, эффективности и надежности благодаря легкой загрузке и отрыву, а также возможности отбора нетканого материала только одной рукой.', 151.8078, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], FALSE, 'http://cdn/images/190494.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '190493', 'Tork безворсовый нетканый материал в салфетках', 'refill', 'napkin', 'W8', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Безворсовый нетканый материал Tork — прочный, гибкий, упакован в небольшую переносную пластиковую упаковку. Его можно использовать в диспенсере Tork для небольших упаковок, разработанном специально для безопасной, эффективной и надежной эксплуатации: материал легко загружать и отбирать по листу, а также возможно вытаскивать салфетки одной рукой.', 20.5487, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/190493.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '190492', 'Tork безворсовый нетканый материал в ведре-диспенсере', 'dispenser', 'wiper', 'W10', 'Elevation',
    'none', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Безворсовый нетканый материал Tork прочный и эластичный. Из рулонов нетканого материала в ведре можно делать собственные влажные салфетки с использованием нужных химикатов. Благодаря полистовому отбору и удобной крышке салфетки не высыхают.', 37.6076, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], TRUE, 'http://cdn/images/190492.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '190491', 'Tork безворсовый нетканый материал в рулоне для ведра', 'refill', 'wiper', 'W10', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Безворсовый нетканый материал Tork прочный и эластичный. Tork безворсовый нетканый материал может использоваться с растворителями и с дезинфицирующими и моющими средствами. Благодаря полистовому отбору и удобной крышке салфетки не высыхают.', 25.0717, 50,
    'A', ARRAY['HoReCa', 'Industrial']::TEXT[], FALSE, 'http://cdn/images/190491.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '530137', 'Tork нетканый материал повышенной прочности в малом рулоне (съемная втулка)', 'refill', 'wiper', 'W3', 'Performance',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Подходит для использования с большинством химических растворителей: Удерживает и выводит растворители более эффективно, чем продукция из текстиля, что уменьшает расход
Суперпрочная конструкция защищает руки от ожогов и металлической стружки
Может использоваться повторно, долговечный протирочный материал — прекрасно подойдет в качестве полотенца для уборки и замены ветоши', 46.5847, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical']::TEXT[], FALSE, 'http://cdn/images/530137.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '90537', 'Tork нетканый материал для интенсивной очистки в малом рулоне (съемная втулка)', 'refill', 'wiper', 'W3', 'Performance',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Нетканый материал Tork для интенсивной очистки хорошо впитывает влагу и обладает высокой прочностью, благодаря чему не рвется и идеально подходит для многократного использования. Рекомендован для использования в диспенсерах Tork серии Performance. Диспенсер защищает материал от влаги и грязи, а также позволяет отбирать материал по одному листу, что снижает расход и количество отходов.', 87.728, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical']::TEXT[], FALSE, 'http://cdn/images/90537.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '570137', 'Tork нетканый материал суперпрочный в малом рулоне (съемная втулка)', 'refill', 'wiper', 'W3', 'Performance',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Может использоваться повторно, долговечный протирочный материал — прекрасно подойдет в качестве полотенца для уборки и замены ветоши
Подходит для использования с большинством химических растворителей: Удерживает и выводит растворители более эффективно, чем продукция из текстиля, что уменьшает расход
Суперпрочная конструкция защищает руки от ожогов и металлической стружки', 42.6586, 50,
    'A', ARRAY['HoReCa', 'Industrial', 'Medical']::TEXT[], FALSE, 'http://cdn/images/570137.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '190578', 'Tork безворсовые нетканые протирочные салфетки, голубые, система W4', 'refill', 'napkin', 'W4', 'Performance',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Безворсовый нетканый материал Tork практически не оставляет ворс и может использоваться с любыми растворителями. С ним можно выполнять самые ответственные задачи, не повреждая чувствительные поверхности и электронные элементы. Рекомендован для использования в настенных диспенсерах Tork для протирочных материалов в салфетках. Диспенсер защищает материал от влаги и грязи, а также позволяет отбирать материал по одному листу, что снижает расход и количество отходов.', 25.1406, 50,
    'A', ARRAY['Industrial']::TEXT[], TRUE, 'http://cdn/images/190578.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '473179', 'Tork нетканые протирочные салфетки для кухонь, белые, система W4', 'refill', 'napkin', 'W4', 'Performance',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Поддерживайте чистоту даже на самой загруженной кухне с этим универсальным нетканым материалом для кухни. Его плотная, хорошо впитывающая текстура позволяет быстро вытирать различные жидкости. Материал термостойкий и остается прочным даже во влажном состоянии, обеспечивая безопасность и надежность при использовании. Этот нетканый материал изготовлен из волокон натурального происхождения* и поставляется в упаковке из переработанных материалов, что позволяет вам снизить воздействие на окружающую с', 19.7222, 50,
    'A', ARRAY['Industrial', 'Medical']::TEXT[], TRUE, 'http://cdn/images/473179.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '190592', 'Tork влажные салфетки для очистки рук в ведре-диспенсере, белые, система W14', 'dispenser', 'napkin', 'W14', 'Elevation',
    'none', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Чистящие влажные салфетки Tork для удобства и эффективной очистки рук, когда вода недоступна.', 19.3548, 50,
    'A', ARRAY['Industrial']::TEXT[], TRUE, 'http://cdn/images/190592.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '190692', 'Tork влажные салфетки для рук , сменный блок для системы W14', 'refill', 'napkin', 'W14', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Чистящие влажные салфетки Tork для удобства и эффективной очистки рук, когда вода недоступна. Простая и эффективная перезаправка продукта.', 11.319, 50,
    'A', ARRAY['Industrial']::TEXT[], TRUE, 'http://cdn/images/190692.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '478711', 'Tork LinStyle® салфетки 39х39 белые', 'refill', 'napkin', 'NA', 'Elevation',
    'white', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Салфетки Tork LinStyle® Premium — идеальное решение для ресторанов высокого класса, где необходимо высокое качество, чтобы произвести хорошее впечатление на гостей. Каждая салфетка, на вид и на ощупь напоминающая настоящую ткань, заметно мягче и объемнее обычных салфеток и при этом особенно хорошо впитывает влагу. Создайте элегантную атмосферу для ваших клиентов с помощью широкого ассортимента салфеток Tork современных и классических оттенков.', 7.4936, 50,
    'A', ARRAY['Medical']::TEXT[], TRUE, 'http://cdn/images/478711.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '478890', 'Tork LinStyle® салфетки 39х39 фисташковые', 'refill', 'napkin', '-', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Салфетки Tork LinStyle® Premium — идеальное решение для ресторанов высокого класса, где необходимо высокое качество, чтобы произвести хорошее впечатление на гостей. Каждая салфетка, на вид и на ощупь напоминающая настоящую ткань, заметно мягче и объемнее обычных салфеток и при этом особенно хорошо впитывает влагу. Создайте элегантную атмосферу для ваших клиентов с помощью широкого ассортимента салфеток Tork современных и классических оттенков.', 10.1022, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], TRUE, 'http://cdn/images/478890.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '478848', 'Tork LinStyle® салфетки 39х39 темно-зеленые', 'refill', 'napkin', '-', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Салфетки Tork LinStyle® Premium — идеальное решение для ресторанов высокого класса, где необходимо высокое качество, чтобы произвести хорошее впечатление на гостей. Каждая салфетка, на вид и на ощупь напоминающая настоящую ткань, заметно мягче и объемнее обычных салфеток и при этом особенно хорошо впитывает влагу. Создайте элегантную атмосферу для ваших клиентов с помощью широкого ассортимента салфеток Tork современных и классических оттенков.', 10.1022, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], TRUE, 'http://cdn/images/478848.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '478852', 'Tork LinStyle® салфетки 39х39 оранжевые', 'refill', 'napkin', '-', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Салфетки Tork LinStyle® Premium — идеальное решение для ресторанов высокого класса, где необходимо высокое качество, чтобы произвести хорошее впечатление на гостей. Каждая салфетка, на вид и на ощупь напоминающая настоящую ткань, заметно мягче и объемнее обычных салфеток и при этом особенно хорошо впитывает влагу. Создайте элегантную атмосферу для ваших клиентов с помощью широкого ассортимента салфеток Tork современных и классических оттенков.', 10.1022, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], TRUE, 'http://cdn/images/478852.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '478888', 'Tork LinStyle® салфетки 39х39 синие', 'refill', 'napkin', '-', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Салфетки Tork LinStyle® Premium — идеальное решение для ресторанов высокого класса, где необходимо высокое качество, чтобы произвести хорошее впечатление на гостей. Каждая салфетка, на вид и на ощупь напоминающая настоящую ткань, заметно мягче и объемнее обычных салфеток и при этом особенно хорошо впитывает влагу. Создайте элегантную атмосферу для ваших клиентов с помощью широкого ассортимента салфеток Tork современных и классических оттенков.', 10.1022, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], TRUE, 'http://cdn/images/478888.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '478886', 'Tork LinStyle® салфетки 39х39 красные', 'refill', 'napkin', '-', 'Elevation',
    'none', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Салфетки Tork LinStyle® Premium — идеальное решение для ресторанов высокого класса, где необходимо высокое качество, чтобы произвести хорошее впечатление на гостей. Каждая салфетка, на вид и на ощупь напоминающая настоящую ткань, заметно мягче и объемнее обычных салфеток и при этом особенно хорошо впитывает влагу. Создайте элегантную атмосферу для ваших клиентов с помощью широкого ассортимента салфеток Tork современных и классических оттенков.', 10.1022, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], TRUE, 'http://cdn/images/478886.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '478725', 'Tork LinStyle® салфетки 39х39 черные', 'refill', 'napkin', '-', 'Elevation',
    'black', 'any', NULL, '{"daily_use_per_person": 4, "portions_per_unit": 800}'::jsonb,
    FALSE, 'Салфетки Tork LinStyle® Premium — идеальное решение для ресторанов высокого класса, где необходимо высокое качество, чтобы произвести хорошее впечатление на гостей. Каждая салфетка, на вид и на ощупь напоминающая настоящую ткань, заметно мягче и объемнее обычных салфеток и при этом особенно хорошо впитывает влагу. Создайте элегантную атмосферу для ваших клиентов с помощью широкого ассортимента салфеток Tork современных и классических оттенков.', 25.0, 100,
    'C', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/478725.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '272213', 'Tork Xpressnap® диспенсер для салфеток, вертикальный, светло-серый, система N4', 'dispenser', 'hand_towel', 'N4', 'Image Line',
    'stainless_steel', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork Xpressnap® диспенсер большой емкости — это отличное решение для объектов высокой проходимости с большим расходом салфеток. Этот современный диспенсер обеспечивает полистовой отбор салфеток, повышая уровень гигиены и снижая расход салфеток до 25% по сравнению с традиционными системами диспенсерных салфеток.', 132.5137, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/272213.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '272513', 'Tork Xpressnap® диспенсер для линии раздачи', 'dispenser', 'hand_towel', 'N4', 'Image Line',
    'stainless_steel', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Tork Xpressnap® настольный диспенсер для салфеток идеально подходит для ресторанов с частичным самообслуживанием, где салфетки выдаются в центральном месте. Этот современный диспенсер обеспечивает полистовой отбор салфеток, повышая уровень гигиены и снижая расход по меньшей мере на 43% по сравнению с традиционными системами диспенсерных салфеток.', 95.4487, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/272513.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '272613', 'Tork Xpressnap® диспенсер для салфеток, настольный, светло-серый, система N4', 'dispenser', 'hand_towel', 'N4', 'Image Line',
    'stainless_steel', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Настольный диспенсер для салфеток Tork Xpressnap® подходит для ресторанов любого типа. При небольшом количестве посетителей может использоваться также на линии раздачи. Этот компактный и современный диспенсер обеспечивает полистовой отбор салфеток, повышая уровень гигиены и значительно снижая расход салфеток по сравнению с традиционными системами диспенсерных салфеток. Доступен в широком спектре современных расцветок, позволяя с легкостью вписаться в ваш интерьер.', 64.2411, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/272613.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '272611', 'Tork Xpressnap®  диспенсер настольный', 'dispenser', 'hand_towel', 'N4', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Настольный диспенсер для салфеток Tork Xpressnap® подходит для ресторанов любого типа. При небольшом количестве посетителей может использоваться также на линии раздачи. Этот компактный и современный диспенсер обеспечивает полистовой отбор салфеток, повышая уровень гигиены и значительно снижая расход салфеток по сравнению с традиционными системами диспенсерных салфеток. Доступен в широком спектре современных расцветок, позволяя с легкостью вписаться в ваш интерьер.', 64.2411, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/272611.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '273002', 'Tork Xpressnap® диспенсер для салфеток, настольный, компактный, отделка под грецкий орех, система N4, серия Image', 'dispenser', 'hand_towel', 'N4', 'Elevation',
    'none', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Диспенсер для салфеток Tork Xpressnap® для линии раздачи идеально подходит для современных ресторанов с частичным и полным циклом обслуживания, где используются салфетки в центральном месте. Этот компактный современный диспенсер из натуральных материалов обеспечивает полистовой отбор салфеток, повышая уровень гигиены и значительно снижая расход салфеток (как минимум на 25 %) по сравнению с традиционными диспенсерами.', 127.2492, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/273002.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '15850', 'Tork Xpressnap® диспенсерные салфетки ультрамягкие (5 пачек в спайке, 8 спаек в коробе)', 'dispenser', 'hand_towel', 'N4', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Салфетки Tork Xpressnap® Premium идеально подходят для ресторанов самообслуживания. Помогает вам сократить расход салфеток как минимум на 25% по сравнению с использованием традиционных диспенсеров для салфеток. Tork Xpressnap® диспенсерные салфетки ультрамягкие белые — прекрасное решение для заведений, которые ценят удобство, экономию и качество.', 13.0901, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/15850.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '10840', 'Tork Xpressnap® диспенсерные салфетки (5 пачек в спайке, 8 спаек в коробе)', 'dispenser', 'hand_towel', 'N4', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Салфетки Tork Xpressnap® Premium идеально подходят для ресторанов самообслуживания. Помогает вам сократить расход салфеток как минимум на 25% по сравнению с использованием традиционных диспенсеров для салфеток. Tork Xpressnap® диспенсерные салфетки ультрамягкие белые — прекрасное решение для заведений, которые ценят удобство, экономию и качество.', 13.2087, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/10840.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '12840', 'Tork Xpressnap® диспенсерные салфетки крафт (5 пачек в спайке, 8 спаек в коробе)', 'dispenser', 'hand_towel', 'N4', 'Elevation',
    'none', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Диспенсеры для салфеток Tork Xpressnap® идеально подходят для ресторанов самообслуживания. Система Tork Xpressnap® гарантирует сокращение расхода салфеток до 25% по сравнению с традиционными диспенсерами для салфеток. Однослойные диспенсерные салфетки Tork Xpressnap® натурального цвета изготовлены из 100% переработанного сырья без отбеливания. Это лучший выбор для тех, кто хочет показать свою экологическую ответственность.', 10.3156, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], TRUE, 'http://cdn/images/12840.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '272900', 'Tork Xpressnap Fit® настольный диспенсер для салфеток, черный, система N14', 'dispenser', 'hand_towel', 'N14', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Управляйте бизнесом более эффективно. Диспенсеры Tork Xpressnap Fitreg идеально подходят для небольших сетевых и независимых ресторанов и могут использоваться на столах и на линии раздачи. Диспенсеры Xpressnap обеспечивают полистовую подачу салфеток, что позволяет сократить расход салфеток и, соответственно, количество отходов. В отличие от традиционных диспенсеров для салфеток, Tork Xpressnap Fitreg дает возможность не только обслужить большее количество гостей, но и экономить место для хранени', 62.9132, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/272900.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '272901', 'Tork Xpressnap Fit® диспенсер салфеток для линии раздачи, черный, система N14', 'dispenser', 'hand_towel', 'N14', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Управляйте бизнесом более эффективно. Диспенсеры Tork Xpressnap Fit® идеально подходят для небольших сетевых и независимых ресторанов и могут использоваться на столах и на линии раздачи. Диспенсеры Xpressnap обеспечивают полистовую подачу салфеток, что позволяет сократить расход салфеток и, соответственно, количество отходов. В отличие от традиционных диспенсеров для салфеток, Tork Xpressnap Fit® дает возможность не только обслужить большее количество гостей, но и экономить место для хранения за', 103.1795, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/272901.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '962900', 'Tork Xpressnap Fit® стартовый набор: черный настольный диспенсер и салфетки, система N14', 'dispenser', 'hand_towel', 'N14', 'Elevation',
    'black', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Благодаря уникальному сложению салфетка стандартного размера легко помещается в компактный диспенсер.
В диспенсере предусмотрено окошко для рекламы AD-A-Glance® — используйте его для привлечения внимания гостей к вашим продуктам и публикуйте обращения к гостям.
Индикатор расхода показывает, когда пора перезаправить салфетки — это гарантирует их постоянное наличие. Теперь салфетки больше не закончатся в часы наибольшего наплыва посетителей.
Надежный и легкий в обслуживании диспенсер экономит ваше', 73.1813, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], FALSE, 'http://cdn/images/962900.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '15830', 'Tork XPN Fit салфетки диспенсерные (6 пачек в спайке, 6 спаек в коробе)', 'dispenser', 'hand_towel', 'N14', 'Elevation',
    'white', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'Управляйте бизнесом более эффективно. Салфетки Tork Xpressnap Fit® Advanced идеально подходят для ресторанов быстрого обслуживания, баров и кафе. В отличие от стандартных диспенсеров для салфеток, система Tork Xpressnap Fit® позволяет обслужить большее количество посетителей, экономит место на складе, а также сокращает вдвое количество выброшенных неиспользованных салфеток. Двухслойные Tork Xpressnap Fit® диспенсерные салфетки белые — лучший выбор для заведений, которые хотят подчеркнуть свою за', 6.7348, 50,
    'A', ARRAY['HoReCa', 'Medical', 'Office']::TEXT[], TRUE, 'http://cdn/images/15830.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;
INSERT INTO products (
    sku, name, category, product_type, system_code, design_line,
    color, traffic_level, dimensions_cm, refill_norms,
    is_focus_item, description, price_eur, priority_rank,
    margin_tier, segment_fit, is_promo, image_url
) VALUES (
    '12830', 'Tork XPN Fit салфетки диспенсерные крафт (6 пачек в спайке, 6 спаек в коробе)', 'dispenser', 'hand_towel', 'N14', 'Elevation',
    'none', 'any', '{"w": 33.7, "h": 37.2, "d": 20.3}'::jsonb, '{"daily_use_per_person": 2, "portions_per_unit": 400}'::jsonb,
    FALSE, 'правляйте бизнесом более эффективно. Салфетки Tork Xpressnap Fit® Advanced идеально подходят для ресторанов быстрого обслуживания, баров, кафе и прилавков с готовой едой. В отличие от стандартных диспенсеров для салфеток, система Tork Xpressnap Fit® позволяет обслужить большее количество посетителей, экономит место на складе, а также сокращает вдвое количество выброшенных неиспользованных салфеток. Двухслойные Tork Xpressnap Fit® диспенсерные салфетки натуральные изготовлены из 100% переработанн', 6.9482, 50,
    'A', ARRAY['HoReCa', 'Office']::TEXT[], TRUE, 'http://cdn/images/12830.png'
) ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    product_type = EXCLUDED.product_type,
    system_code = EXCLUDED.system_code,
    design_line = EXCLUDED.design_line,
    color = EXCLUDED.color,
    traffic_level = EXCLUDED.traffic_level,
    dimensions_cm = EXCLUDED.dimensions_cm,
    refill_norms = EXCLUDED.refill_norms,
    is_focus_item = EXCLUDED.is_focus_item,
    description = EXCLUDED.description,
    price_eur = EXCLUDED.price_eur,
    priority_rank = EXCLUDED.priority_rank,
    margin_tier = EXCLUDED.margin_tier,
    segment_fit = EXCLUDED.segment_fit,
    is_promo = EXCLUDED.is_promo,
    image_url = EXCLUDED.image_url;

-- 5. Seed distributor_prices for all 165 products across distributors 1, 2, 3
INSERT INTO distributor_prices (distributor_id, product_sku, price, in_stock)
SELECT 
    d.id,
    p.sku,
    ROUND(p.price_eur * 617.93, 2),
    TRUE
FROM distributors d
CROSS JOIN products p
ON CONFLICT (distributor_id, product_sku) DO UPDATE SET
    price = EXCLUDED.price,
    in_stock = EXCLUDED.in_stock;

-- 6. Create or replace view v_products_active
CREATE OR REPLACE VIEW v_products_active AS
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
    p.priority_rank,
    p.margin_tier,
    p.segment_fit,
    p.is_promo,
    COALESCE(p.image_url, 'http://cdn/images/' || p.sku || '.png') AS image_url,
    ROUND(p.price_eur * COALESCE(
        (SELECT rate FROM exchange_rates WHERE currency_from = 'EUR' AND currency_to = 'KZT' ORDER BY updated_at DESC LIMIT 1),
        617.9300
    ), 2) AS current_price_kzt
FROM products p;

-- 7. Optimized indexes
CREATE INDEX IF NOT EXISTS idx_products_scoring 
ON products(category, product_type, color, system_code, priority_rank, is_focus_item);

CREATE INDEX IF NOT EXISTS idx_products_segments 
ON products USING GIN(segment_fit);
