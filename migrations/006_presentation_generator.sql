-- ==============================================================================
-- MIGRATION 006: PRESENTATION GENERATOR SUPPORT
-- Adds before_image_url and last_rendered_image_url to user_sessions_leads
-- ==============================================================================

ALTER TABLE user_sessions_leads 
ADD COLUMN IF NOT EXISTS before_image_url TEXT;

ALTER TABLE user_sessions_leads 
ADD COLUMN IF NOT EXISTS last_rendered_image_url TEXT;

COMMENT ON COLUMN user_sessions_leads.before_image_url IS 'Initial client washroom photo (base64 or URL)';
COMMENT ON COLUMN user_sessions_leads.last_rendered_image_url IS 'Gemini photorealistic montage result (base64 or URL)';

