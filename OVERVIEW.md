# Phoenician Capital — Screening Engine
## User Guide & Reference Manual

*Version 6.0 | March 2026 | CONFIDENTIAL — Internal Use Only*

---

## 1. What It Does

The Screening Engine is Phoenician Capital's proprietary AI-powered investment research platform. In a single click, it:

1. Pre-filters the global universe using FMP quality screener (GM > 40%, revenue growth > 8%) — cuts 2,400 random names down to 300–600 quality candidates before Claude ever sees them
2. Sends filtered candidates + dynamically discovered international companies to Claude AI for intelligent pre-screening
3. Fetches structured financial data from FMP for every selected candidate
4. Scores and ranks them using an AI Financial Analyst Agent (4 web searches, bear case, self-critique, 2-stage DCF)
5. Generates a full investment memo for every qualifying company

The system runs on a dedicated AWS server (eu-north-1, Stockholm) with no timeouts or usage caps:

**http://13.49.7.145:3000** (React frontend)
**http://13.49.7.145:5000** (Streamlit dashboard)

---

## 2. Three Pages

### Page 1 — Run Screening

One button. Click **Run Screening** and the engine does everything automatically:

```
Step 1 — Discover (FMP Quality Filter + Claude AI)

  US universe:
    FMP company screener pre-filters for GM > 40%, revenue growth > 8%,
    market cap $250M–$5B → ~300–600 quality candidates
    Falls back to EDGAR/NASDAQ list if FMP returns < 50 results
    Claude then intelligently selects 300–500 from these pre-filtered candidates

  International universe (dynamic, agent-driven):
    Claude searches for high-quality companies across all 23 markets:
    Tier-1: US/GB/SE/NO/DK/FI/DE/NL/BE/CH/AU/CA/JP/SG/IL
    Tier-2: PL/FR/IT/ES/AT/IE/NZ/HK
    Target: 100–150 international candidates (GM > 40%, ROIC > 10%, growth > 8%)
    Up to 25 web searches per run (one per market + cross-market)
    Falls back to LLM re-extraction if JSON parsing fails

  Combined pre-screen:
    Claude sees all candidates and selects 300–500 for financial ingestion
    Intelligent filter — no artificial cap, Claude decides based on quality

Step 2 — Ingest (FMP)
  Fetches full financials for every Claude-selected company in parallel:
    Revenue, margins, EBIT, FCF, ROIC, ROE, EV/EBITDA, market cap, CEO,
    IPO date, insider ownership %, buybacks, stock-based compensation
    5-year income statement history for trend analysis and DCF inputs

Step 3 — Score (AI Analyst Agent)
  Hard filters eliminate banks, REITs, utilities, financials, excluded countries
  AI Analyst Agent scores each company (see Section 3 for full details):
    4 targeted web searches per company (moat, trajectory, bear case, valuation)
    Mandatory bear case with 3 specific failure scenarios
    Self-critique loop before finalising score
    2-stage NOPAT DCF with agent-chosen assumptions
    Mandatory score gates for weak fundamentals
  Generates a full AI-written investment memo for every qualifying company

Step 4 — Save & Rank
  Writes all qualifying companies to the database
  Rank Score = max(0, 70% × Fit − 30% × Risk)  [floored at 0]
  Results immediately visible in the Results page
```

**Max Companies:** Controls how many companies get fully ingested and scored. Recommended:
- **50** — fast run, good for testing (~15–20 min with AI agent)
- **100** — standard run, broad coverage (~30–40 min)
- **200** — thorough run, best results (~60–80 min)

**Runs are browser-independent.** The screening pipeline runs inside Docker on the EC2 server. Closing your browser or switching tabs does **not** stop the run.

---

### Page 2 — Results

Shows every qualifying company from all screening runs, ranked by composite score.

**Filter controls:**
- **Search** — filter by ticker or company name
- **Min Fit** — minimum fit score (40+, 50+, 60+, 70+)
- **Max Risk** — cap risk score (< 15, < 25, < 40)
- **Status** — Pending / Researching / Watched / Rejected
- **Sector** — filter by GICS sector
- **Sort** — Score, Fit, Risk (ascending), or Market Cap

**Table columns:**

| Column | What it means |
|---|---|
| # | Rank (1 = best) |
| Ticker | Stock ticker. **F** badge = founder-led. Gold badge = portfolio analog |
| Company | Full company name + sector |
| Mkt Cap | Market capitalisation |
| Fit | Fit Score (0–100) — AI analyst quality assessment |
| Risk | Risk Score (5–100) — minimum 5, never zero |
| Score | Rank Score = max(0, 70% × Fit − 30% × Risk) |
| Gross Mgn | Gross profit margin |
| ROIC | Return on invested capital |
| FCF Yld | Free cash flow yield |
| Rev Gth | Revenue growth year-over-year |
| ND/EBITDA | Net debt / EBITDA leverage |
| Status | Pending / Researching / Watched / Rejected |

**Click any row** to open the detail drawer with full investment memo, scoring breakdown, bear case, DCF, and diligence checklist.

**Sidebar stats** auto-refresh every 60 seconds showing: Ranked companies, In Research, Watchlist, Avg Fit.

---

### Page 3 — Filters

Adjust all screening criteria without touching code. Changes take effect on the next run.

**Hard Filters** (pass/fail — companies that fail are excluded entirely):
- Market cap range (default $250M–$10B)
- Gross margin floor (default 15%)
- Excluded sectors: Energy, Utilities, Financials, Real Estate
- Excluded countries: China, Russia, Iran, North Korea, Syria, Belarus
- Profitability requirement (net income > 0)

**Portfolio Holdings** — your tracked companies. Used as context for Claude's pre-screening.

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

Each company is scored by a Claude Sonnet 4.6 agent that reads 5 years of financial history, runs 4 targeted web searches, writes a mandatory bear case, self-critiques, and computes a 2-stage DCF — all before assigning a score.

#### Agent workflow (per company):

1. **Build financial context** — 5-year income history + pre-computed trend signals:
   - Gross margin trend (expanding / stable / contracting)
   - Revenue growth σ (consistency), down-year count, growth trajectory (accel/decel)
   - NI CAGR vs Revenue CAGR (operating leverage signal)
   - EBIT CAGRs (3yr + 5yr) for DCF anchor

2. **4 targeted web searches:**
   - Search 1: Moat & business model (competitive positioning, pricing power evidence)
   - Search 2: Recent earnings & trajectory (latest results, management guidance, estimate trends)
   - Search 3: Bear case (short seller theses, analyst downgrades, structural threats)
   - Search 4: Valuation vs peers & insider activity (relative multiples, Form 4 transactions)

3. **Devil's advocate** — mandatory `bear_case` with 3 specific failure scenarios before scoring

4. **Score 9 dimensions** using institutional-grade criteria

5. **Self-critique** — "Would a Phoenician partner challenge this score?" before finalising

6. **DCF valuation** — agent chooses assumptions informed by EBIT CAGRs:
   - Stage 1: 5-year growth rate (hard cap ≤ 35%)
   - Stage 2: terminal growth rate (hard cap ≤ 5%)
   - WACC: Tier-1 base 9%, Tier-2 base 11% (hard cap ≥ 7%)
   - Computes intrinsic equity value vs current market cap → discount / premium %

#### The 9 dimensions the agent scores:

| Dimension | What the Agent Assesses |
|---|---|
| **Business Quality** | Gross margin level + trend, revenue CAGR, margin expansion evidence, pricing power |
| **Unit Economics** | FCF/NI ratio, FCF yield, capex intensity, FCF growing faster than revenue |
| **Capital Returns** | ROIC level, ROIC trend (moat widening vs. eroding), spread over WACC |
| **Growth Quality** | Revenue CAGR over full period, NI CAGR vs Rev CAGR, down years, trajectory |
| **Balance Sheet** | Net cash vs. net debt, ND/EBITDA, interest coverage |
| **Phoenician Fit** | Mandate alignment, moat durability, valuation context, information edge |
| **Bear Case** | Mandatory 3-scenario failure analysis (evidence = stored in scoring_detail) |
| **DCF Assumptions** | Agent-chosen stage1/terminal/WACC with reasoning |
| **Analyst Thesis** | Investment thesis, bear case text, DCF result, diligence questions |

#### Mandatory score gates (hard caps enforced before finalising):

| Condition | Cap |
|---|---|
| Gross margin < 25% | ≤ 35 |
| ROIC < 8% (3-year avg) | ≤ 35 |
| Revenue declining 2+ consecutive years | ≤ 35 |
| Net Debt/EBITDA > 4x | ≤ 35 |
| Net income negative 2+ of last 3 years | ≤ 35 |
| Gross margin < 35% | ≤ 50 |
| No pricing power evidence | ≤ 50 |
| ROIC trending down 3+ years | ≤ 50 |

#### Score distribution (agent-enforced):

| Score | Approx % of universe | What it means |
|---|---|---|
| 77–100 | ~7% | Exceptional — rare, all criteria firing |
| 65–76 | ~18% | High-conviction — strong quality, worth deep research |
| 50–64 | ~35% | Average — above-median, some gaps |
| 0–49 | ~40% | Below average or structurally challenged |

#### Verdict thresholds:

| Verdict | Condition |
|---|---|
| **RESEARCH NOW** | Fit ≥ 72 AND Risk ≤ 45 |
| **WATCH** | Fit 55–71 |
| **PASS** | Fit < 55 OR Risk > 65 |

#### What the agent produces (shown in the detail drawer):

- **Investment Thesis** — bull case + key risk with specific numbers
- **Bear Case** — 3 specific failure scenarios researched from web
- **DCF Result** — intrinsic equity value vs market cap, discount/premium %
- **Analyst Verdict** — RESEARCH NOW / WATCH / PASS with banner
- **Diligence Checklist** — 3 company-specific questions before conviction

**Supplementary Python signals (additive on top of agent score):**
- **Founder & Ownership** — founder-led detection, insider ownership %, Form 4 buying activity
- **Quality Trifecta** (+5 pts): GM > 50% AND ROIC > 15% AND FCF yield > 5%
- **Capital Allocation** (+6 pts): Active buybacks, low dilution, disciplined M&A
- **Balance Sheet Quality** (+5 pts): Net cash position, strong current ratio, low goodwill
- **Earnings Integrity** (+3 pts): AR growth in line with revenue

**Feedback learning:** Every Research Now / Watch / Reject is recorded. On the next run, the agent reads the last 60 days of decisions and calibrates to Phoenician's revealed preferences.

### Risk Score (Round 3 — 5 to 100)

Every company has a minimum risk score of 5.

| Risk Factor | Max Points | How It's Scored |
|---|---|---|
| Leverage | 25 | Net Debt/EBITDA |
| Profitability | 20 | Negative NI = full points; thin margins = partial |
| Earnings Quality | 15 | Negative FCF despite positive NI |
| Customer Concentration | 10 | Detected from filings |
| Jurisdiction | 15 | Tiered: high-risk EM > elevated EM > moderate > developed |
| Valuation/Red Flags | 10 | Priced-for-perfection multiples; regulatory/accounting flags |

### Final Rank Score

```
Rank Score = max(0,  70% × Fit Score  −  30% × Risk Score)
```

Floored at 0 — companies with very high risk relative to fit don't show negative scores.

---

## 4. Data Sources

| Source | What It Provides | Coverage |
|---|---|---|
| **FMP Quality Screener** | Pre-filters US universe by GM > 40%, rev growth > 8%, $250M–$5B market cap | US (pre-discovery) |
| **SEC EDGAR** | US company universe fallback (~7,000 tickers), Form 4 insider transactions | US public companies |
| **FMP (Financial Modeling Prep)** | Income statement (5yr history), cash flow, key metrics, ratios, profile | US + major international |
| **Claude AI (Anthropic)** | Universe pre-screening, 4 web searches per company, bear case, DCF assumptions, memo generation | Global |

---

## 5. Investment Memos

A full investment memo is generated for every qualifying company. Accessible by clicking any row in the Results table.

**Memo tab contents:**
1. Business Model — what the company does, competitive position
2. Financial Highlights — revenue, margins, ROIC, FCF, leverage
3. Key Strengths — top 3–5 compelling aspects
4. Key Risks / Bear Case — 3 specific failure scenarios from web research
5. DCF Valuation — intrinsic equity value, assumptions, discount/premium to market cap
6. Verdict — RESEARCH NOW / WATCH / PASS with reasoning

**Scoring tab contents:**
- Each dimension score with evidence text
- Bear case scenarios
- DCF result and agent reasoning

**Diligence tab:**
- 3 company-specific questions the analyst must answer before conviction

Memos are AI-generated and are a **research starting point, not a final recommendation.** Always verify against primary sources before acting.

---

## 6. Portfolio Monitor

Tracks Phoenician's current holdings in real time.

**IR Events** — Click **Scan IR Sites Now** to scrape each company's investor relations website for new events (earnings dates, presentations, press releases). Covers all languages — Japanese, Finnish, Polish, Swedish, etc. (45s timeout per holding).

**SEC 8-K Signals** — Monitors SEC filings from the last 7 days for material events: CEO changes, buyback authorizations, guidance, restatements.

**Portfolio Analogs** — Companies discovered by the screening engine similar in quality to existing holdings. Tagged with the holding that inspired the discovery.

---

## 7. Deployment

The system runs on AWS EC2 (eu-north-1 — Stockholm):

| Component | Details |
|---|---|
| **React Frontend** | http://13.49.7.145:3000 |
| **Streamlit Dashboard** | http://13.49.7.145:5000 |
| **API** | http://13.49.7.145:8000/api/v1 |
| **Server** | AWS EC2, eu-north-1a, instance ID: i-08bd901b0a0efefad |
| **Database** | PostgreSQL 16 with pgvector |
| **Cache** | Redis 7 |

**SSH access:**
```bash
ssh -i ~/.ssh/phoenician-bastion.pem ubuntu@13.49.7.145
```

**Check live logs:**
```bash
ssh -i ~/.ssh/phoenician-bastion.pem ubuntu@13.49.7.145 \
  "docker logs screening-engine-mcp-server-1 --tail 50 -f"
```

**Deploy latest code (frontend):**
```bash
ssh -i ~/.ssh/phoenician-bastion.pem ubuntu@13.49.7.145 \
  "cd ~/screening-engine && git pull && \
   docker compose build frontend --no-cache && \
   docker compose up -d frontend"
```

**Deploy latest code (backend):**
```bash
ssh -i ~/.ssh/phoenician-bastion.pem ubuntu@13.49.7.145 \
  "cd ~/screening-engine && git pull && docker compose restart mcp-server"
```

**Clear database (fresh start) via API:**
```bash
curl -X POST http://13.49.7.145:8000/api/v1/screening/reset-db
```

**Or via SSH:**
```bash
ssh -i ~/.ssh/phoenician-bastion.pem ubuntu@13.49.7.145 \
  "docker exec screening-engine-db-1 psql -U phoenician -d phoenician -c \
  'SET session_replication_role = replica;
   TRUNCATE TABLE recommendations, metrics, scoring_runs, documents, insider_purchases CASCADE;
   DELETE FROM companies;
   SET session_replication_role = DEFAULT;'"
```

**Trigger a run without browser (browser-independent):**
```bash
curl -X POST http://localhost:8000/api/v1/screening/run \
  -H "Content-Type: application/json" \
  -d '{"max_companies": 50}'
```

**Check run status:**
```bash
curl -s http://localhost:8000/api/v1/screening/status
```

**Monitor logs via CloudWatch:**

AWS Console → CloudWatch → Log Groups → **screening-engine-dashboard** → dashboard

---

*Questions? Contact the Investment Technology team.*
*Confidential — Internal Use Only*
