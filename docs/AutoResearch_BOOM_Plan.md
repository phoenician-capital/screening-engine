# AutoResearch — BOOM Plan
## Phoenician Capital Screening Engine: Autonomous Intelligence Roadmap

*Version 1.0 | March 2026 | CONFIDENTIAL*

---

## Vision

Build the world's most intelligent small-cap investment screening system — one that learns from every decision, improves every night, and eventually surfaces ideas that no human screener would find on their own.

Not a screener. An **autonomous research analyst** that gets smarter every day it runs.

---

## The Core Idea

Today the screening engine is a tool. You run it, review results, make decisions.

With AutoResearch fully built out, it becomes an agent:

- It screens the global universe every night
- It learns from every Research Now / Reject / Watch decision
- It proposes its own weight adjustments and tests them
- It finds patterns in what Phoenician actually selects
- It generates deeper, more personalised investment memos
- It monitors your portfolio, flags risks, finds analogs
- It emails you a morning briefing that reads like a junior analyst wrote it overnight

The engine becomes **a team member, not a tool.**

---

## Phase 1 — Foundation (Now → Month 1)
### "Make the current system production-ready"

**Goal:** Stable, reliable daily screening with consistent results.

| Feature | Description | Priority |
|---|---|---|
| Accumulate results across runs | Never wipe DB — re-rank everything together each run | Done |
| Fix async memo generation | Investment memos generate correctly for all companies | Done |
| Claude pre-screening | Full universe sent to Claude — best 100 candidates selected | Done |
| AWS EC2 deployment | No timeouts, dedicated server, always available | Done |
| International companies | Curated 157-company global list with LLM financials | Done |
| Portfolio holdings loaded | All 19 holdings in DB, available for context | Done |
| Unique index constraints | DB writes reliable, no ON CONFLICT failures | Done |
| Scoring weights editable | Filters page — change criteria without touching code | Done |

**Month 1 target:** 5+ screening runs per week. 200+ companies in DB. 50+ analyst decisions logged.

---

## Phase 2 — AutoResearch Core (Month 1 → Month 2)
### "The engine that learns"

**Goal:** Overnight autonomous weight optimization based on analyst decisions.

### 2.1 Weight History & Experiment Tracking
New database tables:
- `weight_history` — every weight change: before/after, accuracy delta, reason, timestamp
- `experiment_runs` — log of every overnight experiment: proposed weights, accuracy achieved, accepted or discarded

### 2.2 Scoring Dry-Run Mode
Modify the scoring pipeline to accept optional custom weights — score any company with any hypothetical weight set without writing to the database. This is the core capability that makes backtesting possible.

### 2.3 Optimization Engine
The AutoResearch loop (runs nightly at 2:00 AM):

```
1. Load last 30 days of analyst decisions (Research Now / Reject / Watch)
2. Establish baseline accuracy: what % of Research Now companies rank in top 20%?
3. Run 50 experiments:
   a. Propose a small weight perturbation (±0.5 to ±3 pts per category)
   b. Re-score all companies with proposed weights
   c. Measure accuracy against analyst decisions
   d. Keep if better, discard if worse
4. Apply best-found weights if improvement > 1%
5. Log results to DB
6. Include summary in morning email
```

### 2.4 Constraint Engine
Hard rules that no experiment can violate:
- Minimum 50 analyst decisions required before activation
- No weight moves more than ±10 pts from baseline per phase
- Maximum 3 pts change per category per night (smooth learning)
- Total always sums to 100
- Reset to baseline button available at all times

### 2.5 Morning Email — Optimization Section
New section added to daily digest:
- Experiments run, improvements found
- Weight changes applied (before → after, +/- pts)
- Accuracy improvement (67% → 71%)
- Decisions used as training data

### 2.6 Dashboard — Weight Evolution Panel
New panel in the Filters page:
- Auto-optimization toggle (ON/OFF)
- Current weights vs. baseline (side by side)
- Weight evolution line chart (per dimension, over time)
- Accuracy trend chart
- Last 10 nights experiment log
- Reset to baseline button

**Month 2 target:** Weights have adjusted measurably from baseline. Morning email includes optimization summary. Prediction accuracy tracked and improving.

---

## Phase 3 — Intelligence Expansion (Month 2 → Month 3)
### "The engine that searches"

**Goal:** Move beyond scoring known companies — actively hunt for ideas that match Phoenician's evolved profile.

### 3.1 Portfolio DNA Extractor
Every week, the system analyses what Phoenician actually owns and what Roy has marked Research Now. It builds a "DNA profile" of Phoenician's ideal company:

- Average gross margin of Research Now companies
- Average ROIC of Research Now companies
- Sector distribution
- Geography distribution
- Market cap sweet spot
- Common founder/ownership characteristics

This profile is updated weekly and fed into discovery.

### 3.2 DNA-Driven Discovery
Instead of sending Claude a generic mandate, send it Phoenician's evolving DNA profile:

> "Find companies globally that match this profile: avg gross margin 52%, ROIC 18%, market cap $400M–$2B, founder-led preferred, Scandinavia/Poland/Japan/Australia over-represented, Technology and Consumer sectors..."

The more decisions Roy makes, the sharper the DNA profile, the better the discovery.

### 3.3 Similarity Search at Scale
For each company Roy marks Research Now:
- Automatically trigger a similarity search for analogs globally
- Find companies in different geographies with the same business model
- Add to the next screening run
- Tag results as "via [ticker]" in the Results page

### 3.4 Sector Deep-Dive Mode
When Roy shows interest in a sector (multiple Research Now decisions in the same sector), trigger an automated deep-dive:
- Expand the universe filter to include all companies in that sector
- Run a dedicated screening pass
- Surface the best 20 names in that sector specifically

**Month 3 target:** Discovery is driven by Phoenician's actual decisions, not a static mandate. Results feel increasingly relevant and personalised.

---

## Phase 4 — Autonomous Research (Month 3 → Month 6)
### "The engine that investigates"

**Goal:** For every top-ranked company, the engine does real research before Roy even opens the memo.

### 4.1 Pre-Earnings Intelligence
Two weeks before each portfolio company's earnings date (detected via IR monitor):
- Pull last 3 earnings call transcripts
- Analyse: management tone, guidance trends, margin commentary
- Compare: what management said vs. what happened
- Flag: any language suggesting concern or confidence

### 4.2 Insider Conviction Scoring 2.0
Current system: detects cluster buying.
Upgraded: builds a conviction score for each insider across all their historical transactions:
- Has this insider bought before earnings? Did they prove right?
- What is this insider's track record over 5 years?
- How does the current transaction compare to their historical sizing?

### 4.3 Management Quality Profiling
For every screened company, the engine researches the CEO:
- How long have they been CEO?
- What was the company's performance under their tenure?
- Did they found the company or were they hired?
- Have they bought shares personally in the last 2 years?
- What did they say on the last 3 earnings calls?

This feeds directly into the Founder & Ownership dimension with actual evidence, not assumptions.

### 4.4 Competitive Intelligence
For top-ranked companies, the engine automatically:
- Identifies the 3 closest public competitors
- Compares margins, growth, ROIC side by side
- Assesses whether the company has a structural advantage
- Adds this to the investment memo

### 4.5 Red Flag Detection
Real-time monitoring of SEC EDGAR 8-K filings for screened companies:
- Auditor changes
- CFO departures
- Covenant violations
- Related-party transactions
- Restatements

When detected: automatically downgrade the company's rank, flag in Results table, send immediate alert email.

**Month 6 target:** Investment memos include management profiles, competitor comparisons, transcript analysis, and insider track records. The memo reads like it was written by a senior analyst who spent 4 hours on the company.

---

## Phase 5 — Full Autonomy (Month 6 → Month 12)
### "The engine that operates"

**Goal:** The engine runs the full research workflow independently. Roy reviews, decides, and the system handles everything else.

### 5.1 Thesis Validation Loop
When Roy marks a company Research Now, the engine automatically:
- Identifies the 3 core assumptions behind the thesis
- Monitors filings, news, and transcripts for evidence confirming or refuting each assumption
- Weekly update: "Thesis assumption 2 (pricing power) was supported by this week's Q3 transcript"
- Flags when an assumption is undermined: "Revenue growth deceleration detected — see Q2 10-Q"

### 5.2 Portfolio Risk Monitor
Weekly cross-portfolio analysis:
- Sector concentration vs. historical norm
- Geographic concentration
- Factor exposure (value, momentum, quality)
- Correlation between holdings
- Alert if correlation exceeds threshold: "PUUILO.HE and DNP.WA are showing 0.87 correlation — concentrated Poland consumer exposure"

### 5.3 Valuation Alert System
For every watchlisted company:
- Tracks EV/EBITDA, P/FCF, and Price/Sales in real time
- Alerts when the company reaches Roy's target entry multiple
- Shows the current multiple vs. target: "GNTX now at 8.2x EV/EBITDA — your target was 8x"

### 5.4 Capital Allocation Tracker
For every portfolio and watchlist company, monitors:
- Share buyback announcements and execution
- Dividend initiations and increases
- Acquisition announcements — with immediate assessment of strategic logic
- Capex trajectory vs. revenue (is the business getting more or less capital-light?)

### 5.5 Global Compounder Index
Build Phoenician's own private index:
- Every company ever marked Research Now goes in
- Tracked with entry price and date
- Performance compared to benchmark
- This becomes the evidence base that the system is identifying real alpha

**Month 12 target:** The engine is a fully autonomous research department. Every morning Roy receives a brief built overnight by an AI team that has been working since 2 AM — screening, researching, monitoring, and learning.

---

## Scaling Architecture (Required for Phase 4+)

As the system grows, the current single-container architecture will need upgrading:

| Component | Current | Phase 4+ |
|---|---|---|
| Task execution | Synchronous in Streamlit | Celery workers (async job queue) |
| Database | Single PostgreSQL | PostgreSQL + read replicas |
| Scheduling | In-process APScheduler | Dedicated scheduler container |
| Storage | Local EBS volume | S3 for documents and embeddings |
| Server | t3.small (2 vCPU, 2GB) | t3.large or t3.xlarge (4–8 vCPU) |
| Cost | ~$15/month | ~$80–120/month |

None of these changes are needed today. They become relevant when the system is running 1,000+ company analyses overnight.

---

## Data Flywheel

The entire plan depends on one thing: **Roy making decisions.**

Every Research Now, Watch, and Reject click feeds the flywheel:

```
More decisions
    → Better weight calibration (Phase 2)
    → Sharper DNA profile (Phase 3)
    → More relevant discovery
    → Better ranked results
    → Easier to make good decisions
    → More decisions
```

This is why starting now — even before the optimization engine is built — matters. Every decision made today is training data for the system six months from now.

---

## Success Metrics

| Phase | Metric | Target |
|---|---|---|
| Phase 1 | Runs per week | 5+ |
| Phase 2 | Prediction accuracy | 70%+ (from baseline ~50%) |
| Phase 2 | Nightly weight experiments | 50 per night |
| Phase 3 | Discovery quality | >60% of top 10 are "interesting" to Roy |
| Phase 4 | Memo depth | Memos include mgmt profile + competitor analysis |
| Phase 5 | Time saved per week | >5 hours of research replaced |
| Phase 5 | Alpha generation | Positive return on Research Now decisions |

---

## Investment Required

| Phase | Development Time | Infrastructure Cost |
|---|---|---|
| Phase 1 | Complete | $15/month (current) |
| Phase 2 | 4 days | $15/month (no change) |
| Phase 3 | 5 days | $15/month (no change) |
| Phase 4 | 10 days | $30–50/month (larger server) |
| Phase 5 | 15 days | $80–120/month (Celery + scale-up) |
| **Total** | **~34 days over 12 months** | **Max $120/month** |

At $120/month, this is cheaper than one Bloomberg terminal seat. At peak capability, it replaces the initial screening work of 1–2 junior analysts.

---

## Immediate Next Step

**Start Phase 2. Today.**

Phase 1 is complete. Every day we run screenings without Phase 2 active is a day of training data we cannot recover.

Build the optimization engine now. It will sit dormant until 50 decisions are logged. By the time we hit 50 decisions, the engine is ready and waiting.

The flywheel starts spinning the moment Phase 2 is deployed.

---

*Confidential — Internal Use Only*
*Phoenician Capital Investment Technology*
