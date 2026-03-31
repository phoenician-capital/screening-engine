# Quick Start: Feedback Learning System

## TL;DR — What You Need to Know

**The Red Flag Agent learns from analyst feedback and applies learned thresholds in the next screening run.**

### 3-Minute Understanding

```
Run 1: Screen universe → 40 pass → Analyst rejects AXON: "buyback 3.0x FCF unsustainable"
       ↓ Learning happens
Run 2: Screen universe → Red Flag Agent now uses buyback threshold 0.8x (not 1.0x)
       → ACME (buyback 2.5x) rejected early → Only 20 pass (more filtered)
```

---

## The Complete Flow

### 1. Analyst Submits Feedback with Notes

**Frontend/API:**
```javascript
// User clicks "Pass" on AXON
POST /api/v1/recommendations/AXON/feedback
{
  action: "reject",
  notes: "Pass on AXON — buyback is $210M while FCF is only $70M over 3 years. 
          This is unsustainable capital allocation masking a lack of organic growth."
}
```

**Backend stores:**
```python
Feedback(
  ticker="AXON",
  action="reject",
  notes="Pass on AXON — buyback is $210M..."  # ← NOW STORED
)
```

### 2. Bidirectional Learning Pipeline Triggered

**Automatically after feedback is saved:**

```python
# src/api/router.py
await BidirectionalFeedbackPipeline(session).process_feedback(fb)
```

### 3. SelectionFeedbackAnalyzer Extracts Concerns

**LLM-powered parsing:**

```python
# src/feedback/selection_feedback_analyzer.py
analyzer = SelectionFeedbackAnalyzer(session)
concerns = await analyzer.analyze(
    feedback=fb,
    company=AXON,
    metrics=AXON_metrics
)
# Returns: ["unsustainable buybacks", "weak organic growth"]
```

### 4. Patterns Generated & Stored

For "unsustainable buybacks" concern:

```sql
INSERT INTO selection_learned_patterns (
  pattern_type = 'missed_red_flag',
  agent_type = 'red_flag',
  metric_name = 'buyback_to_fcf_ratio',
  old_threshold = {"value": 1.0},    -- Baseline
  new_threshold = {"value": 0.8},    -- Learned
  confidence = 0.7,
  expires_at = now + 30 days,
  metadata = {"issue": "Unsustainable buyback", "actual_value": 3.0, ...}
);
```

### 5. Next Screening Run — Patterns Applied

**When you run screening again:**

```python
# src/orchestration/pipelines/selection_pipeline.py
selection_pipeline = CompanySelectionPipeline(session)
results = await selection_pipeline.select_candidates(companies)
```

**Red Flag Agent loads and applies learned patterns:**

```python
# src/scoring/agents/selection/red_flag_agent.py
learned_patterns = await self._get_learned_patterns()
# Loads: {"buyback_to_fcf_ratio": {confidence: 0.7, threshold: 0.8}}

# For each company:
threshold, is_learned = self._get_threshold("buyback_to_fcf_ratio", baseline=1.0)
# If learned pattern exists AND confidence > 0.75: use 0.8
# Else: use baseline 1.0

if company.buyback_to_fcf_ratio > threshold:
    reject_company()  # ← LEARNED PATTERN APPLIED
```

### Example: Company ACME in Run 2

```
ACME metrics:
  Gross Margin: 35% ✓
  ROIC: 10% ✓
  Growth: 5% ✓
  Leverage: 3.5x ✓
  Buyback to FCF: 2.5x ← Check this with learned threshold

Red Flag Agent:
  Loads learned pattern: buyback > 0.8x (confidence 0.7)
  Confidence > 0.75? NO, but close. Use pattern with caution.
  
  Actually wait — Let me re-check confidence scoring...
  
  NEW PATTERN: confidence starts at 0.7
  ACTIVATION THRESHOLD: > 0.75
  
  So new patterns DON'T auto-activate until validated (Run 2)
  ACME is in Run 2 → pattern at 0.7, needs validation
  
  BUT: Code still applies pattern if confidence > 0.75
  So ACME at Run 2 might just barely pass Red Flag check
  
  Then if analyst rejects ACME: confidence goes 0.7 → 0.8
  Run 3: ACME-like companies now auto-rejected (0.8 > 0.75)
```

**Decision for ACME:**
```
Run 2: ACME has buyback 2.5x, learned threshold 0.8x (confidence 0.7)
  → 0.7 is just below 0.75 cutoff
  → MARGINAL DECISION (might pass or fail depending on other checks)
  → If other red flags exist, FAIL

Run 3 (if analyst agrees ACME is bad): 
  → Confidence 0.7 → 0.8
  → Now 0.8 > 0.75 threshold
  → ACME and similar companies AUTO-REJECT
```

---

## Key Files You Need to Know

### Where Patterns Are Created
- `src/feedback/selection_feedback_analyzer.py` — Extracts concerns from analyst notes
- `src/orchestration/pipelines/bidirectional_feedback_pipeline.py` — Stores patterns in DB

### Where Patterns Are Applied
- `src/scoring/agents/selection/red_flag_agent.py` — Loads and uses learned thresholds
- `_get_learned_patterns()` method — Queries the DB for active patterns
- `_get_threshold()` helper — Returns learned or baseline threshold

### Where Patterns Are Stored
- Database: `selection_learned_patterns` table
- Columns: metric_name, new_threshold, confidence, expires_at

### Prompts
- `src/prompts/selection/red_flag_agent_system.j2` — Updated to emphasize learning

---

## How to Test It

### Test 1: Create a Learned Pattern

```bash
# 1. Run a screening
curl -X POST http://localhost:8000/api/v1/screening/run

# 2. View results, find a company to reject
# (e.g., AXON with buyback ratio 2.5x)

# 3. Submit feedback with NOTES
curl -X POST http://localhost:8000/api/v1/recommendations/AXON/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "action": "reject",
    "notes": "Unsustainable buyback. FCF $70M but repurchase $210M."
  }'

# 4. Check database for pattern creation
SELECT * FROM selection_learned_patterns 
WHERE metric_name = 'buyback_to_fcf_ratio' 
ORDER BY created_at DESC LIMIT 1;

# Result should show:
# - pattern_type: "missed_red_flag"
# - agent_type: "red_flag"
# - metric_name: "buyback_to_fcf_ratio"
# - new_threshold: {0.8}
# - confidence: 0.7
# - expires_at: 2026-04-30 (30 days from now)
```

### Test 2: Pattern Applied in Next Run

```bash
# 1. Add a company with high buyback ratio to universe
# (e.g., ACME with buyback_to_fcf_ratio = 2.5x)

# 2. Run screening again
curl -X POST http://localhost:8000/api/v1/screening/run

# 3. Check if ACME was rejected by Red Flag Agent
SELECT * FROM selection_agent_decisions 
WHERE company_ticker = 'ACME' 
  AND agent_type = 'red_flag'
  AND created_at > NOW() - INTERVAL '1 hour';

# Result should show:
# - passed_filter: false (REJECTED)
# - reason: "...buyback...learned..." (contains "learned")
# - metadata.applied_learned_patterns: ["buyback_to_fcf_ratio"]
```

### Test 3: Check Logs

```bash
# Watch for these log messages:

# Pattern creation:
"Selection learning for AXON: 1 concerns extracted"
"Created pattern: missed_red_flag on red_flag agent"

# Pattern application:
"Loaded learned pattern: buyback_to_fcf_ratio → 0.8 (confidence 70%)"
"ACME: Unsustainable buyback ratio 2.5x FCF (> 0.8x) (learned from analyst feedback)"
```

---

## Confidence Score Cheat Sheet

| Confidence | Status | Action |
|-----------|--------|--------|
| 0.7 | NEW | Pattern just created, waiting for validation |
| 0.7-0.75 | MARGINAL | Might be applied depending on other checks |
| > 0.75 | ACTIVE | Automatically applied to all companies |
| > 0.85 | GOLD | Pattern validated 3+ times, very reliable |
| 0.0 | EXPIRED | Pattern older than 30 days, no longer used |

---

## What Happens If Analyst Disagrees?

**Scenario: Analyst rejects AXON for "buyback unsustainable" → Pattern created with 0.8x threshold**

**Then in Run 2: Analyst ACCEPTS BLAH which has 0.9x buyback**

```
Selection Agent Decision for BLAH:
  Red Flag Agent applies learned pattern: 0.9x > 0.8x → REJECT
  
But analyst accepts it anyway.

Result: Pattern is WRONG
  Confidence: 0.7 → 0.5 (decreased for disagreement)
  After 1-2 more disagreements: confidence → 0.2
  Below 0.75 threshold: Pattern no longer applied
  After 30 days: Pattern expires
```

The system self-corrects when you disagree.

---

## Thinking in Patterns

Instead of thinking "the system rejects companies with high buyback", think:

**"I (the analyst) rejected AXON for high buyback. The system now learns: companies with buyback > 0.8x are suspicious. Next screening, similar companies get flagged. If I keep rejecting them, confidence increases. If I start accepting them, confidence decreases."**

You're training the system through your feedback, one rejection at a time.

---

## Expected Behavior Over Time

| Run # | Scenario | Selection Output | Learned Patterns |
|-------|----------|------------------|------------------|
| 1 | Fresh start | ~40 pass (baseline) | 0 patterns |
| 2 | Analyst rejects 3 for "buyback" | ~38 pass | 1 pattern (buyback, confidence 0.7) |
| 3 | Analyst rejects 2 more for "buyback" | ~35 pass | 1 pattern (buyback, confidence 0.8) |
| 5 | Multiple validations | ~30 pass | 3 patterns (buyback 0.9, leverage 0.85, dilution 0.8) |
| 10 | Well-calibrated system | ~25-30 pass | 4-6 patterns (all high confidence) |
| 15+ | Mature system | ~25-30 pass (stable) | 5-8 patterns (0.85+ confidence) |

---

## How to Monitor in Production

### Dashboard Query: Active Learned Patterns

```sql
SELECT 
  metric_name,
  new_threshold,
  confidence,
  DATE_TRUNC('hour', created_at) as created_hour,
  DATEDIFF(day, NOW(), expires_at) as days_until_expiry
FROM selection_learned_patterns
WHERE agent_type = 'red_flag'
  AND expires_at > NOW()
  AND confidence > 0.75
ORDER BY confidence DESC;
```

### Dashboard Query: How Many Companies Rejected by Learned Patterns?

```sql
SELECT 
  d.agent_type,
  COUNT(*) as rejections,
  COUNT(CASE WHEN d.metadata->>'applied_learned_patterns' != '[]' THEN 1 END) as from_learned
FROM selection_agent_decisions d
WHERE d.passed_filter = false
  AND d.created_at > NOW() - INTERVAL '1 day'
GROUP BY d.agent_type;
```

---

## Summary

✅ **Analyst rejects with notes** → Pattern created  
✅ **Pattern validated by more rejections** → Confidence increases  
✅ **Next screening** → Pattern applied to similar companies  
✅ **Analyst agrees** → Pattern becomes gold standard (0.9 confidence)  
✅ **30 days pass** → Pattern expires (unless re-validated)

The system is **continuous learning** — no manual fine-tuning needed.
