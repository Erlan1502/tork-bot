-- ==============================================================================
-- MIGRATION 004: MANAGER-ONLY MODE (SELECTED SKU & VISUALIZER SUPPORT)
-- ==============================================================================

ALTER TABLE user_sessions_leads 
ADD COLUMN IF NOT EXISTS selected_sku VARCHAR(50) DEFAULT '551000';

ALTER TABLE user_sessions_leads 
ADD COLUMN IF NOT EXISTS last_rendered_image_url TEXT;

COMMENT ON COLUMN user_sessions_leads.selected_sku IS 'Currently selected Tork dispenser SKU for AI fitting';

