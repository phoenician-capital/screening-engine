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
