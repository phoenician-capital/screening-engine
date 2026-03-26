# Screening Engine — What Changed
## Old Logic vs New Logic

*March 2026 | CONFIDENTIAL — Internal Use Only*

---

## Summary

The screening engine has been rebuilt from the ground up. The core change is a shift from a brittle, quota-limited pipeline to a genuinely intelligent, production-grade system. Claude now acts as a real analyst — not just a label. The scoring model no longer penalises companies for data we don't have. The infrastructure runs on dedicated AWS hardware with no timeouts. Every component was rethought.

---

## 1. Universe Discovery

### Before
- Random sample of 50–200 companies from EDGAR
- Hard-coded cap: Claude could only pick 100–200 max
- International: 25 companies from a hardcoded list
- Processed all 2,400+ US tickers blindly to find 50 qualifying ones
- No portfolio context given to discovery

### Now
- Full 2,560 global companies (2,403 US + 157 international) sent to Claude in one call
- **No cap** — Claude decides how many to select (typically 300–500)
- Claude receives Phoenician's full investment mandate, philosophy, and all 19 portfolio holdings
- Claude acts as an intelligent filter: eliminates banks, miners, utilities, debt instruments, Chinese ADRs
- Only selected companies get financial data fetched — no wasted API calls
- Portfolio context means Claude actively avoids duplication and seeks similar-quality ideas

**Impact:** 10x better candidate quality. Claude surfaces companies a random sampler would never find.

---

## 2. International Financial Data

### Before
- Source: Claude web search (LLM fallback)
- Success rate: ~60% (40% returned empty responses or failed)
- Data quality: Hallucinated revenue figures, wrong margins, inconsistent JSON
- Market cap: Always showed **$500M placeholder** for every international company
- Speed: ~20–30 seconds per company (Claude search latency)

### Now
- Source: **Yahoo Finance Timeseries API** (free, no authentication required)
- Success rate: ~90%+
- Data: Real structured annual data — revenue, gross profit, net income, operating income, FCF, capex
- Works for Sweden, Poland, Japan, Australia, Canada, UK, Netherlands, Denmark, Finland, Germany, Greece, Singapore
- Last resort: Claude web search only if Yahoo also fails
- Speed: ~0.5–1 second per company (direct API call)

**Impact:** International companies now have real financial data. Polish, Scandinavian, and Japanese companies score accurately instead of showing — everywhere.

---

## 3. Scoring Model — Core Philosophy Change

### Before — Deduction Model
```
Start at 100 points
Lose points when criteria fail OR data is missing
→ Company with no founder data: loses 8 pts (founder criterion)
→ Company with no analyst count: loses 6 pts (information edge)
→ Company with no recurring revenue data: loses 6 pts (scalability)
Result: Every company penalised for data we simply don't have
Scores compressed between 20–58 regardless of quality
```

### Now — Additive Bonus Model
```
Start at 0 points
Earn points when criteria pass AND data is available
Missing data = 0 points added, NOT deducted
Score = earned_points / max_of_available_criteria × 100
→ Company with no founder data: excluded from denominator (neutral)
→ Company with no analyst count: partial credit from market cap size
→ Company with no recurring data: 0 pts, not -6 pts
Result: Companies scored on what we know, never penalised for what we don't
Scores now spread between 30–80+
```

**Impact:** A genuinely high-quality company with incomplete data now scores in the 50–70 range instead of the 25–40 range. Rankings are meaningful.

---

## 4. Scoring Weights

| Dimension | Before | Now | Why Changed |
|---|---|---|---|
| Business Quality | 25% | **30%** | Most measurable — FMP returns margins reliably |
| Unit Economics | 20% | **25%** | FCF, capex all available — key Phoenician criterion |
| Founder & Ownership | 20% | **20%** | Unchanged |
| Valuation | 15% | **15%** | Unchanged |
| Information Edge | 10% | **5%** | Analyst count rarely populated — reduced drag |
| Scalability | 10% | **5%** | Recurring % rarely measurable — reduced drag |

---

## 5. New Scoring Signals

None of these existed before. All are additive bonuses — they can only help a company's score, never hurt it.

| Signal | Max Bonus | Trigger |
|---|---|---|
| **Quality Trifecta** | +5 pts | Gross margin > 50% AND ROIC > 15% AND FCF yield > 5% all at once |
| **Capital Allocation** | +6 pts | Active buybacks, low stock dilution, disciplined M&A spending |
| **Balance Sheet Quality** | +5 pts | Net cash position, strong current ratio, low goodwill as % of assets |
| **Earnings Integrity** | +3 pts | Accounts receivable growing in line with revenue (no channel stuffing) |
| **Sector-Relative Valuation** | — | EV/EBITDA compared to sector median in DB, not absolute threshold |
| **Recurring Revenue NLP** | — | Company description scanned for: subscription, SaaS, recurring, maintenance contract, ARR |
| **Founder Detection** | — | FMP CEO name + IPO date: CEO last name in company name, or company < 20 years old |

---

## 6. Risk Scoring

### Before
- Almost every company scored **Risk = 0** (meaningless)
- Leverage check only fired if `net_debt_ebitda` was directly populated (null for most international companies)
- Binary profitable/unprofitable check
- Short excluded-country list — otherwise 0 geographic risk
- No valuation risk check

### Now
- **Minimum risk floor of 5** — no investment is zero risk
- Leverage inferred from net debt + net income if direct ratio missing
- Profitability tiered: negative NI = full risk, thin margins = partial risk, strong margins = 0 risk
- **4 jurisdiction tiers:**
  - High risk: China, Russia, Iran, North Korea, Syria, Belarus
  - Elevated risk: Brazil, India, Mexico, Indonesia, Turkey
  - Moderate risk: Israel, Poland, Greece, Argentina, Thailand
  - Low risk: US, UK, Germany, Sweden, Japan, Singapore, etc.
- Earnings quality: negative FCF with positive NI = red flag
- Valuation risk: EV/EBIT > 50x = priced for perfection flag

**Impact:** Risk scores now range 5–40 meaningfully. A highly leveraged Brazilian company scores very differently from a net-cash Swedish compounder.

---

## 7. Hard Filters

| Filter | Before | Now |
|---|---|---|
| Min market cap | $100M | **$250M** — better liquidity |
| Sector exclusion | GICS codes only ("40", "60") | GICS codes **AND** text names ("Financials", "Real Estate", "Financial Services") |
| Debt instruments | Not filtered | Bonds, debentures, subordinated notes, preferred shares, warrants all excluded |
| ETFs / Funds | Not filtered | Excluded |
| BDCs / Closed-end funds | Slipped through | Excluded (no income statement = no score) |
| Pre-revenue biotechs | Slipped through | Excluded (no revenue + no assets = skipped) |

---

## 8. Results Page

| Feature | Before | Now |
|---|---|---|
| Companies shown | Dropdown: 10/25/50/100 | All qualifying companies — no cap |
| Duplicate companies | Same ticker could appear twice | Deduplicated — best score per ticker only |
| Filters | Search, Min Fit, Max Risk, Status | + **Sector filter** + **Sort** (Score / Fit / Risk / Market Cap) |
| Sorting | Insertion order | Always Rank Score descending |
| Re-ranking | Per run only | **All accumulated companies re-ranked together after every run** |
| International market cap | $500M placeholder | Real market cap where available |

---

## 9. Run Stability

### Before
- Browser refresh = **run killed**, all progress lost
- Render timeout = **run killed** after 30 seconds of no HTTP activity
- Session reset = all job state lost
- Second button click = could spawn two simultaneous runs
- Could not resume a run mid-way

### Now
- **Global job state** stored at Python module level — survives any browser action
- Run continues in background thread regardless of what the browser does
- Page reconnects to in-progress run on refresh
- Blocked: clicking Run Screening while a run is active does nothing
- EC2 server has no request timeouts — runs to completion regardless of length

---

## 10. Infrastructure

| Component | Before | Now |
|---|---|---|
| Hosting | Render free/starter (30s timeout) | **AWS EC2 t3.small, eu-north-1 (Stockholm)** |
| Database | Supabase free tier (IPv6 issues, connection drops, session pooler errors) | **PostgreSQL 16 directly on EC2** |
| No timeout | No | Yes — EC2 runs indefinitely |
| Monitoring | SSH into server manually | **AWS CloudWatch** — live log streaming |
| Cost | $0 but unreliable | **~$15/month** — dedicated, always on |
| Log access | `docker logs` via SSH only | CloudWatch console at eu-north-1 |
| Deployment | `git push` + Render auto-deploy | `git pull` + `docker compose build` on EC2 |

---

## 11. Data Sources Summary

| Source | Before | Now | Purpose |
|---|---|---|---|
| SEC EDGAR | Universe + US financials | Universe + US financials | US company list, XBRL financials |
| FMP | US financials (free, 429s constantly) | US + some international (paid key) | Primary US financial data |
| Yahoo Finance | Blocked from server, unusable | **Yahoo Finance Timeseries** (new) | International annual financials |
| LLM (Claude) | International financials (60% failure) | Last-resort fallback only | When both FMP and Yahoo fail |
| Claude AI | 100-company cap, no portfolio context | 300–500 picks, full mandate + portfolio | Universe pre-screening |
| SEC EDGAR Form 4 | Insider transactions | Insider transactions | Buying signals |

---

## Net Result

| Metric | Before | Now |
|---|---|---|
| Score range | 20–58 (compressed) | 30–80+ (meaningful spread) |
| Risk scores | Almost always 0 | 5–40 (realistic) |
| International data | 40% failure rate | 90%+ success |
| Run completion rate | ~30% (timeouts, crashes) | ~95%+ |
| Companies per run | 50 (hard cap) | 200+ (Claude decides) |
| Duplicate results | Common | Eliminated |
| Market cap accuracy | $500M placeholder for intl | Real data |
| Monitoring | Manual SSH | CloudWatch |

---

*Confidential — Internal Use Only*
*Phoenician Capital Investment Technology*
