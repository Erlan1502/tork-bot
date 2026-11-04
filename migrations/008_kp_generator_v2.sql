-- ==============================================================================
-- MIGRATION 008: COMMERCIAL PROPOSAL GENERATOR V2 (KAZAKHSTAN 5-PAGE KP)
-- ==============================================================================

-- 1. Ensure phone column in allowed_managers table
ALTER TABLE allowed_managers 
ADD COLUMN IF NOT EXISTS phone VARCHAR(50) DEFAULT '+7 (777) 777-77-77';

-- 2. Update default manager phones if null
UPDATE allowed_managers 
SET phone = '+7 (777) 777-77-77' 
WHERE phone IS NULL;

-- 3. Ensure client details columns in user_sessions_leads
ALTER TABLE user_sessions_leads
ADD COLUMN IF NOT EXISTS client_facility VARCHAR(255) DEFAULT 'Гостиничный комплекс, 5 этажей, 42 санузла';

ALTER TABLE user_sessions_leads
ADD COLUMN IF NOT EXISTS client_city VARCHAR(100) DEFAULT 'г. Астана, Казахстан';

COMMENT ON COLUMN user_sessions_leads.client_facility IS 'Тип объекта и масштаб (например: Гостиничный комплекс, 5 этажей, 42 санузла)';
COMMENT ON COLUMN user_sessions_leads.client_city IS 'Город и локация объекта (например: г. Астана, Казахстан)';

