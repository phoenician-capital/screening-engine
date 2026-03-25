# AutoResearch Integration — Proposal
## Phoenician Capital Screening Engine

*Prepared by: Investment Technology Team*
*Date: March 25, 2026*
*Status: Proposed — Pending Approval*

---

## The Problem

Our screening engine scores companies using fixed weights across 6 dimensions (Founder, Business Quality, Unit Economics, Valuation, Information Edge, Scalability). These weights were set at launch based on our investment mandate — but they represent our best guess, not evidence of what Roy actually selects when reviewing real companies.

As a result, the engine ranks companies based on a static formula that does not evolve. Over time, there will be a growing gap between what the system surfaces and what the analyst actually finds interesting.

---

## The Opportunity

Andrej Karpathy (co-founder of OpenAI) released AutoResearch in March 2026 — a framework that runs an autonomous improvement loop overnight:

> Propose a change → Test it → Measure the result → Keep if better → Repeat

We propose to apply this exact pattern to our scoring model. Every night, an AI agent will:

1. Look at Roy's past Research Now / Reject decisions
2. Propose small adjustments to the scoring weights
3. Test whether those adjustments would have better predicted his decisions
4. Keep improvements, discard failures
5. Run 50 experiments (≈25 minutes total)
6. Send a morning summary of what changed and why

The system learns from behaviour, not from instructions. It does not require Roy to explain his preferences — it observes them.

---

## What Changes in Practice

**For the analyst:** Nothing. The daily workflow is unchanged. Roy screens, reviews, and decides exactly as today. The only addition is a morning email showing how the model evolved overnight.

**For the system:** Scoring weights update automatically after each overnight run. Roy can view the full history, override any weight manually, or turn the feature off — all from the Filters page.

**Hard constraints to prevent drift:**
- No single weight can move more than ±10 points from its baseline
- Total weights always sum to 100
- System stays on fixed weights until minimum 50 decisions are logged
- Roy can reset to baseline at any time with one click

---

## Expected Impact

| Timeframe | Decisions Logged | Expected Effect |
|---|---|---|
| Week 1–2 | 0–30 | Baseline, no change yet |
| Week 3–4 | 30–80 | First adjustments, minor improvement |
| Month 2 | 80–200 | Meaningful improvement, weights stabilising |
| Month 3+ | 200+ | Mature model, highly personalised to Phoenician's style |

In practical terms: the top 10 results of each screening run will increasingly feel like companies Roy would have selected himself — without him having to manually tune anything.

---

## What We Build

| Component | Description | Status |
|---|---|---|
| Feedback data collector | Stores every Research Now / Watch / Reject decision | Already built |
| Optimization engine | Runs nightly experiments, proposes weight adjustments | To build |
| Overnight scheduler | Runs at 2:00 AM, 50 experiments, sends morning email | To build |
| Dashboard panel | Weight history chart, accuracy trend, on/off toggle | To build |

**Estimated development time: 4 days**
**Activation: automatic when 50 decisions are logged (est. 2–4 weeks from first use)**

---

## Why We Recommend Building Now

If we wait until 50 decisions are made, we lose those 50 decisions as training data. Building now means the system starts collecting immediately from day one. By the time we have sufficient data to activate, the optimization engine is already ready and waiting.

There is no downside to building now — the system sits dormant until conditions are met, then self-activates without any manual step.

---

## Decision Required

| Option | Description | Recommendation |
|---|---|---|
| **A — Build now** | Develop in 4 days, collect data from day one, auto-activate when ready | **Recommended** |
| B — Build later | Wait 2–4 weeks, then build. Loses early training data. | |
| C — Don't build | Keep fixed weights permanently. | |

---

*Next step: Approval to proceed with Option A*
*All development within existing infrastructure — no new services or costs required*
*Confidential — Internal Use Only*
