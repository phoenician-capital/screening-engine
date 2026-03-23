-- ===================================================================
-- Migration 005: Portfolio Holdings
-- ===================================================================

CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker              VARCHAR(20) NOT NULL,
    name                VARCHAR(255),
    sector              VARCHAR(100),

    -- Position
    entry_price         NUMERIC,
    position_size_usd   NUMERIC,
    date_added          DATE,
    notes               TEXT,
    is_active           BOOLEAN DEFAULT TRUE,

    -- Snapshot metrics at entry (for candidate comparison)
    entry_gross_margin  NUMERIC,
    entry_roic          NUMERIC,
    entry_ev_ebit       NUMERIC,
    entry_revenue_growth NUMERIC,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_portfolio_ticker ON portfolio_holdings (ticker);
CREATE INDEX idx_portfolio_active ON portfolio_holdings (is_active);

-- Also add portfolio_comparison column to recommendations
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS portfolio_comparison JSONB;
