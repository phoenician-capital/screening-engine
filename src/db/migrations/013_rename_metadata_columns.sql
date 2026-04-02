-- ===================================================================
-- Migration 013: Rename 'metadata' → 'pattern_metadata' in learned patterns tables
-- The SQLAlchemy models use pattern_metadata but the tables were created with 'metadata'
-- ===================================================================

-- selection_learned_patterns
ALTER TABLE selection_learned_patterns
  RENAME COLUMN metadata TO pattern_metadata;

-- scoring_learned_patterns
ALTER TABLE scoring_learned_patterns
  RENAME COLUMN metadata TO pattern_metadata;
