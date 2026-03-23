"""
Application-wide constants.
"""

# ── GICS sector codes ────────────────────────────────────────────
GICS_ENERGY = "10"
GICS_MATERIALS = "15"
GICS_INDUSTRIALS = "20"
GICS_CONSUMER_DISC = "25"
GICS_CONSUMER_STAPLES = "30"
GICS_HEALTHCARE = "35"
GICS_FINANCIALS = "40"
GICS_IT = "45"
GICS_COMM_SERVICES = "50"
GICS_UTILITIES = "55"
GICS_REAL_ESTATE = "60"

GICS_BIOTECH_SUB_INDUSTRY = "35201010"

# ── Document types ───────────────────────────────────────────────
DOC_10K = "10-K"
DOC_10Q = "10-Q"
DOC_8K = "8-K"
DOC_DEF14A = "DEF 14A"
DOC_FORM4 = "Form 4"
DOC_TRANSCRIPT = "transcript"
DOC_NEWS = "news"

# ── Recommendation statuses ─────────────────────────────────────
STATUS_PENDING = "pending"
STATUS_WATCHED = "watched"
STATUS_REJECTED = "rejected"
STATUS_RESEARCHING = "researching"

# ── Feedback actions ─────────────────────────────────────────────
ACTION_REJECT = "reject"
ACTION_WATCH = "watch"
ACTION_RESEARCH_NOW = "research_now"

# ── Reject reason codes ─────────────────────────────────────────
REJECT_MGMT_QUALITY = "mgmt_quality"
REJECT_CYCLICAL = "too_cyclical"
REJECT_VALUATION = "valuation_unattractive"
REJECT_GOVERNANCE = "governance"
REJECT_LIQUIDITY = "illiquid"
REJECT_OTHER = "other"

# ── Embedding / chunk settings ───────────────────────────────────
CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 64
MAX_CHUNKS_PER_DOC = 200

# ── Rate limits ──────────────────────────────────────────────────
SEC_EDGAR_RPS = 10
PERPLEXITY_RPM = 60
OPENAI_RPM = 500
