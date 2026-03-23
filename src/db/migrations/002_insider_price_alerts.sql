-- ===================================================================
-- Phoenician Capital – Migration 002: Insider Purchases + Price Alerts
-- Run: psql -d phoenician -f 002_insider_price_alerts.sql
-- ===================================================================

-- ── Insider Purchases (from SEC Form 4) ─────────────────────────
CREATE TABLE IF NOT EXISTS insider_purchases (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker              VARCHAR(20) REFERENCES companies(ticker),
    insider_name        VARCHAR(255) NOT NULL,
    insider_title       VARCHAR(100),               -- CEO | CFO | Director | etc.
    shares              INTEGER,
    price_per_share     NUMERIC,
    total_value         NUMERIC,
    transaction_date    DATE NOT NULL,
    form4_url           TEXT,
    is_open_market      BOOLEAN DEFAULT TRUE,        -- exclude option exercises
    conviction_score    NUMERIC,                    -- 0–100 computed at ingest
    is_cluster          BOOLEAN DEFAULT FALSE,       -- 2+ insiders within 14 days
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_insider_ticker   ON insider_purchases (ticker);
CREATE INDEX idx_insider_date     ON insider_purchases (transaction_date DESC);
CREATE INDEX idx_insider_cluster  ON insider_purchases (is_cluster) WHERE is_cluster = TRUE;

-- ── Price Alerts (analyst-set price targets) ─────────────────────
CREATE TABLE IF NOT EXISTS price_alerts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker              VARCHAR(20) REFERENCES companies(ticker),
    target_price        NUMERIC NOT NULL,
    notes               TEXT,
    expires_at          DATE,
    status              VARCHAR(20) NOT NULL DEFAULT 'active',  -- active | triggered | dismissed | expired
    triggered_at        TIMESTAMPTZ,
    triggered_price     NUMERIC,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_price_alerts_ticker  ON price_alerts (ticker);
CREATE INDEX idx_price_alerts_status  ON price_alerts (status);
