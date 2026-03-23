-- Migration 004: Production hardening
-- Add missing index + tighten numeric precision

-- Index on recommendations.scoring_run_id (missing, causes full table scans)
CREATE INDEX IF NOT EXISTS idx_recommendations_scoring_run
    ON recommendations (scoring_run_id);

-- Tighten numeric precision on metrics table
-- Revenue / cash flow / assets: up to 999 trillion, 2 decimal places
ALTER TABLE metrics
    ALTER COLUMN revenue              TYPE NUMERIC(20,2),
    ALTER COLUMN gross_profit         TYPE NUMERIC(20,2),
    ALTER COLUMN ebit                 TYPE NUMERIC(20,2),
    ALTER COLUMN net_income           TYPE NUMERIC(20,2),
    ALTER COLUMN fcf                  TYPE NUMERIC(20,2),
    ALTER COLUMN capex                TYPE NUMERIC(20,2),
    ALTER COLUMN net_debt             TYPE NUMERIC(20,2),
    ALTER COLUMN total_assets         TYPE NUMERIC(20,2),
    ALTER COLUMN market_cap_usd       TYPE NUMERIC(20,2),
    ALTER COLUMN shares_outstanding   TYPE NUMERIC(20,2),
    ALTER COLUMN avg_daily_volume     TYPE NUMERIC(20,2);

-- Ratios / margins: 6 decimal places is plenty
ALTER TABLE metrics
    ALTER COLUMN gross_margin                 TYPE NUMERIC(8,6),
    ALTER COLUMN ebit_margin                  TYPE NUMERIC(8,6),
    ALTER COLUMN fcf_yield                    TYPE NUMERIC(8,6),
    ALTER COLUMN capex_to_revenue             TYPE NUMERIC(8,6),
    ALTER COLUMN roic                         TYPE NUMERIC(8,6),
    ALTER COLUMN roe                          TYPE NUMERIC(8,6),
    ALTER COLUMN revenue_growth_yoy           TYPE NUMERIC(8,6),
    ALTER COLUMN revenue_growth_3yr_cagr      TYPE NUMERIC(8,6),
    ALTER COLUMN insider_ownership_pct        TYPE NUMERIC(8,6),
    ALTER COLUMN institutional_ownership_pct  TYPE NUMERIC(8,6);

-- Multiples: up to 9999.99
ALTER TABLE metrics
    ALTER COLUMN net_debt_ebitda  TYPE NUMERIC(8,2),
    ALTER COLUMN ev_ebit          TYPE NUMERIC(8,2),
    ALTER COLUMN ev_fcf           TYPE NUMERIC(8,2),
    ALTER COLUMN pe_ratio         TYPE NUMERIC(8,2);

-- recommendations.rank should not be null (always assigned)
-- Add NOT NULL with default 0 for existing rows
UPDATE recommendations SET rank = 0 WHERE rank IS NULL;
ALTER TABLE recommendations ALTER COLUMN rank SET NOT NULL;
ALTER TABLE recommendations ALTER COLUMN rank SET DEFAULT 0;
