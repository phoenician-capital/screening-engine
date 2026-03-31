# Feedback Learning Guide — How the Red Flag Agent Learns

## Overview

The Red Flag Agent is special. Unlike the other 4 selection agents with fixed rules, **the Red Flag Agent adapts and learns from every analyst rejection**.

This document explains the complete feedback loop from analyst feedback → learning → next screening run.

---

## The Learning Loop: 5 Steps

### Step 1: Analyst Rejects Company with Feedback

**Example: Run 1, Company: AXON**

```
User submits feedback:
{
  action: "reject",
  notes: "Pass on AXON — FCF is $70M over 3 years but buyback is $210M.
          Unsustainable capital allocation. Also unclear what they do exactly —
          conglomerate-like structure."
}
```

### Step 2: SelectionFeedbackAnalyzer Extracts Concerns

**File:** `src/feedback/selection_feedback_analyzer.py`

```python
analyzer = SelectionFeedbackAnalyzer(session)
concerns = await analyzer.analyze(
    feedback=feedback,
    company=axon_company,
    metrics=axon_metrics,
)
```

**What gets extracted:**
```
concerns = [
  "Unsustainable buybacks",
  "Unclear business model / conglomerate"
]
```

**LLM Processing:**
The analyzer uses Claude to parse notes and extract 2-3 bullet-point concerns from free-text feedback. This is language-aware, not regex-based.

### Step 3: Learning Patterns Generated & Stored

**File:** `src/db/models/learned_patterns.py`

For each concern, a pattern is created:

```python
# Pattern 1: Buyback concern
selection_learned_pattern_1 = SelectionLearnedPattern(
    pattern_type="missed_red_flag",
    agent_type="red_flag",
    metric_name="buyback_to_fcf_ratio",
    old_threshold={"value": 1.0},  # Baseline
    new_threshold={"value": 0.8},  # Suggested learning
    triggered_by_feedback_id=feedback.id,
    analyst_action="reject",
    confidence=0.7,  # New pattern starts here
    expires_at=now + 30 days,  # Auto-decay
    metadata={
        "issue": "Unsustainable buyback ratio not caught",
        "company_ticker": "AXON",
        "actual_value": 3.0,  # AXON's actual buyback_to_fcf_ratio
        "severity": "high"
    }
)
session.add(selection_learned_pattern_1)

# Pattern 2: Business model concern
selection_learned_pattern_2 = SelectionLearnedPattern(
    pattern_type="miscalibration",
    agent_type="business_model",
    metric_name=None,
    triggered_by_feedback_id=feedback.id,
    analyst_action="reject",
    confidence=0.7,
    expires_at=now + 30 days,
    metadata={
        "issue": "Business marked as clear when analyst found it unclear",
        "company_ticker": "AXON",
        "reason": "Conglomerate-like structure"
    }
)
session.add(selection_learned_pattern_2)
```

**Database Result:**
```sql
SELECT * FROM selection_learned_patterns 
WHERE ticker = 'AXON' AND created_at > now - interval '5 minutes';

id | pattern_type | agent_type | metric_name | old_threshold | new_threshold | confidence | expires_at | metadata
---|--------------|------------|-------------|---------------|---------------|------------|-----------|----------
1  | missed_red_flag | red_flag | buyback_to_fcf_ratio | {1.0} | {0.8} | 0.7 | 2026-04-30 | {...}
2  | miscalibration | business_model | NULL | NULL | NULL | 0.7 | 2026-04-30 | {...}
```

### Step 4: Next Screening Run — Patterns Applied

**Run 2 starts. Universe includes ACME (similar to AXON):**

```
Company: ACME
- Buyback to FCF ratio: 2.5x
- Conglomerate structure with unclear core business
- Other metrics: OK
```

**Selection Pipeline evaluates ACME:**

```python
# 1. Filter Agent: PASS (metrics OK)
# 2. Business Model Agent: PASS (initially unclear, but passes)
# 3. Founder Agent: PASS (sufficient insider ownership)
# 4. Growth Agent: PASS (organic growth present)
# 5. Red Flag Agent: Loads learned patterns
```

**Red Flag Agent Execution:**

```python
class RedFlagAgent:
    async def evaluate(self, ticker="ACME", buyback_to_fcf_ratio=2.5, ...):
        
        # STEP A: Load learned patterns
        learned_patterns = await self._get_learned_patterns()
        # Returns: {
        #   "buyback_to_fcf_ratio": {
        #     "confidence": 0.7,
        #     "suggested_threshold": 0.8,  # Learned from feedback
        #     "original_threshold": 1.0
        #   }
        # }
        
        # STEP B: For each metric, get dynamic threshold
        threshold, is_learned = self._get_threshold(
            "buyback_to_fcf_ratio",
            baseline=1.0  # Original static threshold
        )
        # Returns: (0.8, True)  # Use learned threshold, it's from feedback
        
        # STEP C: Check if company exceeds learned threshold
        if buyback_to_fcf_ratio > threshold:  # 2.5 > 0.8? YES
            flags.append(
                f"Unsustainable buyback ratio 2.5x FCF "
                f"(> 0.8x) (learned from analyst feedback)"
            )
        
        # ACME FAILS at Red Flag Agent
        passed = False
        return AgentDecision(
            passed=False,
            reason="Unsustainable buyback ratio 2.5x FCF (> 0.8x) (learned from analyst feedback)",
            metadata={
                "applied_learned_patterns": ["buyback_to_fcf_ratio"],
                "learned_pattern_count": 1
            }
        )
```

**Result:**
```
✗ ACME REJECTED at Selection stage
  Reason: Red Flag Agent caught unsustainable buyback (learned from AXON feedback)
  Log: "learned_pattern_count": 1, "applied_learned_patterns": ["buyback_to_fcf_ratio"]
```

### Step 5: Pattern Validation & Confidence Update

If analyst later reviews ACME:
- **Confirms rejection** ("Yes, bad buyback ratio"): Pattern confidence 0.7 → 0.8
- **Accepts despite buyback** ("Pattern is wrong"): Confidence 0.7 → 0.5
- **Doesn't review ACME** (Pattern assumed correct)

After pattern reaches 0.9+ confidence:
- It becomes "gold standard" for that metric
- Automatically applies every run
- Becomes part of institutional knowledge

---

## Threshold Learning: Progression

**Baseline (Static):**
```
Buyback to FCF ratio > 1.0x = RED FLAG
```

**After Analyst Feedback (Run 1):**
```
Analyst rejects AXON: "buyback 3.0x FCF is unsustainable"
Learned: Buyback > 0.8x FCF = RED FLAG
Confidence: 0.7 (new pattern, not yet validated)
```

**After Validation (Run 3):**
```
Analyst rejects BLAH: "buyback 1.5x FCF is too much"
Same pattern triggered → Confidence: 0.7 → 0.8
```

**After Strong Validation (Run 7):**
```
Analyst rejects CHARLIE: "buyback 2.0x FCF unsustainable"
Same pattern triggered → Confidence: 0.8 → 0.9
Now this is HIGH CONFIDENCE. Auto-rejects companies > 0.8x
```

**After 30 Days (Pattern Expires):**
```
Pattern expires_at = now + 30 days
If analyst hasn't re-validated, pattern drops from active checks
Reverts to baseline: > 1.0x = RED FLAG
(This prevents permanent over-learning from single outlier rejection)
```

---

## Dynamic Threshold Logic in Code

Here's exactly how the Red Flag Agent applies learned thresholds:

```python
async def evaluate(self, ticker: str, buyback_to_fcf_ratio: float | None = None, ...):
    
    # Load all learned patterns for this run
    learned_patterns = await self._get_learned_patterns()
    # Result: {
    #   "buyback_to_fcf_ratio": {confidence: 0.8, suggested_threshold: 0.8},
    #   "leverage": {confidence: 0.9, suggested_threshold: 3.5},
    #   ...
    # }
    
    # Helper function: Get active threshold
    def _get_threshold(metric_name, baseline):
        if metric_name in learned_patterns:
            pattern = learned_patterns[metric_name]
            # ONLY use learned threshold if confidence > 0.75
            if pattern["confidence"] > 0.75:
                return pattern["suggested_threshold"], is_learned=True
        return baseline, is_learned=False
    
    # Check buyback
    threshold, is_learned = _get_threshold("buyback_to_fcf_ratio", 1.0)
    if buyback_to_fcf_ratio > threshold:
        if is_learned:
            reason = f"...Learned from analyst feedback"
        else:
            reason = f"...Baseline check"
        flags.append(reason)
    
    # Check leverage
    threshold, is_learned = _get_threshold("net_debt_ebitda", 5.0)
    if net_debt_ebitda > threshold:
        flags.append(...)
    
    # ... similar for other metrics
    
    return AgentDecision(passed=len(flags)==0, reason=" | ".join(flags))
```

---

## Complete Example: Multi-Run Learning

### Run 1: Initial Screening
```
Universe: 1000 companies

Selection Pipeline:
- Filter: 1000 → 900
- Business Model: 900 → 850
- Founder: 850 → 500
- Growth: 500 → 100
- Red Flag (baseline thresholds): 100 → 40

Sent to Scoring: 40 companies

Analyst feedback: Rejects AXON
  "Buyback 3.0x FCF unsustainable"
  → Pattern created: {buyback_to_fcf_ratio: 0.8x, confidence: 0.7}
```

### Run 2: Patterns Active
```
Universe: 1000 companies

Red Flag Agent (now with learned pattern):
- Loads: buyback_to_fcf_ratio > 0.8x = flag (confidence 0.7)
- Checks: 100 candidates
  - ACME: buyback 2.5x > 0.8x → REJECT
  - BLAH: buyback 1.5x > 0.8x → REJECT
  - CHARLIE: buyback 0.6x < 0.8x → OK
  - ... (similar checks for other metrics)
- Result: 20 candidates (vs 40 in Run 1)

Analyst feedback: Rejects BLAH
  "Yes, buyback 1.5x is too much"
  → SAME pattern validated: confidence 0.7 → 0.8
```

### Run 3-5: Pattern Becomes Gold Standard
```
By Run 5: Pattern confidence 0.9+ (validated 3+ times)
- Auto-rejects all companies with buyback > 0.8x
- Analyst comments: "Good, you're catching these earlier"
- Selection output: 25-30 companies (highly filtered)
```

### Run 6+: Mature System
```
- Selection team highly optimized
- Most rejected companies have clear reasons
- Analyst feedback is validation ("correct!") not correction ("too strict")
- Both teams calibrated to Phoenician's actual standards
```

---

## Confidence Scoring: The Math

Each learned pattern starts with confidence = **0.7** (baseline trust in analyst)

**Confidence Progression:**

| Event | Confidence Change | Reasoning |
|-------|-------------------|-----------|
| Pattern created from feedback | 0.7 | Baseline: analyst said it, believe them |
| Analyst reviews similar company, agrees | +0.1 | Pattern validated once |
| Analyst reviews another similar, agrees | +0.1 | Pattern validated twice |
| Analyst reviews similar company, disagrees | -0.2 | Pattern wrong, we over-corrected |
| Pattern expires (30 days, not re-validated) | → 0.0 | Market changed, forget it |

**Confidence Threshold for Activation:**

```
confidence > 0.75: Use learned threshold (high-confidence pattern)
0.6 < confidence ≤ 0.75: Use learned threshold but log as "marginal"
confidence ≤ 0.6: Ignore (not validated enough yet)
```

---

## Monitoring Learned Patterns

### Check Which Patterns Are Active

```sql
-- All active learned patterns for red flag agent
SELECT metric_name, confidence, new_threshold, created_at
FROM selection_learned_patterns
WHERE agent_type = 'red_flag'
  AND expires_at > NOW()
  AND confidence > 0.75
ORDER BY confidence DESC;

-- Result:
metric_name | confidence | new_threshold | created_at
buyback_to_fcf_ratio | 0.90 | {0.8} | 2026-03-20
net_debt_ebitda | 0.85 | {3.5} | 2026-03-18
stock_dilution_rate | 0.80 | {0.015} | 2026-03-15
```

### Check Pattern Applications

```sql
-- How many times each pattern was applied in latest run
SELECT applied_learned_patterns, COUNT(*) as rejected_count
FROM selection_agent_decisions
WHERE agent_type = 'red_flag'
  AND passed_filter = false
  AND created_at > NOW() - INTERVAL '1 day'
GROUP BY applied_learned_patterns;

-- Result:
applied_learned_patterns | rejected_count
{buyback_to_fcf_ratio} | 5
{net_debt_ebitda} | 3
{buyback_to_fcf_ratio, net_debt_ebitda} | 2
{} | 30  -- Static baseline checks only
```

### Check Pattern Effectiveness

```sql
-- Pattern effectiveness: was pattern correct?
SELECT 
  metric_name,
  COUNT(*) as applications,
  SUM(CASE WHEN analyst_agreed THEN 1 ELSE 0 END) as agreed_count,
  ROUND(100.0 * SUM(CASE WHEN analyst_agreed THEN 1 ELSE 0 END) / COUNT(*), 1) as agreement_pct
FROM selection_learned_patterns p
LEFT JOIN recommendations r ON r.id IN (
  SELECT recommendation_id FROM feedback 
  WHERE notes LIKE CONCAT('%', p.metadata->>'issue', '%')
)
WHERE p.agent_type = 'red_flag'
  AND p.expires_at > NOW()
GROUP BY metric_name;
```

---

## Logs: What to Look For

### When Patterns Are Applied

```
2026-03-31 14:22:45 [DEBUG] Loaded learned pattern: 
  buyback_to_fcf_ratio → 0.8 (confidence 90%)

2026-03-31 14:22:46 [INFO] ACME: Red Flag Agent
  Unsustainable buyback ratio 2.5x FCF (> 0.8x) (learned from analyst feedback)
  Applied patterns: ["buyback_to_fcf_ratio"]

2026-03-31 14:22:47 [INFO] Selection learning for ACME: 
  ✗ REJECTED at red_flag agent
  Learned patterns applied: 1
```

### When Patterns Are Created

```
2026-03-30 10:15:22 [INFO] Processing feedback for AXON: 
  action=reject, notes provided

2026-03-30 10:15:23 [INFO] Selection learning for AXON: 
  1 concerns extracted (LLM-based)
  - "Unsustainable buyback ratio"

2026-03-30 10:15:24 [INFO] Bidirectional learning triggered:
  Created pattern: missed_red_flag on red_flag agent
  Created pattern: miscalibration on business_model agent

2026-03-30 10:15:25 [INFO] Feedback processing complete for AXON:
  Learned patterns stored, expire in 30 days
```

---

## FAQ: Learning Behavior

### Q: How quickly do patterns activate?

**A:** After 1st analyst rejection → pattern confidence 0.7 → immediately used IF > 0.75 threshold

So actually: Pattern waits until next analyst validation (Run 2) to reach 0.75+ confidence.

### Q: What if analyst is wrong?

**A:** If analyst rejects AXON but later accepts similar BLAB, pattern confidence drops. After 2-3 contradictions, pattern is disabled (confidence < 0.6).

### Q: Do patterns ever expire?

**A:** YES. After 30 days, if analyst hasn't re-validated, pattern expires. Prevents stale patterns from blocking good companies.

### Q: Can I manually adjust a threshold?

**A:** Not yet (Phase 2 feature). Currently only analyst feedback creates/updates patterns.

### Q: Are thresholds per-sector?

**A:** Not yet. All companies use same learned thresholds. Phase 3 could segment by sector/stage.

### Q: Does the system learn bad lessons?

**A:** Yes, if analyst is inconsistent. But patterns auto-decay & require validation, so bad patterns don't stick around.

---

## Next Steps

1. **Run a screening** with the new code
2. **Submit feedback with notes** on a rejection
3. **Check logs** for "Selection learning" messages
4. **Query the DB:** `SELECT * FROM selection_learned_patterns WHERE created_at > NOW() - INTERVAL '1 hour'`
5. **Run next screening** and watch patterns apply
6. **Monitor effectiveness** - how many companies do learned patterns reject?

The feedback loop is now live. 🚀
