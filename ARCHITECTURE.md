# Phoenician Capital — Screening Engine Architecture

## Overview

The Screening Engine is Phoenician Capital's proprietary investment research platform. It continuously discovers, scores, and ranks global public equities against the firm's investment criteria — founder-led, high-quality businesses with strong cash generation and reasonable valuations. The system ingests data from multiple sources, applies a transparent six-dimension scoring rubric, generates citation-backed investment memos, and learns from analyst feedback to continuously improve its recommendations.
---

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Data Flow](#data-flow)
3. [Project Structure](#project-structure)
4. [Module Deep Dives](#module-deep-dives)
   - [Configuration](#1-configuration-srcconfig)
   - [Database Layer](#2-database-layer-srcdb)
   - [Shared Utilities](#3-shared-utilities-srcshared)
   - [Data Ingestion](#4-data-ingestion-srcingestion)
   - [Information Extraction](#5-information-extraction-srcextraction)
   - [Scoring Engine](#6-scoring-engine-srcscoring)
   - [RAG System](#7-rag-system-srcrag)
   - [Orchestration](#8-orchestration-srcorchestration)
   - [Feedback Loop](#9-feedback-loop-srcfeedback)
   - [MCP Server](#10-mcp-server-srcmcp_server)
   - [Dashboard](#11-dashboard-srcdashboard)
   - [Prompt Templates](#12-prompt-templates-srcprompts)
5. [Scoring Rubric](#scoring-rubric)
6. [Ranking Formula](#ranking-formula)
7. [Technology Stack](#technology-stack)
8. [Deployment](#deployment)
9. [Investment Universe](#investment-universe)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATION LAYER                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │ Daily Job    │  │ Weekly Job   │  │ Manual Trigger (Dashboard)│ │
│  └──────┬───────┘  └──────┬───────┘  └─────────────┬─────────────┘ │
│         │                 │                         │               │
│         ▼                 ▼                         ▼               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Scoring Pipeline / Memo Pipeline               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         │                    │                      │
         ▼                    ▼                      ▼
┌────────────────┐  ┌─────────────────┐  ┌───────────────────┐
│   INGESTION    │  │    SCORING      │  │   RAG + MEMO      │
│                │  │                 │  │                   │
│ SEC EDGAR      │  │ Hard Filters    │  │ Vector Retriever  │
│ Transcripts    │  │ 6 Criteria      │  │ Memo Generator    │
│ News           │  │ Risk Scorer     │  │ (Claude)          │
│ Market Data    │  │ Ranker          │  │                   │
└───────┬────────┘  └────────┬────────┘  └────────┬──────────┘
        │                    │                     │
        ▼                    ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DATABASE LAYER                              │
│  PostgreSQL 16 + pgvector                                          │
│  ┌──────────┐ ┌─────────┐ ┌───────────┐ ┌────────────┐            │
│  │Companies │ │Metrics  │ │Documents  │ │Embeddings  │            │
│  └──────────┘ └─────────┘ └───────────┘ └────────────┘            │
│  ┌──────────────┐ ┌──────────┐ ┌────────────┐ ┌──────────┐       │
│  │Recommendations│ │Feedback │ │ScoringRuns │ │Watchlist │       │
│  └──────────────┘ └──────────┘ └────────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                          │
│  ┌─────────────────────┐        ┌──────────────────────────┐       │
│  │ MCP Server (FastAPI)│        │ Streamlit Dashboard      │       │
│  │ :8000               │        │ :5000                    │       │
│  │ 8 tool endpoints    │        │ 8 pages                  │       │
│  └─────────────────────┘        └──────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

The system operates in a continuous cycle:

```
STEP 1 — INGEST
  SEC EDGAR + Transcripts + News + Market Data
       │
       ▼
  Store → companies, metrics, documents tables

STEP 2 — EXTRACT
  Documents → LLM extraction (financial metrics + narrative claims)
       │
       ▼
  Chunk documents → generate embeddings → store in pgvector

STEP 3 — SCORE
  For each company in universe:
       │
       ├─ Hard Filters (sector, market cap, leverage) → pass/fail
       ├─ Fit Score (6 criteria → 0–100)
       ├─ Risk Score (6 risk factors → 0–100)
       └─ Rank Score = fit × 0.50 − risk × 0.50 + feedback_adj
       │
       ▼
  Persist ranked recommendations

STEP 4 — GENERATE MEMOS
  Top N recommendations:
       │
       ├─ Vector search → retrieve relevant document chunks
       └─ Claude generates 1–2 page memo with [N] citations
       │
       ▼
  Store memo in recommendation record

STEP 5 — ANALYST REVIEW
  Dashboard presents rankings + memos
       │
       ├─ Analyst actions: Research Now / Watch / Reject
       └─ Feedback stored with reject reasons
       │
       ▼
  Feedback loop adjusts scoring weights for next cycle
```

---

## Project Structure

```
Screening_Engine/
│
├── scripts/                              # CLI entry points
│   ├── init_db.py                        #   Initialize database schema
│   ├── ingest_tickers.py                 #   Ingest specific tickers
│   ├── run_pipeline.py                   #   Run scoring/memo pipeline
│   └── run_server.py                     #   Start FastAPI server
│
├── src/
│   ├── config/                           # Configuration
│   │   ├── settings.py                   #   Env-based settings (DB, Redis, LLM, etc.)
│   │   ├── constants.py                  #   GICS codes, enums, limits
│   │   ├── scoring_weights.yaml          #   Editable scoring criteria weights
│   │   └── scoring_weights.py            #   YAML loader with caching
│   │
│   ├── db/                               # Database layer
│   │   ├── session.py                    #   Async SQLAlchemy engine + session
│   │   ├── models/                       #   10 SQLAlchemy ORM models
│   │   │   ├── base.py                   #     Declarative base
│   │   │   ├── company.py                #     Company master record
│   │   │   ├── metric.py                 #     Financial metrics (time-series)
│   │   │   ├── document.py               #     SEC filings, news, transcripts
│   │   │   ├── embedding.py              #     Vector embeddings (pgvector)
│   │   │   ├── recommendation.py         #     Scored recommendations
│   │   │   ├── scoring_run.py            #     Pipeline execution log
│   │   │   ├── feedback.py               #     Analyst actions
│   │   │   ├── watchlist.py              #     Watched companies
│   │   │   └── exclusion.py              #     Permanently excluded companies
│   │   ├── repositories/                 #   Data access layer (async)
│   │   │   ├── base_repo.py              #     Generic CRUD operations
│   │   │   ├── company_repo.py           #     Upsert, market cap range queries
│   │   │   ├── metric_repo.py            #     Latest metrics, sector medians
│   │   │   ├── document_repo.py          #     By ticker, accession dedup
│   │   │   ├── recommendation_repo.py    #     Top ranked, status updates
│   │   │   └── feedback_repo.py          #     Action counts, reject summaries
│   │   └── migrations/
│   │       └── 001_initial_schema.sql    #   Full DDL + pgvector + indexes
│   │
│   ├── shared/                           # Cross-cutting utilities
│   │   ├── types/
│   │   │   └── schemas.py                #   Pydantic DTOs (CompanyData, ScoringResult, etc.)
│   │   ├── llm/
│   │   │   ├── client_factory.py         #   Unified LLM client (Claude, OpenAI, Google, Perplexity)
│   │   │   └── embeddings.py             #   OpenAI text-embedding-3-small wrapper
│   │   ├── logging/
│   │   │   └── setup.py                  #   Structured logging configuration
│   │   └── utils/
│   │       ├── text.py                   #   Sentence-aware chunking, cleaning
│   │       └── rate_limiter.py           #   Token-bucket async rate limiter
│   │
│   ├── ingestion/                        # Data source connectors
│   │   ├── sources/
│   │   │   ├── sec_edgar/
│   │   │   │   ├── client.py             #     EDGAR full-text search, filing fetch
│   │   │   │   └── parser.py             #     10-K/10-Q section extraction, Form 4
│   │   │   ├── transcripts/
│   │   │   │   └── client.py             #     Earnings call transcripts (Perplexity)
│   │   │   ├── news/
│   │   │   │   └── client.py             #     News search (Perplexity deep-research)
│   │   │   └── market_data/
│   │   │       └── client.py             #     yfinance: company info + financials
│   │   └── workers/
│   │       └── ingestion_worker.py       #   Coordinates ingestion across all sources
│   │
│   ├── extraction/                       # LLM-powered information extraction
│   │   ├── financial/
│   │   │   └── parser.py                 #   Extract revenue, margins, FCF, multiples
│   │   ├── claims/
│   │   │   └── extractor.py              #   Extract moat signals, pricing power, TAM
│   │   └── embeddings/
│   │       └── chunker.py                #   Chunk + embed documents for RAG
│   │
│   ├── scoring/                          # Phoenician Fit Score engine
│   │   ├── filters/
│   │   │   └── hard_filters.py           #   Pass/fail: sector, cap, leverage, margin
│   │   ├── criteria/                     #   6 scoring dimensions (sum to 100)
│   │   │   ├── founder_ownership.py      #     0–20 pts
│   │   │   ├── business_quality.py       #     0–25 pts
│   │   │   ├── unit_economics.py         #     0–20 pts
│   │   │   ├── valuation.py              #     0–15 pts
│   │   │   ├── information_edge.py       #     0–10 pts
│   │   │   └── scalability.py            #     0–10 pts
│   │   └── engine/
│   │       ├── fit_scorer.py             #   Aggregates criteria → composite 0–100
│   │       ├── risk_scorer.py            #   Independent risk assessment → 0–100
│   │       └── ranker.py                 #   Final ranking with feedback adjustment
│   │
│   ├── rag/                              # Retrieval-Augmented Generation
│   │   ├── retriever/
│   │   │   └── vector_retriever.py       #   pgvector cosine similarity search
│   │   └── generator/
│   │       └── memo_generator.py         #   Claude-powered memo with citations
│   │
│   ├── orchestration/                    # Pipeline coordination
│   │   ├── pipelines/
│   │   │   ├── scoring_pipeline.py       #   Full: filter → score → rank → persist
│   │   │   └── memo_pipeline.py          #   Generate memos for top N
│   │   ├── discovery/
│   │   │   └── universe_expander.py      #   Find new companies (3 strategies)
│   │   └── scheduler/
│   │       └── jobs.py                   #   Daily + Weekly automated jobs
│   │
│   ├── feedback/
│   │   └── feedback_loop.py              #   Analyze feedback → adjust weights
│   │
│   ├── mcp_server/                       # FastAPI MCP tool server
│   │   ├── main.py                       #   App factory, router mounting
│   │   ├── middleware/
│   │   │   └── error_handler.py          #   @tool_endpoint decorator
│   │   └── tools/                        #   8 tool endpoints
│   │       ├── sec_filings_tool.py       #     Search/fetch SEC filings
│   │       ├── transcripts_tool.py       #     Fetch earnings transcripts
│   │       ├── news_tool.py              #     Search company news
│   │       ├── extractor_tool.py         #     Extract financials + claims
│   │       ├── embedder_tool.py          #     Embed documents
│   │       ├── vector_tool.py            #     Similarity search
│   │       ├── database_tool.py          #     Query companies, metrics, feedback
│   │       └── scheduler_tool.py         #     Trigger pipelines
│   │
│   ├── dashboard/                        # Streamlit UI
│   │   ├── app.py                        #   Main app with sidebar navigation
│   │   ├── pages/
│   │   │   ├── rankings.py               #     Ranked company list
│   │   │   ├── company_detail.py         #     Deep dive: metrics + memo + scores
│   │   │   ├── watchlist_page.py         #     Watched companies
│   │   │   ├── feedback_analytics.py     #     Precision KPIs, reject distributions
│   │   │   └── pipeline_runner.py        #     Manual ingest/score/memo triggers
│   │   └── components/
│   │       └── db_helpers.py             #     Async DB wrappers for Streamlit
│   │
│   └── prompts/                          # Jinja2 LLM prompt templates
│       ├── loader.py                     #   PromptLoader with load_prompt()
│       ├── extraction/
│       │   ├── parse_financials.j2        #     Financial data extraction prompt
│       │   ├── parse_financials_system.j2 #     System prompt for extraction
│       │   ├── extract_claims.j2          #     Qualitative signal extraction
│       │   └── extract_claims_system.j2   #     System prompt for claims
│       ├── ingestion/
│       │   ├── fetch_transcript.j2        #     Earnings transcript fetch
│       │   ├── fetch_transcript_system.j2
│       │   ├── list_transcripts.j2        #     List available quarters
│       │   ├── list_transcripts_system.j2
│       │   ├── news_search.j2             #     News search query
│       │   ├── news_search_system.j2
│       │   ├── web_read.j2               #     URL content extraction
│       │   ├── web_read_system.j2
│       │   ├── screen_universe.j2         #     Market screener prompt
│       │   └── screen_universe_system.j2
│       ├── discovery/
│       │   ├── similarity_search.j2       #     Find similar companies
│       │   ├── similarity_search_system.j2
│       │   ├── thematic_search.j2         #     Thematic investment queries
│       │   └── thematic_search_system.j2
│       └── memo/
│           ├── memo_system.j2             #     Analyst persona system prompt
│           └── memo_user.j2              #     Full memo structure template
│
├── docker-compose.yml                    # PostgreSQL + Redis + App services
├── Dockerfile                            # Python 3.11-slim container
├── requirements.txt                      # All Python dependencies
├── pyproject.toml                        # Project metadata + ruff config
├── .env                                  # Environment variables (gitignored)
└── .env.example                          # Template for .env setup
```

---

## Module Deep Dives

### 1. Configuration (`src/config/`)

| File | Purpose |
|------|---------|
| `settings.py` | Loads all env vars into frozen dataclasses: `DatabaseSettings`, `RedisSettings`, `LLMSettings`, `VectorStoreSettings`, `IngestionSettings`, `ScoringSettings` |
| `constants.py` | GICS sector/sub-industry codes for exclusion, document type enums, status enums, reject reason codes |
| `scoring_weights.yaml` | Human-editable YAML defining all scoring weights, thresholds, and hard filter parameters. Modified by the feedback loop |
| `scoring_weights.py` | Loads YAML with caching, provides fallback defaults if file is missing |

### 2. Database Layer (`src/db/`)

**10 ORM Models** built on SQLAlchemy 2.0 with UUID primary keys:

| Model | Key Fields |
|-------|------------|
| `Company` | ticker, name, sector, sub_industry, market_cap, gics_code |
| `Metric` | ticker, period, revenue, gross_margin, ebitda, fcf, roic, ev_ebit, net_debt_ebitda |
| `Document` | ticker, doc_type (10-K, 10-Q, 8-K, transcript, news), content, accession_number |
| `Embedding` | document_id, chunk_index, chunk_text, vector (pgvector 1536-dim) |
| `Recommendation` | ticker, fit_score, risk_score, rank_score, rank_position, status, memo |
| `Feedback` | recommendation_id, action (research_now / watch / reject), reject_reason |
| `ScoringRun` | run_id, started_at, completed_at, companies_scored, status |
| `Watchlist` | ticker, added_at, notes |
| `Exclusion` | ticker, reason, excluded_at |

**Repository Pattern**: Each repository wraps async SQLAlchemy queries behind a clean interface. The `BaseRepository` provides generic `get_by_id`, `create`, `create_many`, `delete`, and `commit`.

**Migration**: `001_initial_schema.sql` creates all tables, the pgvector extension, and an IVFFlat index on embeddings for fast similarity search.

### 3. Shared Utilities (`src/shared/`)

**LLM Client Factory** (`client_factory.py`):
- Unified `complete(model, system, user)` function
- Auto-detects provider from model name:
  - `claude-*` → Anthropic API
  - `gpt-*` / `codex-*` → OpenAI API
  - `gemini-*` → Google Generative AI
  - `deep-research` → Perplexity API
- Each provider has its own async implementation

**Embeddings** (`embeddings.py`):
- Wraps OpenAI's `text-embedding-3-small` (1536 dimensions)
- Supports batch embedding for efficiency

**Schemas** (`schemas.py`):
- Pydantic models used as DTOs throughout the system
- `CompanyData`, `MetricData`, `DocumentData`, `ScoringResult`, `CriterionScore`, `RecommendationData`, `Citation`, `MemoOutput`, `FeedbackData`, `ToolResponse`, `ToolError`

### 4. Data Ingestion (`src/ingestion/`)

Four data source connectors, each behind an async client:

| Source | Client | Data Collected |
|--------|--------|----------------|
| **SEC EDGAR** | `SECEdgarClient` | 10-K, 10-Q, 8-K filings; Form 4 insider transactions; XBRL financial facts |
| **FMP API** | `FMPClient` | Company profiles, financial ratios, key metrics, income statements, cash flows; global coverage |
| **Transcripts** | `TranscriptClient` | Earnings call transcripts with prepared remarks and Q&A |
| **News** | `NewsClient` | Recent news via NewsAPI, Finnhub, and Google News |
| **Claude AI** | via `LLMClient` | Qualitative analysis of ingested documents (moat, management, quality signals) |
| **FactSet** *(optional)* | `FactSetClient` | Premium fundamentals, ownership data, screening where available |

The **IngestionWorker** orchestrates ingestion for a batch of tickers:
1. Fetch company info + metrics from yfinance
2. Pull latest SEC filings from EDGAR
3. Fetch recent earnings transcripts
4. Search for relevant news
5. Store everything in the database

### 5. Information Extraction (`src/extraction/`)

After raw documents are stored, extraction pulls structured data:

| Module | Input | Output |
|--------|-------|--------|
| `FinancialParser` | Document text | Revenue, margins, FCF, multiples, growth rates |
| `ClaimExtractor` | Document text | Narrative signals: pricing power, TAM, moat, recurring revenue |
| `Chunker` | Document text | Sentence-aware chunks → embeddings stored in pgvector |

Both parsers use LLM extraction via Jinja2 prompt templates. The extraction model defaults to `gpt-4.1-mini` for cost efficiency.

### 6. Scoring Engine (`src/scoring/`)

#### Hard Filters (Pass/Fail)

Applied before scoring to exclude disqualified companies:

| Filter | Rule |
|--------|------|
| Geography Exclusion | Reject companies listed on mainland China, Russian, or Iranian exchanges |
| Sector Exclusion | Reject Energy (GICS 10), Utilities (GICS 55) |
| Sub-Industry Exclusion | Reject Biotech / early-stage pharma (GICS 35201010) |
| Market Cap Floor | Reject if < $100M |
| Market Cap Ceiling | Reject if > $10B |
| Leverage Cap | Reject if Net Debt / EBITDA ≥ 5x |
| Gross Margin Floor | Reject if ≤ 20% |

#### Fit Score — 6 Criteria (0–100 total)

| # | Criterion | Max Points | Sub-components |
|---|-----------|-----------|----------------|
| 1 | **Founder / Ownership** | 16.67 | Founder-led, insider stake (>5% ideal), recent insider buying on Form 4 |
| 2 | **Business Quality** | 16.67 | Gross/operating margins, ROIC, revenue growth, margin expansion trajectory |
| 3 | **Unit Economics** | 16.67 | FCF yield, earnings quality (FCF vs. net income), capital-light model |
| 4 | **Valuation** | 16.67 | EV/EBITDA relative to growth, PEG ratio, price-to-FCF |
| 5 | **Information Edge** | 16.67 | Low analyst coverage (<5 analysts), sweet-spot market cap ($500M–$3B) |
| 6 | **Scalability** | 16.67 | Total addressable market, recurring revenue percentage, international runway |

The **FitScorer** loads weights from `scoring_weights.yaml`, calls each criterion module, and sums the results.

#### Risk Score (0–100)

Separate from fit score. Six risk factors:

| Factor | Weight |
|--------|--------|
| Leverage risk | High net debt / EBITDA |
| Concentration risk | Revenue concentration signals |
| Regulatory risk | Industry-specific regulatory exposure |
| Management turnover | Recent C-suite changes |
| Accounting quality | Restatements, audit concerns |
| Geographic risk | Emerging market exposure |

#### Ranker

Combines scores into a final rank:

```
rank_score = fit_score × 0.50 − risk_score × 0.50 + feedback_adjustment
```

The 50/50 weighting is the default and can be adjusted from the Settings page. Feedback adjustments are bounded to [−10, +10] and decay over time.

### 7. RAG System (`src/rag/`)

**Retrieval**: `VectorRetriever` queries pgvector using cosine similarity:
- Input: query text (e.g., "What is ACME Corp's competitive moat?")
- Filters: ticker, document type
- Returns: top-K most relevant document chunks with similarity scores

**Generation**: `MemoGenerator` produces investment memos:
1. Retrieves relevant chunks for a company
2. Numbers each chunk as a citation source
3. Sends chunks + company data to Claude via Jinja2 templates
4. Claude generates a 1–2 page memo with `[1]`, `[2]` citation markers
5. Returns `MemoOutput` with memo text + structured `Citation` objects

### 8. Orchestration (`src/orchestration/`)

**Scoring Pipeline** — end-to-end scoring run:
1. Fetch all active companies (or specific tickers)
2. Load latest metrics for each
3. Apply hard filters → separate passed/failed
4. For passed companies: compute fit score + risk score
5. Query feedback history → calculate adjustments
6. Rank all companies by composite score
7. Persist `Recommendation` records with full scoring detail
8. Log the `ScoringRun`

**Memo Pipeline** — generates memos for top recommendations:
1. Query top N recommendations without memos
2. For each: run RAG retrieval + memo generation
3. Update recommendation with generated memo

**Universe Expander** — discovers new companies via 3 strategies:
1. **Screener**: Market cap range + sector filters via Perplexity
2. **Similarity**: "Find companies similar to [accepted ticker]"
3. **Thematic**: Free-text queries like "founder-led SaaS compounders"

**Scheduler Jobs**:
- **Daily** (weekdays, 6:30 AM ET): Re-score existing universe, check for new filings/news, generate 5 new memos, send email digest, run feedback loop adjustment, check price alerts, scan Form 4 insider purchases
- **Weekly** (Mondays, 5:00 AM ET): Full discovery scan across all exchanges → ingest new companies → full re-score expanded universe → generate 20 memos → send expanded email report

### 9. Feedback Loop (`src/feedback/`)

Closes the loop between analyst decisions and scoring behavior:

1. **Analyze**: Count accepts vs. rejects, summarize reject reasons across the last 30 days
2. **Adjust**: If a dimension is over-represented in rejects, reduce its weight; if associated with accepted companies, increase it. Maximum adjustment: **±2 points per cycle per dimension**
3. **Bound**: Each dimension has a floor of **5 points** and a ceiling of **35 points**
4. **Normalize**: Keep total weights at 100 after adjustments
5. **Persist**: Write updated weights back to `scoring_weights.yaml`

Each reject reason maps to a scoring dimension:

| Reject Reason | Affected Dimension |
|--------------|-------------------|
| Too expensive | Valuation |
| Weak moat / low quality | Business Quality |
| Poor unit economics | Unit Economics |
| No insider alignment | Founder & Ownership |
| Too well-covered | Information Edge |
| Limited growth runway | Scalability |
| Too risky | Risk Score |
| Already known / duplicate | No weight impact |

This creates a self-improving system: analyst expertise calibrates the algorithm over time without any code changes.

### 10. MCP Server (`src/mcp_server/`)

FastAPI application exposing 8 tool endpoints for integration with Claude Desktop:

| Endpoint | Tool | Description |
|----------|------|-------------|
| `/tools/sec-filings` | `sec_filings_tool` | Search and fetch SEC EDGAR filings |
| `/tools/transcripts` | `transcripts_tool` | Fetch earnings call transcripts |
| `/tools/news` | `news_tool` | Search company news |
| `/tools/extractor` | `extractor_tool` | Extract financials + narrative claims |
| `/tools/embedder` | `embedder_tool` | Embed documents into pgvector |
| `/tools/vector` | `vector_tool` | Similarity search over embeddings |
| `/tools/database` | `database_tool` | Query companies, metrics, recommendations |
| `/tools/scheduler` | `scheduler_tool` | Trigger scoring/memo/discovery pipelines |

All endpoints are wrapped with the `@tool_endpoint` decorator that provides consistent error handling and `ToolResponse` / `ToolError` formatting.

### 11. Dashboard (`src/dashboard/`)

Streamlit multi-page application:

| Page | Purpose |
|------|---------|
| **Rankings** | Ranked company list with fit/risk scores, six-dimension pills, action buttons (Research/Watch/Reject) |
| **Company Detail** | Deep dive: financial metrics, scoring breakdown, full memo with citations, feedback history |
| **Watchlist** | Manage watched companies with notes and promotion to Research Now |
| **Analytics** | Accept rate, reject reason distribution, weight evolution chart, recent action feed |
| **Pipeline Runner** | Manual triggers: ingest, score, memo generation, universe expansion, price alert check |
| **Settings** | Edit hard filters, market cap range, scoring weights, ranking formula, output settings, PI config |
| **Insider Buying** | Cluster buy highlights, conviction-ranked purchases, full Form 4 feed, scan trigger |
| **Price Alerts** | Set/manage price targets, triggered alert triage, alert history |

### 12. Prompt Templates (`src/prompts/`)

All LLM prompts are externalized as Jinja2 `.j2` templates. The `PromptLoader` class uses Jinja2's `FileSystemLoader` with `StrictUndefined` to catch missing variables at render time.

Template categories:
- **extraction/**: Financial parsing and claim extraction prompts
- **ingestion/**: Transcript fetch, news search, universe screening prompts
- **discovery/**: Similarity and thematic company search prompts
- **memo/**: System persona + user-facing memo structure prompts

Each template has a corresponding `_system.j2` file for the LLM system prompt.

---

## Scoring Rubric

```
PHOENICIAN FIT SCORE (0–100)
├── Founder / Ownership ............. 16.67 pts
│   ├── Founder-led .................
│   ├── Insider stake > 5% ..........
│   └── Recent Form 4 purchases .....
├── Business Quality ................ 16.67 pts
│   ├── Gross / operating margins ...
│   ├── ROIC .........................
│   ├── Revenue growth ...............
│   └── Margin expansion trajectory .
├── Unit Economics .................. 16.67 pts
│   ├── FCF yield ....................
│   ├── Earnings quality (FCF vs NI) .
│   └── Capital-light model ..........
├── Valuation ....................... 16.67 pts
│   ├── EV/EBITDA vs. growth ........
│   ├── PEG ratio ...................
│   └── Price-to-FCF ................
├── Information Edge ................ 16.67 pts
│   ├── Analyst coverage < 5 ........
│   └── Market cap $500M–$3B ........
└── Scalability ..................... 16.67 pts
    ├── Total addressable market .....
    ├── Recurring revenue % ..........
    └── International runway .........

Note: All six dimensions are equally weighted by default (16.67 pts each).
Weights can be adjusted via the Settings page or by the automated feedback loop.
Each dimension has a floor of 5 pts and a ceiling of 35 pts.
```

---

## Ranking Formula

```
rank_score = fit_score × 0.50
           − risk_score × 0.50
           + feedback_adjustment

where:
  feedback_adjustment = bounded to [−10, +10], decays over time

Default Fit/Risk weighting is 50/50. This can be changed from the Settings page
(e.g., 60/40 to prioritize upside, or 40/60 to prioritize risk avoidance).
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| API Server | FastAPI + Uvicorn |
| Dashboard | Streamlit |
| Database | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy 2.0 (async) |
| Cache/Queue | Redis 7 |
| LLM (Primary) | Claude Sonnet 4.6 (Anthropic) |
| LLM (Memo) | Claude Opus 4.6 (Anthropic) |
| LLM (Extraction) | GPT-4.1-mini (OpenAI) |
| LLM (Discovery) | deep-research (Perplexity) |
| Embeddings | text-embedding-3-small (OpenAI, 1536-dim) |
| Market Data | FMP API (global coverage) |
| SEC Data | EDGAR EFTS API + XBRL |
| News | NewsAPI + Finnhub + Google News |
| Prompt Templates | Jinja2 |
| Containerization | Docker + Docker Compose |

---

## Deployment

### Docker (Recommended)

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 2. Start all services
docker-compose up --build
```

This starts:
- **PostgreSQL + pgvector** on port 5432 (with auto-migration)
- **Redis** on port 6379
- **MCP Server** on port 8000
- **Streamlit Dashboard** on port 5000

### Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start PostgreSQL and Redis locally

# 3. Initialize database
python scripts/init_db.py

# 4. Start the MCP server
python scripts/run_server.py

# 5. Start the dashboard (separate terminal)
streamlit run src/dashboard/app.py --server.port 5000
```

---

## Investment Universe

| Parameter | Criteria |
|-----------|----------|
| **Market Cap** | $100M – $10B |
| **Geographies** | Global public equities, all exchanges |
| **Excluded Geographies** | Mainland China, Russia, Iran |
| **Excluded Sectors** | Energy (GICS 10), Utilities (GICS 55) |
| **Excluded Sub-industries** | Biotech / early-stage pharma (GICS 35201010) |
| **Leverage Limit** | Net Debt / EBITDA < 5x |
| **Gross Margin Floor** | > 20% |

All hard filters can be toggled on/off and their thresholds adjusted from the Settings page. Changes take effect on the next scoring run.
