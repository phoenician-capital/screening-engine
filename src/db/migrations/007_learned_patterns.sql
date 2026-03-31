-- ===================================================================
-- Migration 007: Learned Patterns for Selection & Scoring Teams
-- Adds tables for bidirectional feedback learning
-- ===================================================================

-- Selection Team Learned Patterns
CREATE TABLE IF NOT EXISTS selection_learned_patterns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pattern_type VARCHAR(50) NOT NULL,  -- "missed_red_flag", "miscalibration", "threshold_adjustment"
  agent_type VARCHAR(50) NOT NULL,    -- "filter", "business_model", "founder", "growth", "red_flag"
  metric_name VARCHAR(100),           -- "buyback_ratio", "apic_growth", "clarity_score", etc.
  old_threshold JSONB,                -- Previous threshold/condition
  new_threshold JSONB,                -- Updated threshold/condition
  triggered_by_feedback_id UUID REFERENCES feedback(id),
  analyst_action VARCHAR(20),         -- "research_now", "watch", "reject"
  confidence FLOAT DEFAULT 0.7,       -- How often does this pattern hold? 0-1
  applied_count INT DEFAULT 0,        -- Companies filtered by this rule
  validation_count INT DEFAULT 0,     -- Companies that validated this (analyst agreed)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP,               -- Auto-decay after 30 days
  metadata JSONB DEFAULT '{}'::jsonb  -- Additional context/reasoning
);

CREATE INDEX IF NOT EXISTS idx_selection_learned_metric_expires
  ON selection_learned_patterns(metric_name, expires_at);
CREATE INDEX IF NOT EXISTS idx_selection_learned_agent_type
  ON selection_learned_patterns(agent_type);
CREATE INDEX IF NOT EXISTS idx_selection_learned_feedback
  ON selection_learned_patterns(triggered_by_feedback_id);

-- Scoring Team Learned Patterns
CREATE TABLE IF NOT EXISTS scoring_learned_patterns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pattern_type VARCHAR(50) NOT NULL,  -- "risk_factor", "dimension_weight", "red_flag"
  dimension VARCHAR(50),              -- "capital_returns", "growth_quality", "valuation", etc.
  pattern_data JSONB NOT NULL,        -- Condition + action (e.g., {buyback_ratio_fcf: {threshold: 2.0, adjustment: -20}})
  triggered_by_feedback_id UUID REFERENCES feedback(id),
  analyst_action VARCHAR(20),         -- "research_now", "watch", "reject"
  confidence FLOAT DEFAULT 0.7,       -- Pattern confidence 0-1
  applied_count INT DEFAULT 0,        -- Times this pattern was applied
  validation_count INT DEFAULT 0,     -- Times analyst validated this pattern
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP,               -- Auto-decay after 30-60 days
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_scoring_learned_dimension_expires
  ON scoring_learned_patterns(dimension, expires_at);
CREATE INDEX IF NOT EXISTS idx_scoring_learned_pattern_type
  ON scoring_learned_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_scoring_learned_feedback
  ON scoring_learned_patterns(triggered_by_feedback_id);

-- Selection Team Agent Decisions (for tracking what each selection agent decided)
CREATE TABLE IF NOT EXISTS selection_agent_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_ticker VARCHAR(20) NOT NULL,
  agent_type VARCHAR(50) NOT NULL,    -- "filter", "business_model", "founder", "growth", "red_flag"
  passed_filter BOOLEAN NOT NULL,     -- Did company pass this agent's filter?
  score FLOAT,                        -- Optional: agent-specific score
  reason TEXT,                        -- Why did it pass or fail?
  decision_data JSONB,                -- Agent's full decision output
  screening_run_id UUID,              -- Link to screening run
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_selection_agent_ticker_agent
  ON selection_agent_decisions(company_ticker, agent_type);
CREATE INDEX IF NOT EXISTS idx_selection_agent_run
  ON selection_agent_decisions(screening_run_id);

-- Scoring Team Agent Decisions (similar tracking for scoring agents)
CREATE TABLE IF NOT EXISTS scoring_agent_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_ticker VARCHAR(20) NOT NULL,
  agent_type VARCHAR(50) NOT NULL,    -- "researcher", "scorer", "critic", "memo"
  decision_data JSONB NOT NULL,       -- Agent's output (scores, findings, memo, etc.)
  was_correct BOOLEAN,                -- Did analyst agree with agent?
  screening_run_id UUID,              -- Link to screening run
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scoring_agent_ticker
  ON scoring_agent_decisions(company_ticker);
CREATE INDEX IF NOT EXISTS idx_scoring_agent_run
  ON scoring_agent_decisions(screening_run_id);
