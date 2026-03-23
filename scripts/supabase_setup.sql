-- Supabase setup: pgvector + all migrations
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- === Phoenician ===
-- ===================================================================
-- Phoenician Capital – Screening Engine – Initial Schema
-- Run: psql -d phoenician -f 001_initial_schema.sql
-- ===================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ── Companies ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS companies (
    ticker              VARCHAR(20)     PRIMARY KEY,
    name                VARCHAR(255)    NOT NULL,
    exchange            VARCHAR(50),
    country             VARCHAR(100),
    gics_sector         VARCHAR(10),
    gics_industry_group VARCHAR(10),
    gics_industry       VARCHAR(10),
    gics_sub_industry   VARCHAR(20),
    market_cap_usd      NUMERIC,
    description         VARCHAR(2000),
    website             VARCHAR(500),
    cik                 VARCHAR(20),
    is_founder_led      BOOLEAN,
    founder_name        VARCHAR(255),
    is_active           BOOLEAN         DEFAULT TRUE,
    created_at          TIMESTAMPTZ     DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX idx_companies_sector ON companies (gics_sector);
CREATE INDEX idx_companies_market_cap ON companies (market_cap_usd);

-- ── Metrics (time-series) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS metrics (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker                      VARCHAR(20) REFERENCES companies(ticker),
    period_end                  DATE NOT NULL,
    period_type                 VARCHAR(10) NOT NULL,

    revenue                     NUMERIC,
    gross_profit                NUMERIC,
    gross_margin                NUMERIC,
    ebit                        NUMERIC,
    ebit_margin                 NUMERIC,
    net_income                  NUMERIC,

    fcf                         NUMERIC,
    fcf_yield                   NUMERIC,
    capex                       NUMERIC,
    capex_to_revenue            NUMERIC,

    net_debt                    NUMERIC,
    net_debt_ebitda             NUMERIC,
    total_assets                NUMERIC,

    roic                        NUMERIC,
    roe                         NUMERIC,

    revenue_growth_yoy          NUMERIC,
    revenue_growth_3yr_cagr     NUMERIC,

    ev_ebit                     NUMERIC,
    ev_fcf                      NUMERIC,
    pe_ratio                    NUMERIC,

    insider_ownership_pct       NUMERIC,
    institutional_ownership_pct NUMERIC,
    analyst_count               INTEGER,

    market_cap_usd              NUMERIC,
    avg_daily_volume            NUMERIC,
    shares_outstanding          NUMERIC,

    created_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_metrics_ticker ON metrics (ticker);
CREATE INDEX idx_metrics_period ON metrics (ticker, period_end DESC);

-- ── Documents ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker          VARCHAR(20) REFERENCES companies(ticker),
    doc_type        VARCHAR(50) NOT NULL,
    source          VARCHAR(100),
    source_url      TEXT,
    accession_no    VARCHAR(50),
    title           VARCHAR(500),
    raw_text        TEXT,
    published_at    TIMESTAMPTZ,
    ingested_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_ticker ON documents (ticker);
CREATE INDEX idx_documents_type ON documents (doc_type);

-- ── Embeddings (vector store) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS embeddings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doc_id          UUID REFERENCES documents(id),
    ticker          VARCHAR(20),
    chunk_text      TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL,
    embedding       vector(1536),
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_embeddings_doc ON embeddings (doc_id);
CREATE INDEX idx_embeddings_ticker ON embeddings (ticker);
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ── Scoring Runs ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scoring_runs (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_type                VARCHAR(20) NOT NULL,
    tickers_scored          INTEGER DEFAULT 0,
    tickers_passed_filter   INTEGER DEFAULT 0,
    config_snapshot         JSONB,
    run_at                  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Recommendations ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recommendations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker          VARCHAR(20) REFERENCES companies(ticker),
    scoring_run_id  UUID REFERENCES scoring_runs(id),
    fit_score       NUMERIC NOT NULL,
    risk_score      NUMERIC NOT NULL,
    rank_score      NUMERIC NOT NULL,
    rank            INTEGER,
    memo_text       TEXT,
    citations       JSONB,
    scoring_detail  JSONB,
    status          VARCHAR(20) DEFAULT 'pending',
    generated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_recommendations_ticker ON recommendations (ticker);
CREATE INDEX idx_recommendations_status ON recommendations (status);
CREATE INDEX idx_recommendations_rank ON recommendations (rank);

-- ── Feedback ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS feedback (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recommendation_id   UUID REFERENCES recommendations(id),
    ticker              VARCHAR(20),
    analyst_id          VARCHAR(100),
    action              VARCHAR(20) NOT NULL,
    reject_reason       VARCHAR(100),
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_feedback_ticker ON feedback (ticker);
CREATE INDEX idx_feedback_action ON feedback (action);

-- ── Watchlist ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchlist (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker              VARCHAR(20) REFERENCES companies(ticker),
    analyst_id          VARCHAR(100),
    trigger_condition   TEXT,
    added_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_watchlist_ticker ON watchlist (ticker);

-- ── Exclusions ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exclusions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker          VARCHAR(20) UNIQUE,
    reason          VARCHAR(200) NOT NULL,
    analyst_id      VARCHAR(100),
    notes           TEXT,
    excluded_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_exclusions_ticker ON exclusions (ticker);

-- === Phoenician ===
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

-- === Phoenician ===
-- Migration 003: widen sector/industry columns to hold full FMP text values
ALTER TABLE companies
    ALTER COLUMN gics_sector          TYPE VARCHAR(100),
    ALTER COLUMN gics_industry_group  TYPE VARCHAR(100),
    ALTER COLUMN gics_industry        TYPE VARCHAR(100),
    ALTER COLUMN gics_sub_industry    TYPE VARCHAR(100);

-- === Phoenician ===
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

-- recommendations.rank — keep nullable (assigned after scoring)
ALTER TABLE recommendations ALTER COLUMN rank DROP NOT NULL;

-- === Phoenician ===
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

-- === Phoenician ===
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
