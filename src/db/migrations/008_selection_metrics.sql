-- ===================================================================
-- Migration 008: Add derived metrics for selection team
-- Buyback/FCF ratio, dilution rate, organic growth
-- ===================================================================

ALTER TABLE metrics
    ADD COLUMN IF NOT EXISTS buyback_to_fcf_ratio NUMERIC,
    ADD COLUMN IF NOT EXISTS stock_dilution_rate NUMERIC,
    ADD COLUMN IF NOT EXISTS organic_revenue_growth NUMERIC;

CREATE INDEX IF NOT EXISTS idx_metrics_buyback_fcf
  ON metrics(buyback_to_fcf_ratio);
