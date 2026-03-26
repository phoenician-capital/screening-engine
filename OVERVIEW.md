# Phoenician Capital — Screening Engine
## User Guide & Reference Manual

*Version 5.0 | March 2026 | CONFIDENTIAL — Internal Use Only*

---

## 1. What It Does

The Screening Engine is Phoenician Capital's proprietary AI-powered investment research platform. In a single click, it:

1. Sends the full global universe of ~2,600 companies to Claude AI for intelligent pre-screening
2. Fetches structured financial data from FMP for every selected candidate
3. Scores and ranks them against our multi-dimensional scoring framework
4. Generates a full investment memo for every qualifying company
5. Accumulates results across runs — re-ranks everything together each time

The system runs on a dedicated AWS server (eu-north-1, Stockholm) with no timeouts or usage caps:

**http://13.49.7.145:5000**

---

## 2. Three Pages

### Page 1 — Run Screening

One button. Click **Run Screening** and the engine does everything automatically:

```
Step 1 — Discover (Claude AI)
  Fetches ~2,400 US companies from SEC EDGAR + 157 curated international companies
  Sends the full list to Claude with our mandate, portfolio context, and investment philosophy
  Claude acts as an intelligent filter — selects 300–500 companies worth investigating
  No artificial cap — Claude decides how many to select based on quality signals

Step 2 — Ingest (FMP for US + Yahoo Finance for International)
  Fetches full financials for every Claude-selected company in parallel:
    US companies → FMP API: revenue, margins, EBIT, FCF, ROIC, ROE, EV/EBITDA,
                             market cap, CEO name, IPO date, insider ownership %,
                             buybacks, stock-based compensation
    International → Yahoo Finance Timeseries: revenue, gross profit, net income,
                    operating income, FCF, capex — free, no auth, works globally
    Last resort → Claude web search (only if both FMP and Yahoo fail)

Step 3 — Score (10-dimension framework)
  Hard filters eliminate banks, REITs, utilities, financials, excluded countries
  Additive bonus model — missing data = 0 pts added, never a penalty
  Score = points earned / max of available criteria × 100 (fair normalisation)
  Generates a full AI-written investment memo for every qualifying company
  New signals: quality trifecta bonus, capital allocation score, balance sheet quality,
               sector-relative valuation, earnings integrity check

Step 4 — Save & Re-rank
  Writes all qualifying companies to the database
  Deduplicates by ticker — keeps only the best score per company
  Re-ranks ALL accumulated companies across all runs together
  Results immediately visible in the Results page
```

**Max Companies:** Controls how many companies get fully ingested and scored. Recommended:
- **50** — fast run, good for testing (~5 min)
- **100** — standard run, broad coverage (~10 min)
- **200** — thorough run, best results (~20 min)

**Accumulation:** Results build up across runs. Each new run adds fresh companies to the pool. The entire accumulated universe is re-ranked together after every run.

---

### Page 2 — Results

Shows every qualifying company from all screening runs, ranked by composite score.

**Filter controls:**
- **Search** — filter by ticker or company name
- **Min Fit** — minimum fit score (30+, 40+, 50+, 60+, 70+)
- **Max Risk** — cap risk score (< 15, < 25, < 40, < 55)
- **Status** — Pending / Researching / Watched / Rejected
- **Sector** — filter by GICS sector
- **Sort** — Score, Fit, Risk (ascending), or Market Cap

**Table columns:**

| Column | What it means |
|---|---|
| # | Rank across all accumulated runs (1 = best) |
| Ticker | Stock ticker. **F** badge = founder-led detected |
| Company | Full company name |
| Mkt Cap | Market capitalisation |
| Fit | Fit Score (0–100) — how well the company matches our criteria |
| Risk | Risk Score (5–100) — minimum 5, never zero |
| Score | Composite = 70% × Fit − 30% × Risk |
| Gross Mgn | Gross profit margin |
| ROIC | Return on invested capital |
| FCF Yld | Free cash flow yield |
| Rev Gth | Revenue growth year-over-year |
| ND/EBITDA | Net debt / EBITDA leverage |
| Status | Pending / Researching / Watched / Rejected |
| Action | Research Now / Watch / Reject |

Click any row to expand the full investment memo and scoring breakdown.

---

### Page 3 — Filters

Adjust all screening criteria without touching code. Changes take effect on the next run.

**Hard Filters** (pass/fail — companies that fail are excluded entirely):
- Market cap range (default $250M–$10B)
- Gross margin floor (default 15%)
- Excluded sectors: Energy, Utilities, Financials, Real Estate (and all text equivalents)
- Excluded countries: China, Russia, Iran, North Korea, Syria, Belarus
- Profitability requirement (net income > 0)

**Scoring Weights** — the AI analyst agent scores the 6 core dimensions. The weights below govern how the supplementary Python signals are combined with the agent scores:
- Founder & Ownership (20%) — founder detection, insider ownership %, Form 4 buying signals
- Information Edge (5%) — analyst coverage, market cap sweet spot
- Scalability (5%) — recurring revenue keywords, international expansion signals
- Bonus signals — quality trifecta, capital allocation, balance sheet quality, earnings integrity

**Portfolio Holdings** — your 19 tracked companies. Used as context for Claude's pre-screening ("avoid these but find similar quality elsewhere in the world").

---

## 3. Scoring Framework

### Hard Filters (Round 1 — Pass/Fail)

| Filter | Threshold |
|---|---|
| Market cap | $250M – $10B |
| Gross margin | ≥ 15% |
| Sector | Excludes banks, REITs, utilities, energy, financials |
| Country | Excludes China, Russia, Iran, North Korea, Syria, Belarus |
| Profitability | Net income must be positive |
| Instrument type | Excludes ETFs, funds, debt instruments, SPACs |

### Fit Score (Round 2 — 0 to 100)

**Powered by an AI Financial Analyst Agent**

The Fit Score is no longer computed by Python thresholds. It is assessed by a Claude-powered Financial Analyst Agent that reads 5 years of financial history and scores the company the way a senior analyst at a hedge fund would — looking at trends, consistency, and quality, not just point-in-time numbers.

**Why this matters:** A company with consistent 15% revenue CAGR over 5 years scores very differently from one with a single 15% year surrounded by flat/declining periods. The agent detects this. Python thresholds cannot.

**How the agent works:**

1. Receives the company's full 5-year income statement history (revenue, gross profit, EBIT, net income, FCF, capex)
2. Computes multi-year CAGRs, year-to-year growth consistency, and margin expansion trends
3. Scores 6 dimensions using institutional-grade criteria, with evidence for each score
4. Falls back to Python threshold scoring if the agent is unavailable

**The 6 dimensions the agent scores:**

| Dimension | What the Agent Assesses |
|---|---|
| **Business Quality** | Gross margin level + trend, revenue CAGR, NI vs revenue growth (margin expansion evidence), pricing power signals from web search |
| **Unit Economics** | FCF/NI ratio (earnings quality), FCF yield, capex intensity, FCF growing faster than revenue |
| **Capital Returns** | ROIC level, ROIC trend (moat widening vs. eroding), spread over WACC |
| **Growth Quality** | Revenue CAGR over full period, NI CAGR vs revenue CAGR, year-to-year consistency, down years, trajectory |
| **Balance Sheet** | Net cash vs. net debt, ND/EBITDA, interest coverage, financial flexibility |
| **Phoenician Fit** | Holistic mandate alignment — portfolio comparison, moat durability from research, valuation context, information edge |

**What the agent also produces (shown in the UI):**
- **Investment Thesis** — one sentence: bull case + key risk with specific numbers
- **Analyst Verdict** — RESEARCH NOW / WATCH / PASS with a highlighted banner
- **Diligence Checklist** — 3 company-specific questions the analyst must answer before conviction
- **Suggested Action** — the verdict pre-highlights the Research Now button when agent says RESEARCH NOW

**Context the agent receives:**
- 5 years of financial history (revenue, gross profit, EBIT, net income, FCF, capex)
- Current valuation multiples (EV/EBIT, EV/FCF, P/E, FCF yield, ND/EBITDA)
- Sector peer medians (from DB + hardcoded fallbacks per sector)
- Portfolio context (your 19 holdings' avg margins, ROIC, growth, leverage)
- Recent analyst decisions (last 60 days of Research Now / Watch / Reject with reasons)
- Web search (2 searches: business model + recent developments)

**Feedback learning:** Every Research Now, Watch, and Reject you make is recorded. On the next run, the agent reads your last 60 days of decisions and calibrates its scores to match Phoenician's revealed preferences. The more decisions you make, the smarter the agent gets.

**Supplementary Python signals (additive on top of agent score):**
- **Founder & Ownership** — founder-led detection, insider ownership %, Form 4 insider buying activity
- **Quality Trifecta** (+5 pts): GM > 50% AND ROIC > 15% AND FCF yield > 5% simultaneously
- **Capital Allocation** (+6 pts): Active buybacks, low stock dilution, disciplined M&A
- **Balance Sheet Quality** (+5 pts): Net cash position, strong current ratio, low goodwill
- **Earnings Integrity** (+3 pts): AR growth in line with revenue (no channel stuffing)

**Scoring calibration (agent-enforced):**

| Score | What it means |
|---|---|
| 80–100 | Exceptional compounder — rare, all criteria firing |
| 65–79 | High-conviction candidate — strong quality, worth deep research |
| 50–64 | Good business — above average, some gaps |
| 35–49 | Average — no clear edge, not compelling for Phoenician |
| 0–34 | Below average or structurally challenged |

The median global public company scores 40–55. A top-quartile business scores 65–75. A genuine compounder scores 80+.

### Risk Score (Round 3 — 5 to 100)

Every company has a minimum risk score of 5 — no investment is zero risk.

| Risk Factor | Max Points | How It's Scored |
|---|---|---|
| Leverage | 25 | Net Debt/EBITDA — computed from components if direct ratio unavailable |
| Profitability | 20 | Negative NI = full points; thin margins = partial points |
| Earnings Quality | 15 | Negative FCF despite positive NI = red flag |
| Customer Concentration | 10 | Detected from filings; small companies get baseline risk |
| Jurisdiction | 15 | Tiered: high-risk EM > elevated EM > moderate > low-risk developed |
| Valuation/Red Flags | 10 | Priced-for-perfection multiples; regulatory/accounting flags from filings |

### Founder Detection

The system automatically detects likely founder-led companies from FMP data:
- CEO last name appears in company name (eponymous founder)
- Company < 20 years old (founder likely still running it)
- Large, old companies with professional management flagged as non-founder-led

### Sector-Relative Valuation

When enough companies exist in the DB to compute a sector median, EV/EBITDA and P/FCF are scored relative to sector peers — not absolute thresholds. A 15x EV/EBITDA pharma company 40% below peers scores better than a 10x software company at a premium to peers.

### Final Rank Score

```
Rank Score = (70% × Fit Score) − (30% × Risk Score)
```

All companies across all screening runs are re-ranked together after every run. The Results page always shows the full accumulated universe sorted by Rank Score.

---

## 4. Data Sources

| Source | What It Provides | Coverage |
|---|---|---|
| **SEC EDGAR** | US company universe (~7,000 tickers), CIK numbers, XBRL financials, Form 4 insider transactions | US public companies |
| **FMP (Financial Modeling Prep)** | Income statement, cash flow, key metrics, ratios, profile (CEO, IPO date, market cap, insider ownership) | US + major international |
| **Claude AI (Anthropic)** | Intelligent universe pre-screening (300–500 companies from 2,600), investment memo generation | Global |
| **Yahoo Finance Timeseries** | Annual revenue, gross profit, net income, operating income, FCF, capex for international companies — free, no auth, works from server | Global (all exchanges) |
| **Curated International List** | 157 vetted companies across Scandinavia, Poland, Japan, Australia, Singapore, UK, Netherlands, Germany, etc. | Non-US exchanges |

---

## 5. Investment Memos

A full investment memo is generated for every company that passes the hard filters. Written by Claude using actual financial data from FMP and our scoring framework.

Each memo contains:

1. **Business Model** — What the company does, how it makes money, competitive position
2. **Fit Score Analysis** — Commentary on each scoring dimension with data
3. **Financial Highlights** — Revenue, margins, ROIC, FCF, leverage with context
4. **Key Strengths** — Top 3–5 compelling aspects for Phoenician
5. **Key Risks** — Top 2–3 concerns with specific evidence
6. **Valuation** — Current multiple vs. sector and history
7. **Portfolio Comparison** — How this compares to what we already own
8. **Verdict** — Whether this fits the mandate and why

Memos are AI-generated and are a **research starting point, not a final recommendation.** Always verify against primary sources before acting.

---

## 6. Portfolio Monitor

Tracks all 19 of Phoenician's current holdings in real time.

**IR Events** — Click **Scan IR Sites Now** to scrape each company's investor relations website for new events (earnings dates, presentations, press releases, regulatory announcements). Covers all languages — Japanese, Finnish, Polish, Greek, Swedish, etc.

**SEC 8-K Signals** — Monitors SEC filings from the last 7 days for material events: CEO changes, buyback authorizations, earnings guidance, restatements, covenant violations.

**Portfolio Analogs** — Companies discovered by the screening engine that are similar in quality profile to existing holdings. Tagged "via [ticker]" to show which holding inspired the discovery.

---

## 7. What the System Does and Does Not Do

### Does
- Intelligently pre-screens 2,600 global companies using Claude's judgment
- Fetches structured financial data and computes all key metrics
- Scores companies using a 10-dimension additive framework (no data penalties)
- Detects founders, insider ownership, recurring revenue, capital allocation quality
- Generates detailed AI-written investment memos with portfolio comparisons
- Accumulates results across runs — universe grows with every screening
- Monitors portfolio company IR websites and SEC filings
- Runs on a dedicated AWS server — no timeouts, no limits

### Does Not
- Make buy or sell recommendations
- Execute trades or connect to any brokerage
- Replace fundamental analysis (memos are starting points)
- Guarantee data accuracy (verify against primary sources)
- Store material non-public information

---

## 8. Deployment

The system runs on AWS EC2 (eu-north-1 — Stockholm):

| Component | Details |
|---|---|
| **Dashboard** | http://13.49.7.145:5000 |
| **Server** | AWS EC2 t3.small, eu-north-1a |
| **Database** | PostgreSQL 16 with pgvector, 30GB EBS |
| **Cache** | Redis 7 |
| **Cost** | ~$15/month |

**SSH access:**
```bash
ssh -i ~/.ssh/phoenician-bastion.pem ubuntu@13.49.7.145
```

**Check live logs:**
```bash
ssh -i ~/.ssh/phoenician-bastion.pem ubuntu@13.49.7.145 \
  "docker logs screening-engine-dashboard-1 --tail 50 -f"
```

**Deploy latest code:**
```bash
ssh -i ~/.ssh/phoenician-bastion.pem ubuntu@13.49.7.145 \
  "cd /home/ubuntu/screening-engine && git pull && \
   docker compose build dashboard --no-cache && \
   docker compose up -d dashboard"
```

**Clear database (fresh start):**
```bash
ssh -i ~/.ssh/phoenician-bastion.pem ubuntu@13.49.7.145 \
  "docker exec screening-engine-db-1 psql -U phoenician -d phoenician -c \
  'TRUNCATE TABLE embeddings, documents, metrics, recommendations, feedback, \
   watchlist, exclusions, scoring_runs, insider_purchases, price_alerts \
   RESTART IDENTITY CASCADE; DELETE FROM companies;'"
```

**Monitor logs via CloudWatch:**

AWS Console → CloudWatch → Log Groups → **screening-engine-dashboard** → dashboard

Direct link: `https://eu-north-1.console.aws.amazon.com/cloudwatch/home?region=eu-north-1#logsV2:log-groups/log-group/screening-engine-dashboard`

Logs stream automatically from the EC2 instance in real time.

---

*Questions? Contact the Investment Technology team.*
*Confidential — Internal Use Only*
