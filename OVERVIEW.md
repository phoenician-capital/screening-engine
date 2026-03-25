# Phoenician Capital — Screening Engine
## User Guide & Reference Manual

*Version 4.0 | March 2026 | CONFIDENTIAL — Internal Use Only*

---

## 1. What It Does

The Screening Engine is Phoenician Capital's proprietary AI-powered investment research platform. In a single click, it:

1. Discovers global companies that match our investment criteria
2. Ingests their financial data from SEC EDGAR and FMP
3. Scores and ranks them against our 6-dimension framework
4. Generates a full investment memo for each top candidate
5. Saves the top results to a database for review

The system runs on a dedicated AWS server (eu-north-1, Stockholm) and is accessible at:

**http://13.49.7.145:5000**

---

## 2. Three Pages

The dashboard has exactly three pages — kept simple by design.

### Page 1 — Run Screening

One button. Click **Run Screening** and the engine does everything:

```
Step 1 — Discover
  Fetches the full universe of ~2,500 global companies from EDGAR + curated international list
  Sends the entire list to Claude AI with our investment mandate and portfolio context
  Claude selects the best 100–200 candidates based on Phoenician's criteria

Step 2 — Ingest
  Fetches financials for each Claude-selected company from FMP (revenue, margins, ROIC, FCF)
  Falls back to Claude web search for international companies not covered by FMP

Step 3 — Score & Rank
  Runs every company through our 6-dimension scoring framework
  Generates a full AI-written investment memo for each qualifying company
  Ranks by composite score

Step 4 — Save
  Writes top results to the database
  Results immediately visible in the Results page
```

**How long it takes:** ~3–5 minutes for 50 companies.

**Max Companies:** Set this number in the input box. 20 is fast (2–3 min), 50 is thorough (5–7 min).

---

### Page 2 — Results

Shows every company that passed the hard filters and received a score, ranked best to worst.

**Table columns:**

| Column | What it means |
|---|---|
| # | Rank (1 = best composite score) |
| Ticker | Stock ticker symbol |
| Company | Full company name |
| Mkt Cap | Market capitalisation |
| Fit | Fit Score (0–100) — how well the company matches our criteria |
| Risk | Risk Score (0–100) — 0 is lowest risk, 100 is highest |
| Score | Composite rank score = 70% × Fit − 30% × Risk |
| Gross Mgn | Gross profit margin |
| ROIC | Return on invested capital |
| FCF Yld | Free cash flow yield |
| Rev Gth | Revenue growth year-over-year |
| ND/EBITDA | Net debt / EBITDA (leverage) |
| Status | Pending / Research / Watch / Rejected |
| Action | Buttons to act on the company |

Click any row to expand the full investment memo and scoring breakdown.

---

### Page 3 — Settings

Adjust the screening criteria without touching any code. Changes take effect on the next run.

**Hard Filters** (pass/fail gates — companies that fail are excluded entirely):
- Market cap range (default $100M–$10B)
- Gross margin floor (default 15%)
- Excluded sectors (default: Energy, Utilities, Real Estate)
- Excluded countries (China, Russia, Iran, North Korea, Syria, Belarus)
- Profitability requirement

**Scoring Weights** (tune the 6-dimension framework):
- Founder & Ownership (default 20%)
- Business Quality (default 25%)
- Unit Economics (default 20%)
- Valuation (default 15%)
- Information Edge (default 10%)
- Scalability (default 10%)

**Portfolio Holdings** — view and manage your 19 tracked companies. These are used to give Claude context when pre-screening candidates ("find companies similar in quality to what we own").

---

## 3. Scoring Framework

### Hard Filters (Round 1 — Pass/Fail)

Companies that fail any of these are eliminated before scoring:

| Filter | Threshold |
|---|---|
| Market cap | $100M – $10B |
| Gross margin | ≥ 15% |
| Sector | No banks, REITs, utilities, energy |
| Country | No China, Russia, Iran, North Korea, Syria, Belarus |
| Profitability | Net income must not be deeply negative |

### Fit Score (Round 2 — 0 to 100)

Six dimensions, each scored 0 to their maximum:

| Dimension | Max Points | What It Measures |
|---|---|---|
| **Founder & Ownership** | 20 | Founder-led CEO, insider stake ≥10%, recent insider buying on Form 4, cluster buying near 52-week low |
| **Business Quality** | 25 | Gross margin (≥50% ideal), operating margin (≥15% ideal), ROIC (≥15% ideal), revenue growth (≥8% ideal) |
| **Unit Economics** | 20 | FCF yield (≥5% ideal), FCF/Net Income ratio ≥0.7, positive FCF, CapEx/Revenue <10% |
| **Valuation** | 15 | EV/EBITDA (≤12x ideal), PEG ratio (≤1.5 ideal), Price/FCF (≤20x ideal) |
| **Information Edge** | 10 | Market cap in $300M–$3B sweet spot, AI-assessed as under-followed |
| **Scalability** | 10 | Recurring revenue, international diversification, AI scalability assessment |

**Total maximum: 100 points.**

In practice, scores above 50 indicate strong alignment. The system currently shows all qualifying companies regardless of score — you can filter in Settings.

### Risk Score (Round 3 — deductions)

Calculated independently from Fit. Lower is better (0 = no risk flags):

- Leverage: Net Debt/EBITDA ≥ 4x adds risk points
- Profitability: Negative net income adds risk points
- Geopolitical: Emerging market domicile adds risk points
- Red flags: Customer concentration, litigation, restatements

### Insider Buying Bonus

On top of the Fit Score, insider buying signals score points:
- Transaction ≥ $50K (meaningful)
- Transaction ≥ $1M (strong)
- CEO/Chairman buyer preferred
- Cluster buying: 2+ insiders within 14 days
- Repeat buying within 3 months
- Purchase increases insider holding by >10%

### Final Rank Score

```
Rank Score = (70% × Fit Score) − (30% × Risk Score)
```

Companies are displayed in descending Rank Score order.

---

## 4. Data Sources

| Source | What It Provides | Coverage |
|---|---|---|
| **SEC EDGAR** | Company universe, CIK numbers, financial XBRL data, Form 4 insider transactions | ~7,000 US public companies |
| **FMP (Financial Modeling Prep)** | Income statement, cash flow, key metrics, ratios, company profile | US + major international |
| **Claude AI (Anthropic)** | Pre-screens 2,500 candidates to best 100, writes investment memos, LLM fallback for international financials | Global |
| **Curated International List** | 157 vetted international companies across Scandinavia, Poland, Japan, Australia, Singapore, etc. | Non-US exchanges |

---

## 5. Investment Memos

The system generates a full investment memo for every company that passes the hard filters. Memos are written by Claude AI using actual financial data and our investment framework.

Each memo contains:

1. **Business Model** — What the company does, how it makes money, competitive position
2. **Fit Score Analysis** — Commentary on each of the 6 scoring dimensions
3. **Financial Highlights** — Revenue, margins, ROIC, FCF, leverage with context
4. **Key Strengths** — Top 3–5 compelling aspects
5. **Key Risks** — Top 2–3 concerns with context
6. **Valuation** — Where the company trades and whether it's reasonable
7. **Verdict** — Whether this fits Phoenician's mandate and why

Memos are generated by AI and should be treated as a **research starting point, not a final recommendation.** Always verify key claims against primary sources.

---

## 6. Portfolio Monitor

The Portfolio Monitor page tracks all 19 of Phoenician's current holdings:

**IR Events** — Scans each company's investor relations website for new events (earnings dates, presentations, press releases). Click **Scan IR Sites Now** to refresh. Covers all languages including Japanese, Finnish, Polish.

**SEC 8-K Signals** — Monitors SEC filings for material events: CEO changes, buyback announcements, earnings guidance, restatements.

**Portfolio Analogs** — Companies found by the screening engine that are similar in quality profile to your existing holdings. Tagged "via [ticker]" to show which holding inspired the find.

---

## 7. What the System Does and Does Not Do

### Does

- Discovers, scores, and ranks global companies against Phoenician's criteria
- Generates detailed AI-written investment memos
- Monitors portfolio company IR websites and SEC filings
- Learns from the portfolio context to find similar-quality ideas
- Runs on a dedicated server — no timeouts, no usage limits

### Does Not

- Make buy or sell recommendations
- Execute trades or connect to any brokerage
- Replace fundamental analysis (memos are a starting point)
- Guarantee data accuracy (AI analysis must be verified)
- Store material non-public information

---

## 8. Deployment

The system runs on AWS EC2 (eu-north-1 — Stockholm):

| Service | Details |
|---|---|
| **Dashboard** | http://13.49.7.145:5000 |
| **Server** | AWS EC2 t3.small, eu-north-1a |
| **Database** | PostgreSQL 16 with pgvector, 30GB EBS |
| **Cache** | Redis 7 |
| **Cost** | ~$15/month |

To SSH into the server:
```
ssh -i ~/.ssh/phoenician-bastion.pem ubuntu@13.49.7.145
```

To check logs:
```
ssh ubuntu@13.49.7.145 "docker logs screening-engine-dashboard-1 --tail 50"
```

To update to latest code:
```
ssh ubuntu@13.49.7.145 "cd /home/ubuntu/screening-engine && git pull && docker compose build dashboard && docker compose up -d dashboard"
```

---

*Questions? Contact the Investment Technology team.*
*Confidential — Internal Use Only*
