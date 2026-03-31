# Action Plan: Fix Critical Gaps (4-5 Hour Implementation)

## Priority 1: Fix LLM Client Calls (5 min)

### File: `src/feedback/selection_feedback_analyzer.py`

**Problem:** Line 196 calls `await self.llm.complete(..., output_format="json")` but parameter doesn't exist.

**Fix:**
```python
async def _extract_concerns(self, notes: str) -> list[str]:
    """Parse analyst notes to extract specific concerns using LLM."""
    if not notes or len(notes.strip()) < 10:
        return []

    prompt = f"""Analyst notes: "{notes}"

Extract the specific concerns, red flags, or reasons for rejection mentioned.
Return ONLY a JSON list of concern strings, one per issue.
Example: ["unsustainable buybacks", "unclear business model", "too much leverage"]

If no specific concerns found, return empty list: []
Be thorough — capture all distinct concerns mentioned."""
    
    try:
        # FIX: Remove output_format="json", it doesn't exist
        response = await self.llm.complete(
            prompt, 
            model="claude-haiku", 
            temperature=0
        )
        
        # Parse the string response as JSON
        if isinstance(response, str):
            concerns = json.loads(response)
            return concerns if isinstance(concerns, list) else []
        return response if isinstance(response, list) else []
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response as JSON: {e}")
        return []
    except Exception as e:
        logger.warning(f"Failed to extract concerns: {e}")
        return []
```

**Verify:** Run a test feedback submission and check for JSON parsing errors in logs.

---

## Priority 2: Wire Selection Pipeline (15 min)

### File: `src/orchestration/pipelines/scoring_pipeline.py`

**Location:** In the `_score_one()` function, around line 172-175

**Current Code:**
```python
async def _score_one(company) -> None:
    async with sem:
        # 3. Get latest metrics
        metrics = await self.metric_repo.get_latest(company.ticker)
        if not metrics:
            logger.warning("No metrics for %s, skipping", company.ticker)
            return

        # ... rest of scoring logic ...
```

**Add Before Metrics Check:**
```python
async def _score_one(company) -> None:
    async with sem:
        # STEP 0: Selection Team Pre-Filter (NEW)
        try:
            selection_pipeline = CompanySelectionPipeline(self.session)
            selection_result = await selection_pipeline.evaluate_company(company, None)
            
            if not selection_result.passed_selection:
                # Company rejected by selection team, skip scoring
                results.append(ScoringResult(
                    ticker=company.ticker,
                    fit_score=0,
                    risk_score=100,
                    rank_score=-100,
                    disqualified=True,
                    disqualify_reason=f"Selection filter: {selection_result.disqualification_reason}",
                ))
                logger.debug(f"✗ {company.ticker}: {selection_result.disqualification_reason}")
                return
        except Exception as e:
            logger.error(f"Selection pipeline failed for {company.ticker}: {e}")
            # Continue with normal scoring if selection fails
            pass
        
        # 3. Get latest metrics
        metrics = await self.metric_repo.get_latest(company.ticker)
        # ... rest continues unchanged ...
```

**Add Imports at top:**
```python
from src.orchestration.pipelines.selection_pipeline import CompanySelectionPipeline
```

**Verify:**
- Run a screening
- Check logs for "Selection filter:" rejections
- Verify fewer companies reach scoring stage

---

## Priority 3: Load Actual Metrics (1-2 hours)

### File: `src/orchestration/pipelines/selection_pipeline.py`

**Problem:** Line 105-145 has `founder_ownership=None`, `insider_ownership=None`, `major_acquisitions_3yr=0`

**The fix requires database queries.** In the `evaluate_company()` function:

```python
async def evaluate_company(
    self, company: Company, metric: Metric | None
) -> SelectionResult:
    """Evaluate one company through all 5 selection agents."""

    # LOAD ACTUAL DATA FROM DATABASE
    
    # 1. Load founder/insider ownership
    insider_data = {}
    try:
        from sqlalchemy import select, func
        from src.db.models.insider_purchase import InsiderPurchase
        
        # Query insider purchases (last 30 days)
        stmt = select(func.count(InsiderPurchase.id)).where(
            InsiderPurchase.ticker == company.ticker,
            InsiderPurchase.transaction_date >= datetime.utcnow() - timedelta(days=30)
        )
        result = await self.session.execute(stmt)
        recent_insider_buys = result.scalar() or 0
        
        # Get total insider ownership (if available in company table or separate table)
        insider_ownership = getattr(company, 'insider_ownership_pct', None)
        if metric and metric.insider_ownership_pct:
            insider_ownership = float(metric.insider_ownership_pct)
    except Exception as e:
        logger.warning(f"Failed to load insider data for {company.ticker}: {e}")
        recent_insider_buys = 0
        insider_ownership = None
    
    # 2. Load founder status
    founder_ownership = None
    founder_name = company.founder_name
    try:
        # Check if marked as founder-led
        if company.is_founder_led:
            # Try to find founder ownership percentage
            # This might be in a separate table or Company table
            founder_ownership = getattr(company, 'founder_ownership_pct', 0.05)
    except Exception as e:
        logger.warning(f"Failed to determine founder status for {company.ticker}: {e}")
    
    # 3. Load acquisition history
    major_acquisitions_3yr = 0
    acquisition_spend = 0
    try:
        from sqlalchemy import select, func
        from src.db.models.metric import Metric
        
        # If you have historical metrics, count acquisitions
        # For now, use metric.acquisitions_net as proxy
        if metric and metric.acquisitions_net:
            acquisition_spend = float(metric.acquisitions_net)
            major_acquisitions_3yr = 1 if acquisition_spend > 100_000_000 else 0
    except Exception as e:
        logger.warning(f"Failed to load acquisition data for {company.ticker}: {e}")
    
    # 4. Calculate derived metrics
    if metric:
        # Calculate buyback to FCF ratio
        buyback_to_fcf_ratio = None
        if metric.stock_repurchased and metric.fcf and metric.fcf > 0:
            buyback_to_fcf_ratio = metric.stock_repurchased / metric.fcf
        
        # Calculate stock dilution rate (if we have share count history)
        stock_dilution_rate = None
        if metric.stock_based_compensation and metric.revenue:
            stock_dilution_rate = metric.stock_based_compensation / metric.revenue
    
    # Now use these in agent evaluations:
    founder_decision = await self.founder_agent.evaluate(
        founder_ownership=founder_ownership,
        insider_ownership=insider_ownership,
        founder_name=founder_name,
        recent_insider_buys=recent_insider_buys,
    )
    
    # ... rest of agents with actual data ...
    
    red_flag_decision = await self.red_flag_agent.evaluate(
        ticker=company.ticker,
        buyback_to_fcf_ratio=buyback_to_fcf_ratio,
        stock_dilution_rate=stock_dilution_rate,
        # ... other metrics ...
    )
```

**Verify:**
- Agents now receive actual data instead of None
- Founder/Growth agents can make real decisions
- Red Flag agent has metrics to check

---

## Priority 4: Enable Dynamic Thresholds (10 min)

### File: `src/scoring/agents/selection/red_flag_agent.py`

**Problem:** `_get_learned_patterns()` exists but is never called. Dynamic thresholds never applied.

**Fix:** In the `evaluate()` function, replace this block:

```python
# CURRENT (DOESN'T WORK):
async def evaluate(self, ticker: str, ...):
    flags = []
    
    # ... static checks ...
    
    # 6. Check learned patterns from feedback (if session provided)
    if self.session and ticker:
        learned_flags = await self._check_learned_patterns(ticker)
        flags.extend(learned_flags)
```

**With this:**

```python
# FIXED (APPLIES DYNAMIC THRESHOLDS):
async def evaluate(self, ticker: str, ...):
    flags = []
    applied_patterns = []
    
    # LOAD LEARNED PATTERNS (NEW)
    learned_patterns = {}
    if self.session:
        learned_patterns = await self._get_learned_patterns()
    
    # Helper to get dynamic threshold
    def _get_threshold(metric_name: str, baseline: float) -> tuple[float, bool]:
        if metric_name in learned_patterns:
            pattern = learned_patterns[metric_name]
            if pattern.get("confidence", 0) > 0.75:
                return pattern.get("suggested_threshold", baseline), True
        return baseline, False
    
    # 1. Buyback (with dynamic threshold)
    if buyback_to_fcf_ratio is not None:
        threshold, is_learned = _get_threshold("buyback_to_fcf_ratio", 1.0)
        if buyback_to_fcf_ratio > threshold:
            source = " (learned from analyst feedback)" if is_learned else ""
            flags.append(f"Unsustainable buyback {buyback_to_fcf_ratio:.1f}x > {threshold:.1f}x{source}")
            if is_learned:
                applied_patterns.append("buyback_to_fcf_ratio")
    
    # ... similar for other metrics ...
    
    return AgentDecision(
        passed=len(flags) == 0,
        reason=" | ".join(flags) if flags else "No red flags",
        metadata={
            "applied_learned_patterns": applied_patterns,
            "learned_count": len(applied_patterns),
        },
    )
```

**Verify:**
- Check logs for "learned from analyst feedback"
- Verify selection_agent_decisions.metadata has `applied_learned_patterns`

---

## Priority 5: Fix Feedback Processing (30 min)

### File: `src/orchestration/pipelines/bidirectional_feedback_pipeline.py`

**Problem:** Early return when `feedback.recommendation is None`

**Fix:**

```python
async def process_feedback(self, feedback: Feedback):
    """Process feedback for both selection and scoring teams."""
    
    # Ensure recommendation is loaded
    if not feedback.recommendation:
        # Try to reload explicitly
        from src.db.repositories.recommendation_repo import RecommendationRepository
        rec_repo = RecommendationRepository(self.session)
        rec = await rec_repo.get_by_id(feedback.recommendation_id)
        if not rec:
            logger.warning(f"Feedback {feedback.id} has no recommendation, skipping")
            return
    else:
        rec = feedback.recommendation
    
    company = rec.company
    metrics = rec.metrics_at_time_of_scoring if hasattr(rec, 'metrics_at_time_of_scoring') else None
    
    logger.info(f"Processing feedback for {feedback.ticker}: action={feedback.action}, notes={bool(feedback.notes)}")
    
    # SELECTION TEAM LEARNING
    if feedback.action == "reject" and feedback.notes:
        selection_analyzer = SelectionFeedbackAnalyzer(self.session)
        try:
            selection_learnings = await selection_analyzer.analyze(
                feedback=feedback,
                company=company,
                metrics=metrics,
                selection_detail=rec.scoring_detail.get("selection_detail") if rec.scoring_detail else None,
            )
            
            for learning in selection_learnings:
                learning["feedback_id"] = feedback.id
                learning["analyst_action"] = feedback.action
                learning["confidence"] = 0.7
                await self.selection_repo.save_pattern(learning)
                logger.info(f"Stored learning: {learning['type']} on {learning['agent']}")
        except Exception as e:
            logger.error(f"Selection learning failed for {feedback.ticker}: {e}", exc_info=True)
    
    # SCORING TEAM LEARNING (simplified for now)
    if feedback.notes:
        try:
            scoring_learnings = await self._analyze_scoring_feedback(feedback, company, metrics)
            for learning in scoring_learnings:
                learning["feedback_id"] = feedback.id
                learning["analyst_action"] = feedback.action
                await self.scoring_repo.save_pattern(learning)
        except Exception as e:
            logger.error(f"Scoring learning failed for {feedback.ticker}: {e}")
```

**Verify:**
- Submit feedback with notes
- Check logs for "Stored learning" messages
- Query `selection_learned_patterns` table

---

## Testing Checklist

After implementing all fixes:

```bash
# 1. Test LLM call
curl -X POST http://localhost:8000/api/v1/recommendations/AXON/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "action": "reject",
    "notes": "Unsustainable buyback $210M vs FCF $70M. Conglomerate structure unclear."
  }'

# Check logs: "Extracting concerns..."
# Check logs: No JSON decode errors

# 2. Test Selection Pipeline Wiring
# Run screening, check for "Selection filter:" log entries

# 3. Test Dynamic Thresholds
# Verify logs show "learned from analyst feedback"
# Query: SELECT * FROM selection_learned_patterns LIMIT 5

# 4. Test Learned Pattern Application
# Run next screening
# Verify: Companies with learned-pattern metrics rejected with "learned" label
```

---

## Estimated Timeline

| Task | Time | Status |
|------|------|--------|
| Fix LLM calls | 5 min | Easy, just parameter removal |
| Wire selection pipeline | 15 min | Straightforward integration |
| Load metrics from DB | 60-90 min | Most work, multiple queries |
| Enable dynamic thresholds | 10 min | Code already written |
| Fix feedback processing | 30 min | Relationship loading + error handling |
| **Total** | **2-3 hours** | **Estimated** |

Plus 1-2 hours for:
- Testing
- Debugging issues
- Checking logs

**Total: 3-5 hours to fully working system**

---

## Risk Mitigation

**If you run out of time:**
1. Do Priority 1 + 2 (20 min) → Selection pipeline wired but with None metrics
2. Do Priority 3 (90 min) → Real metrics loaded, agents work
3. Skip 4 + 5 → Dynamic thresholds & feedback learning can come later

That's 1.5 hours → 70% of the system working.
