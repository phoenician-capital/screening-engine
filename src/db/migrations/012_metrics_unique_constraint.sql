-- Migration 012: Add unique constraint on metrics(ticker, period_end, period_type)
-- Required for ON CONFLICT upserts in universe_expander.py

ALTER TABLE metrics
    ADD CONSTRAINT uq_metrics_ticker_period UNIQUE (ticker, period_end, period_type);
