-- Migration 014: add persistent screen numbers to scoring runs.
-- This supports historical run selection in the frontend.

ALTER TABLE scoring_runs
    ADD COLUMN IF NOT EXISTS screen_number INTEGER;

WITH ordered_runs AS (
    SELECT
        id,
        ROW_NUMBER() OVER (ORDER BY run_at ASC, id ASC) AS rn
    FROM scoring_runs
)
UPDATE scoring_runs sr
SET screen_number = ordered_runs.rn
FROM ordered_runs
WHERE sr.id = ordered_runs.id
  AND sr.screen_number IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_scoring_runs_screen_number
    ON scoring_runs (screen_number)
    WHERE screen_number IS NOT NULL;
