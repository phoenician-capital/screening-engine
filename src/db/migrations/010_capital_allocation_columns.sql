-- ===================================================================
-- Migration 010: Add capital allocation columns to metrics table
-- stock_repurchased, stock_based_compensation, acquisitions_net
-- These columns exist in the ORM model but were never added to the schema
-- ===================================================================

ALTER TABLE metrics
    ADD COLUMN IF NOT EXISTS stock_repurchased        NUMERIC,
    ADD COLUMN IF NOT EXISTS stock_based_compensation NUMERIC,
    ADD COLUMN IF NOT EXISTS acquisitions_net         NUMERIC;
