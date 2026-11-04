-- Migration 007: Phase 3 - Previous Montage State & Undo Protection
-- Adds previous_montage_state column to user_sessions_leads to preserve montage history on dispenser change

ALTER TABLE user_sessions_leads
ADD COLUMN IF NOT EXISTS previous_montage_state JSONB DEFAULT NULL;

COMMENT ON COLUMN user_sessions_leads.previous_montage_state IS 'Archived state of the previous AI montage (selected_sku, bundle, image URLs, caption) for zero-token undo rollback';
