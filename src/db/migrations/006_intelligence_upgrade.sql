-- ===================================================================
-- Migration 006: Intelligence Upgrade
-- Adds meta column to documents, IR URLs to portfolio, inspired_by
-- to recommendations, and 52-week low fields to insider_purchases.
-- ===================================================================

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS meta JSONB;

ALTER TABLE portfolio_holdings
    ADD COLUMN IF NOT EXISTS ir_url TEXT,
    ADD COLUMN IF NOT EXISTS events_url TEXT;

ALTER TABLE recommendations
    ADD COLUMN IF NOT EXISTS inspired_by VARCHAR(20);

ALTER TABLE insider_purchases
    ADD COLUMN IF NOT EXISTS near_52wk_low BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS cluster_window_days INTEGER;

CREATE INDEX IF NOT EXISTS idx_documents_meta ON documents USING gin(meta);
CREATE INDEX IF NOT EXISTS idx_recommendations_inspired_by ON recommendations (inspired_by);
