# Phoenician Capital — Screening Engine
## Analyst Work Paper: System Guide & Reference Manual

*Version 3.0 | March 2026 | CONFIDENTIAL — Internal Use Only*

---

## 1. Purpose

The Screening Engine is Phoenician Capital's proprietary investment research platform. It continuously discovers, analyzes, scores, and ranks public companies against our investment criteria. The system delivers daily and weekly investment ideas with full citation-backed memos, and learns from your feedback to improve its recommendations over time.

This work paper explains how the system works and what is expected of you as an analyst interacting with it daily.

---

## 2. Investment Universe

The engine screens global public equities (all exchanges except mainland China, Russia, and Iran) within the following target range:

| Parameter | Criteria |
|-----------|----------|
| Market Cap | $100 million – $10 billion |
| Geographies | Global, excluding China, Russia, and Iran |
| Excluded Sectors | Energy, Utilities, Biotech / early-stage pharma |
| Leverage Limit | Net Debt / EBITDA < 5x |
| Gross Margin Floor | > 20% |

Companies that fail any of these hard filters are automatically excluded before scoring begins.

---

## 3. Scoring Framework

Every company that passes the hard filters receives two independent scores.

### 3.1 Fit Score (0–100)

The Fit Score measures how well a company matches our investment philosophy across six dimensions:

| Dimension | Max | What It Measures |
|-----------|-----|-----------------|
| Founder & Ownership | 16.67 | Founder-led, insider stake (>5% ideal), recent insider buying on Form 4 |
| Business Quality | 16.67 | Gross/operating margins, ROIC, revenue growth, margin expansion trajectory |
| Unit Economics | 16.67 | FCF yield, earnings quality (FCF vs. net income), capital-light model |
| Valuation | 16.67 | EV/EBITDA relative to growth, PEG ratio, price-to-FCF |
| Information Edge | 16.67 | Low analyst coverage (<5 analysts), sweet-spot market cap ($500M–$3B) |
| Scalability | 16.67 | Total addressable market, recurring revenue percentage, international runway |

A perfect Fit Score is 100. In practice, scores above 65 indicate strong alignment with our criteria.

### 3.2 Risk Score (0–100)

The Risk Score is calculated independently and captures downside factors:

- Leverage and debt maturity risk
- Earnings quality concerns (large gap between reported earnings and cash flow)
- Customer or revenue concentration
- Regulatory and litigation exposure
- Management credibility (turnover, governance red flags)
- Geographic and currency risk

A Risk Score of 0 is best (lowest risk). Scores above 50 warrant extra caution.

### 3.3 Final Ranking

Companies are ranked using a composite formula:

> **Rank = (50% × Fit Score) − (50% × Risk Score)**

These weights (50/50) are starting values and can be adjusted from the Settings page. The system also adjusts them automatically based on your feedback patterns over time (see Section 7).

---

## 4. Data Sources

The engine ingests data from multiple sources to build a comprehensive picture of each company:

| Source | Data Collected | Used For |
|--------|---------------|---------|
| **SEC EDGAR** | 10-K, 10-Q, 8-K filings; Form 4 insider transactions; XBRL financial facts | Financials, insider ownership, filing activity |
| **FMP API** | Company profiles, financial ratios, key metrics, income statements, cash flows | Universe building, enrichment, global coverage |
| **Earnings Transcripts** | Full call transcripts with prepared remarks and Q&A | Management tone, guidance, recurring revenue signals |
| **News APIs** | Recent news from NewsAPI, Finnhub, and Google News | Sentiment, catalysts, risk events |
| **Claude AI** | Qualitative analysis of all ingested documents | Business quality assessment, moat identification, management evaluation |
| **FactSet (optional)** | Premium fundamentals, ownership data, screening | Enhanced data quality where available |

All data points used in analysis are tracked as source documents. When you see a citation number in a memo (e.g., [1], [2]), it refers to a specific filing, transcript, or news article that you can trace back.

---

## 5. Using the Dashboard

The web dashboard is your primary interface for interacting with the Screening Engine. It runs at http://localhost:5000 and has eight pages.

### 5.1 Rankings Page

This is the main view. You will see a ranked list of companies sorted by their composite score. Each row shows the ticker, company name, Fit Score, Risk Score, and Rank. Colored pills show the score for each of the six dimensions at a glance.

For each company, you have three action buttons:

- **Research Now** — Flags the company for deeper work. Use this when a name looks promising and you want to move it into your active research pipeline.
- **Watch** — Adds the company to your watchlist. Use this for names that are interesting but not immediately actionable (e.g., waiting for a catalyst, need next quarter's numbers).
- **Reject** — Removes the company from consideration. You must select a reason from the dropdown (e.g., "Too expensive," "Weak moat," "Poor management"). You can also add a free-text note.

Click any company row to expand its investment memo inline, or click "Full Detail" to open the deep-dive page.

### 5.2 Company Detail Page

Accessed by clicking a ticker or "Full Detail." This page shows the complete picture: a visual bar chart of all six Fit Score dimensions, the full investment memo with numbered citations, key financial metrics, your feedback history for this company, and a list of all ingested documents (filings, transcripts, news) with dates.

### 5.3 Watchlist Page

Shows all companies you've marked "Watch." Each entry shows the date added and any notes. From here, you can promote a company to "Research Now" or remove it from the watchlist.

### 5.4 Analytics Page

This page gives you insight into your own decision patterns and how the system is adapting. It shows your research rate (what percentage of presented names you advance), your most common reject reasons (as a bar chart), the current scoring weights for each dimension (which may differ from the defaults if the system has adjusted them), the full weight evolution history, and a feed of your recent actions.

### 5.5 Pipeline Runner Page

A control panel for manually triggering system operations. In normal use, the scheduler runs everything automatically. But you can use this page to run an ad-hoc daily or weekly scoring cycle, score a specific ticker on demand, trigger a discovery search (market, similarity, or thematic), generate memos for specific companies, or manually run the feedback-loop weight adjustment.

### 5.6 Settings Page

The Settings page gives you full control over the screening parameters without touching any code or config files. From this page you can:

- **Adjust or disable hard filters** — For example, you can lower the gross margin floor from 20% to 10%, or turn it off entirely to let low-margin, high-growth companies through.
- **Change the market cap range** — Widen or narrow the investable universe (e.g., raise the minimum to $500M, or expand the maximum to $15B).
- **Add or remove excluded sectors and industries** — Drop "Energy" from the exclusion list, or add "Real Estate."
- **Tune scoring dimension weights and thresholds** — Increase the weight on insider ownership, raise the bar for what counts as "strong" revenue growth, adjust the FCF yield floor, etc.
- **Modify the ranking formula** — Change the Fit/Risk weighting (e.g., 60/40 instead of 50/50) to prioritize upside over risk avoidance or vice versa.
- **Control output settings** — Change how many ideas appear in the daily email digest.
- **Configure Phoenician Intelligence** — Enable/disable the PI integration, set the API endpoint and key (see Section 5.8).
- **Tune Insider Buying Tracker** — Adjust the lookback window and minimum transaction size for insider purchase scanning.

Each filter has an on/off toggle. When you disable a filter (for example, the gross margin floor), the system will no longer eliminate companies based on that criterion. All changes are saved immediately and take effect on the next scoring run. You do not need to restart anything — just click "Save All Changes" and the next daily or manual run will use the updated parameters.

This is especially useful when you want to explore a specific thesis. For instance, if you want to look at high-growth software companies regardless of current margins, you can temporarily disable the gross margin filter, run a scoring cycle from the Pipeline page, review the results, and then re-enable the filter when you're done.

### 5.7 Insider Buying Page

The Insider Buying page is a dedicated view of insider purchase activity across the screener's universe. The system scans SEC Form 4 filings daily and extracts open-market share purchases by company officers and directors.

The page has three sections:

- **Cluster Buys** — Highlighted at the top. A cluster buy means two or more insiders bought the same stock within a 14-day window. This is one of the strongest insider signals because it suggests coordinated conviction across multiple people with inside knowledge.
- **Highest Conviction** — Individual purchases ranked by a 0–100 conviction score. The score weighs the dollar amount (CEO spending $1M scores higher than a director spending $50K), the insider's role (CEO/Chair > CFO > Director), whether it's a cluster buy, and the frequency of recent buying.
- **Full Feed** — A sortable table of all insider purchases in the lookback window, with ticker, insider name, title, shares, price, total value, conviction score, cluster flag, and date.

Each row has "Research" and "Watch" buttons so you can act on insider buying signals directly. There is also a "Filing" link that opens the original SEC Form 4 document. You can click "Scan Now" to trigger an immediate scan, but the system also runs this automatically every morning as part of the daily cycle.

### 5.8 Price Alerts Page

The Price Alerts page lets you set price targets on any company. When a stock trades at or below your target level, the system flags it so you can revisit the name at a more attractive entry point.

There are three sections on this page:

- **Triggered Alerts** — Shown in red at the top. These are companies whose stock has hit or dropped below your target price. Each triggered alert shows the target you set, the price it triggered at, and how far below target it traded. You can click "Research Now" (which also sends to PI if enabled), "Watch," or "Dismiss" to acknowledge the alert.
- **Active Targets** — A table of all your current price targets showing the ticker, your target price, the current market price, the distance to your target (as a percentage), your notes, and the expiration date. Rows turn amber when the stock is within 15% of your target, and red when within 5%. You can edit or remove any target.
- **Alert History** — A log of all past triggered alerts for your records.

To set a new target, click "+ Set Price Target" and enter the ticker, the price you'd like to buy at, a note explaining your rationale (e.g., "Wait for pullback to 15x FCF"), and an optional expiration. The system checks all active targets every morning during the daily cycle. You can also trigger a manual check from the Pipeline page.

This is especially useful for companies you liked but felt were too expensive. Instead of losing track of them, set a price target and let the system tell you when the market gives you a better entry.

### 5.9 Phoenician Intelligence Integration

When the Phoenician Intelligence (PI) integration is enabled in Settings, clicking "Research Now" on any company does two things: it records your feedback (as before), and it automatically sends a due diligence request to the Phoenician Intelligence platform.

The request includes the ticker, company name, exchange, and — if you have "Send Screener Data" enabled — the company's current scores, dimension breakdown, and a summary of the investment memo. This gives PI the context it needs to start a targeted diligence workflow without you having to re-enter any information.

You can configure the PI endpoint URL, API key, and other settings from the Settings page. If PI is not enabled, the "Research Now" button works exactly as before — it just records your feedback without making any external call.

---

## 6. Investment Memos

The system generates 1–2 page investment memos for top-ranked companies. Each memo follows a consistent structure:

1. **Investment Thesis** — A concise summary of why this company fits our criteria.
2. **Phoenician DNA Fit** — How the company maps to each of our six scoring dimensions.
3. **Key Strengths** — The 3–5 most compelling aspects of the business.
4. **Primary Risks** — The 3–5 biggest concerns, with context.
5. **Valuation Context** — Where the company trades relative to peers and history.
6. **Due Diligence Checklist** — Specific items to investigate further.
7. **Recommended Action** — Research Now, Watch, or Pass, with reasoning.
8. **Sources** — Numbered list of all documents cited in the memo.

Every factual claim in the memo includes a citation number (e.g., [1]) that maps to the Sources section. This lets you verify any statement by going directly to the original filing, transcript, or article. The memos are generated by AI and should be treated as a research starting point, not as a final recommendation.

---

## 7. The Feedback Loop

Your feedback directly improves the system.

### 7.1 How Your Actions Train the System

Every time you click Research Now, Watch, or Reject, the system records your decision along with the company's current scores across all six dimensions. Over time, this builds a dataset of your revealed preferences.

### 7.2 How Weights Adjust

Periodically, the feedback loop analyzes the pattern of your decisions. If a particular scoring dimension is consistently associated with companies you reject, its weight decreases. If it's associated with companies you advance to research, its weight increases. Adjustments are conservative: a maximum of ±2 points per cycle per dimension, and each dimension has a floor of 5 and a ceiling of 35. The total always remains 100 points.

### 7.3 Example

Suppose you keep rejecting companies that score highly on Valuation but poorly on Business Quality — that is, cheap but low-quality names. The system will gradually reduce the Valuation weight and increase the Business Quality weight, so future rankings better match your actual preferences.

### 7.4 Why Reject Reasons Matter

When you reject a company, the reason you select is critical. Each reason maps to a specific scoring dimension:

| Reject Reason | Affects Dimension |
|--------------|------------------|
| Too expensive | Valuation |
| Weak moat / low quality | Business Quality |
| Poor unit economics | Unit Economics |
| No insider alignment | Founder & Ownership |
| Too well-covered | Information Edge |
| Limited growth runway | Scalability |
| Too risky | Risk Score |
| Already known / duplicate | No weight impact |

Selecting accurate reject reasons ensures the system learns the right lessons from your decisions.

---

## 8. Company Discovery

Beyond re-scoring the existing universe, the system actively discovers new companies through three strategies:

### 8.1 Market Screening

Scans all global exchanges for companies in our target market cap range that aren't already in the database. New names are automatically ingested and scored.

### 8.2 Similarity Search

Given a company you like, the system finds others in the same sector with similar size, growth, and margin profiles. Use this when you find a compelling name and want to explore the neighborhood.

### 8.3 Thematic Search

Describe a theme in plain English (e.g., "companies benefiting from nearshoring trends in Mexico" or "enterprise software with 90%+ recurring revenue") and the AI interprets it into screening criteria, then finds matching companies. This is available from the Pipeline Runner page.

---

## 9. Your Daily Workflow

**Morning (after 6:30 AM ET):** Check your email for the daily screening report. It will contain the top-ranked ideas with score cards and brief AI snapshots. Flag anything that catches your eye.

**Insider Buying Check:** Open the Insider Buying page. Look at Cluster Buys first — these are the strongest signals. Check if any high-conviction purchases overlap with names on your Rankings or Watchlist. Research or Watch any that catch your attention.

**Dashboard Review:** Open the Rankings page. Review the top 10–15 names. For each, read the inline memo and make a decision: Research Now, Watch, or Reject (with reason). Aim to act on at least 5–10 names per day. When you click "Research Now," the system automatically sends a due diligence request to Phoenician Intelligence (if enabled).

**Deep Dives:** For companies you mark "Research Now," a full Phoenician Due Diligence is already being prepared in PI. In the meantime, open the Company Detail page in the screener to review the scoring breakdown, memo, and citations.

**Watchlist Check (weekly):** Review the Watchlist page. Has anything changed for the names you're tracking? Promote, keep, or remove.

**Analytics (weekly):** Check the Analytics page to see how the system is adapting to your preferences. Review the weight evolution chart to make sure it's trending in a direction that makes sense.

---

## 10. Automated Schedules

| Schedule | Timing | What Happens |
|----------|--------|-------------|
| **Daily** | Weekdays, 6:30 AM ET | Re-scores universe, checks for new filings and news, generates 5 new memos, sends email digest, runs feedback loop adjustment |
| **Weekly** | Mondays, 5:00 AM ET | Full discovery scan across all exchanges, ingests new companies, re-scores expanded universe, generates 20 memos, sends expanded email report |

Both schedules run automatically. You do not need to trigger them manually unless you want an ad-hoc run from the Pipeline Runner page.

---

## 11. Claude Desktop Integration

If your Claude Desktop app is configured with the Screening Engine MCP server, you can interact with the system conversationally. Examples of things you can ask:

- "Show me the current top 10 rankings."
- "What's the scoring breakdown for DDOG?"
- "Find companies similar to FIVE."
- "Mark PAYC as Research Now with a note about their Q4 margins."
- "What are the most common reject reasons this month?"
- "Search for companies benefiting from AI infrastructure buildout."

This gives you a conversational interface to the same system the dashboard provides, useful for quick lookups or when you want to ask follow-up questions.

---

## 12. Important Notes

### What This System Does

- Discovers, scores, and ranks companies against Phoenician's investment criteria.
- Generates citation-backed investment memos as a research starting point.
- Learns from your feedback to improve recommendations over time.
- Automates the initial screening layer so you can focus on deep research.

### What This System Does Not Do

- It does not make buy/sell recommendations. All output is for research purposes.
- It does not execute trades or interface with any brokerage or OMS.
- It does not replace fundamental analysis. Memos are a starting point, not a conclusion.
- It does not guarantee accuracy. AI-generated analysis should always be verified against primary sources.
- It does not store material non-public information. All data comes from public sources.

### Best Practices

- Be consistent with your feedback. The system learns fastest when you act on names regularly.
- Always select a reject reason, not just "Reject." The reason is what drives the learning.
- Check the Analytics page periodically to see how weights are evolving.
- Use thematic discovery when you have an investment thesis you want to explore.
- Treat memos as hypotheses to test, not conclusions to accept.

---

*Questions? Contact the Investment Technology team.*
