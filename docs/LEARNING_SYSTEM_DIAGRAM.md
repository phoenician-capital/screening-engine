# Learning System — Visual Diagrams

## The Complete Feedback Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SCREENING RUN N                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Universe (1000 companies)                                                  │
│  ↓ Selection Team (5 agents)                                                │
│  ├─ Filter Agent (metrics)                  ✓                              │
│  ├─ Business Model Agent                    ✓                              │
│  ├─ Founder Agent                           ✓                              │
│  ├─ Growth Agent                            ✓                              │
│  └─ Red Flag Agent                          ✓ ← Loads learned patterns    │
│  ↓                                                                           │
│  Selected: 40 companies                                                      │
│  ↓ Scoring Team                                                              │
│  ├─ Researcher Agent                        ↓                              │
│  ├─ Scorer Agent                            ↓                              │
│  ├─ Critic Agent                            ↓                              │
│  └─ Memo Agent                              ↓                              │
│  ↓                                                                           │
│  Results: 8 RESEARCH NOW + 12 WATCH + 20 PASS                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
                          ┌─────────────────────┐
                          │   ANALYST REVIEWS   │
                          │  8 RESEARCH NOW     │
                          │  Gives FEEDBACK     │
                          └─────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                      BIDIRECTIONAL LEARNING                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FEEDBACK: "Reject AXON — buyback $210M / FCF $70M unsustainable"          │
│            "Also unclear business model"                                    │
│                                    ↓                                        │
│  SelectionFeedbackAnalyzer (LLM-powered)                                   │
│    ↓ Parses analyst notes                                                   │
│    ↓ Extracts concerns: ["unsustainable buybacks", "unclear business"]     │
│                                    ↓                                        │
│  Pattern Creation                                                            │
│    ├─ Pattern 1: {                                                          │
│    │    metric: "buyback_to_fcf_ratio"                                      │
│    │    old_threshold: 1.0  (baseline)                                      │
│    │    new_threshold: 0.8  (learned from feedback)                         │
│    │    confidence: 0.7     (new pattern)                                   │
│    │    expires_at: now + 30 days                                           │
│    │  }                                                                      │
│    └─ Pattern 2: {                                                          │
│       metric: NULL                                                           │
│       issue: "Business model clarity"                                       │
│       confidence: 0.7                                                       │
│     }                                                                        │
│                                    ↓                                        │
│  Database Storage                                                            │
│    INSERT INTO selection_learned_patterns (pattern_1)                       │
│    INSERT INTO selection_learned_patterns (pattern_2)                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SCREENING RUN N+1 (PATTERNS ACTIVE)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Universe (1000 companies)                                                  │
│  ↓ Selection Team                                                            │
│  └─ Red Flag Agent:                                                          │
│     ├─ Load learned patterns from DB                                        │
│     │  {buyback_to_fcf_ratio: threshold=0.8, confidence=0.7}               │
│     │                                                                        │
│     ├─ For company ACME (buyback_to_fcf_ratio = 2.5):                       │
│     │  Is 2.5 > 0.8? YES                                                    │
│     │  Is confidence > 0.75? NO (0.7 not yet validated)                    │
│     │  → Marginal: might apply depending on other checks                   │
│     │                                                                        │
│     ├─ For company BLAH (buyback_to_fcf_ratio = 0.6):                       │
│     │  Is 0.6 > 0.8? NO                                                     │
│     │  → OK, passes red flag check                                          │
│     │                                                                        │
│     └─ Log: "Applied learned pattern: buyback (confidence 70%)"             │
│                                                                              │
│  Selected: 35-40 companies (fewer than before, more filtered)               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
                    ┌───────────────────────────────┐
                    │  Analyst Feedback Again       │
                    │  Run N+2 → rejects ACME       │
                    │  "Yes, that buyback is bad"   │
                    │       ↓                       │
                    │  Pattern confidence:          │
                    │  0.7 → 0.8 (validated!)       │
                    └───────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                 SCREENING RUN N+3 (PATTERN GOLD STANDARD)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Red Flag Agent loads:                                                       │
│    {buyback_to_fcf_ratio: threshold=0.8, confidence=0.8}                    │
│                                                                              │
│  Is confidence > 0.75? YES (0.8 > 0.75)                                    │
│  → AUTO-APPLY: All companies with buyback > 0.8x REJECTED                  │
│                                                                              │
│  For company CHARLIE (buyback = 1.5x):                                      │
│  Is 1.5 > 0.8? YES                                                          │
│  Confidence high? YES                                                        │
│  → AUTO-REJECT with: "Unsustainable buyback 1.5x FCF (> 0.8x)             │
│                       (learned from analyst feedback)"                      │
│                                                                              │
│  Selected: 25-30 companies (highly filtered, better quality)                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Pattern Lifecycle

```
                        Pattern Creation
                             ↓
                    ┌────────────────┐
                    │   Confidence   │
                    │      0.7       │
                    │   (NEW)        │
                    └────────────────┘
                             ↓
        ┌────────────────────────────────────────┐
        │  Run 2: Analyst reviews similar company │
        └────────────────────────────────────────┘
                             ↓
                        ┌────────────────┐
                        │   Confidence   │
                        │      0.8       │
                        │  (VALIDATED)   │
                        │  > 0.75 ✓      │
                        │  AUTO-APPLY!   │
                        └────────────────┘
                             ↓
        ┌────────────────────────────────────────┐
        │  Run 3: Analyst reviews 3rd similar     │
        └────────────────────────────────────────┘
                             ↓
                        ┌────────────────┐
                        │   Confidence   │
                        │      0.9       │
                        │  (GOLD STD)    │
                        │  Highly reliable
                        └────────────────┘
                             ↓
        ┌────────────────────────────────────────┐
        │  Days 1-30: Pattern in use             │
        │  Pattern applied to all companies      │
        │  Analyst validates or disagrees        │
        └────────────────────────────────────────┘
                             ↓
        ┌────────────────────────────────────────┐
        │  Day 30: Pattern expires_at = NOW()    │
        │  If confidence < 0.8: DROP from index  │
        │  If confidence >= 0.8: REFRESH expiry  │
        │  (Auto-renewed if analyst kept validating)
        └────────────────────────────────────────┘
                             ↓
                    ┌────────────────┐
                    │   Confidence   │
                    │      0.0       │
                    │   (EXPIRED)    │
                    │   Removed      │
                    └────────────────┘
```

---

## Database Tables: Pattern Storage

```
┌─────────────────────────────────────────────────────────────────┐
│              selection_learned_patterns                          │
├─────────────────────────────────────────────────────────────────┤
│ id (UUID)                                                        │
│ pattern_type          → 'missed_red_flag' | 'miscalibration'   │
│ agent_type            → 'filter' | 'business_model' | 'founder' │
│                         'growth' | 'red_flag'                   │
│ metric_name           → 'buyback_to_fcf_ratio', 'leverage', ... │
│ old_threshold         → {value: 1.0}  (baseline)               │
│ new_threshold         → {value: 0.8}  (learned)                │
│ confidence            → 0.7 to 0.95 (0.0 = expired)            │
│ triggered_by_feedback_id → FK to feedback.id                   │
│ analyst_action        → 'reject' | 'watch' | 'research_now'    │
│ expires_at            → now + 30 days                           │
│ metadata              → {                                        │
│                          "issue": "Unsustainable buyback",      │
│                          "company_ticker": "AXON",              │
│                          "actual_value": 3.0,                   │
│                          "severity": "high"                     │
│                        }                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Analyst Notes → Learned Threshold

```
API Endpoint receives feedback:
┌─────────────────────────────────────────┐
│ POST /recommendations/{ticker}/feedback │
│ {                                       │
│   action: "reject",                     │
│   notes: "Buyback $210M / FCF $70M"    │
│ }                                       │
└─────────────────────────────────────────┘
                        ↓
           ┌────────────────────────┐
           │  Feedback stored       │
           │  notes = text          │
           └────────────────────────┘
                        ↓
           ┌────────────────────────┐
           │ SelectionFeedback      │
           │ Analyzer               │
           │                        │
           │ LLM parses notes       │
           │ Extracts concerns      │
           └────────────────────────┘
                        ↓
           ┌────────────────────────┐
           │ Concerns extracted:    │
           │ ["unsustainable buyback │
           │  unclear business"]    │
           └────────────────────────┘
                        ↓
           ┌────────────────────────┐
           │ For each concern:      │
           │ Create Pattern object  │
           │ Calculate new threshold│
           │ Set confidence 0.7     │
           └────────────────────────┘
                        ↓
           ┌────────────────────────┐
           │ Store in database      │
           │ selection_learned_     │
           │ patterns               │
           └────────────────────────┘
                        ↓
Next Screening Run:
┌─────────────────────────────────────────┐
│ Red Flag Agent                          │
│ ._get_learned_patterns()                │
│ ._get_threshold()                       │
│                                         │
│ Load: {buyback_to_fcf_ratio: 0.8}      │
│ Apply to all companies                  │
└─────────────────────────────────────────┘
```

---

## Confidence Score Evolution

```
Run 1: AXON rejected, pattern created
┌──────────────────────────────────┐
│  Pattern: buyback > 0.8x         │
│  Confidence: 0.7 (INITIAL)       │
│  Activation: No (< 0.75)         │
│  Status: Waiting for validation  │
└──────────────────────────────────┘

Run 2: ACME rejected for same reason
┌──────────────────────────────────┐
│  Pattern: buyback > 0.8x         │
│  Confidence: 0.8 (VALIDATED)     │
│  Activation: Yes (> 0.75) ✓      │
│  Status: Auto-applying now       │
└──────────────────────────────────┘

Run 3: CHARLIE rejected for same reason
┌──────────────────────────────────┐
│  Pattern: buyback > 0.8x         │
│  Confidence: 0.85 (STRONG)       │
│  Activation: Yes                 │
│  Status: Highly reliable         │
└──────────────────────────────────┘

Run 5: DAVID accepted despite buyback > 0.8x
┌──────────────────────────────────┐
│  Pattern: buyback > 0.8x         │
│  Confidence: 0.65 (DISAGREEMENT) │
│  Activation: No (< 0.75)         │
│  Status: Pattern is questionable │
└──────────────────────────────────┘

Day 31: Pattern expires_at = NOW()
┌──────────────────────────────────┐
│  Pattern: buyback > 0.8x         │
│  Confidence: 0.65 (EXPIRED)      │
│  Activation: No                  │
│  Status: Removed from active set │
│  → Revert to baseline 1.0x       │
└──────────────────────────────────┘
```

---

## Red Flag Agent Decision Tree

```
                    Red Flag Agent.evaluate()
                            ↓
                ┌───────────────────────────┐
                │ Load learned patterns DB  │
                └───────────────────────────┘
                            ↓
            ┌───────────────────────────────────┐
            │ For each metric (buyback, leverage,│
            │ dilution, FCF/CapEx):             │
            └───────────────────────────────────┘
                            ↓
            ┌───────────────────────────────────┐
            │ Get threshold (learned or         │
            │ baseline) via _get_threshold()    │
            └───────────────────────────────────┘
                            ↓
            ┌──────────────────────────────────────────┐
            │ Is metric > threshold?                   │
            └──────────────────────────────────────────┘
              /                                    \
            YES                                    NO
             ↓                                      ↓
      ┌─────────────────┐                  ┌──────────────┐
      │ Add flag to list │                 │ Continue to  │
      │                 │                  │ next metric  │
      │ If learned:     │                  └──────────────┘
      │ "learned from   │
      │ analyst feedback"
      └─────────────────┘
             ↓
    ┌───────────────────────┐
    │ All metrics checked?  │
    └───────────────────────┘
         /              \
       YES               NO
        ↓                ↓
    Return Decision:   Continue
    - passed: len(flags)==0
    - reason: " | ".join(flags)
    - metadata:
        applied_patterns: [...]
        learned_count: N
```

---

## How Learned Patterns Flow Through Selection Agent Decisions

```
Company ACME enters pipeline:
                    ↓
    ┌───────────────────────────┐
    │ Selection Agent Decision  │
    │ (SQLAlchemy ORM model)    │
    └───────────────────────────┘
                    ↓
    ┌───────────────────────────┐
    │ id: UUID                  │
    │ company_ticker: "ACME"    │
    │ agent_type: "red_flag"    │
    │ passed_filter: FALSE      │
    │ reason: "Buyback 2.5x...  │
    │  (learned from analyst)"  │
    │ decision_data: {          │
    │   "buyback_ratio": 2.5,   │
    │   "applied_learned_       │
    │    patterns": [           │
    │      "buyback_to_fcf_     │
    │       ratio"              │
    │    ],                      │
    │   "learned_pattern_count":1
    │ }                         │
    └───────────────────────────┘
                    ↓
        Stored in database for:
        - Analysis
        - Debugging
        - Learning validation
```

---

## Performance Impact: With vs Without Learning

```
SCREENING RUN WITHOUT LEARNING:
┌──────────────────────────────────┐
│ Universe: 1000 companies         │
│ Hard Filter: 1000 → 250          │
│ (Sector, country, market cap)    │
│                                  │
│ Selection Team (baseline):       │
│ Filter: 250 → 225                │
│ Business: 225 → 200              │
│ Founder: 200 → 100               │
│ Growth: 100 → 50                 │
│ Red Flag (baseline): 50 → 40     │
│                                  │
│ → 40 sent to Scoring             │
│ → Scoring cost: 40 × $1 = $40    │
│ → Total cost: ~$50               │
└──────────────────────────────────┘

SCREENING RUN WITH LEARNING (Run 10):
┌──────────────────────────────────┐
│ Universe: 1000 companies         │
│ Hard Filter: 1000 → 250          │
│ (Same as before)                 │
│                                  │
│ Selection Team (learned filters):│
│ Filter: 250 → 225                │
│ Business: 225 → 200              │
│ Founder: 200 → 100               │
│ Growth: 100 → 50                 │
│ Red Flag (3 learned patterns):   │
│   50 → 25                        │
│                                  │
│ → 25 sent to Scoring             │
│ → Scoring cost: 25 × $1 = $25    │
│ → Total cost: ~$35               │
│ SAVINGS: 37% cost reduction      │
└──────────────────────────────────┘
```

---

## Summary: System Architecture

```
Analyst Feedback → SelectionFeedbackAnalyzer → Patterns → Database
                                      ↓
                                   Learning
                                      ↓
                          Next Screening Run
                                      ↓
                          Red Flag Agent loads
                          & applies patterns
                                      ↓
                          More filtered companies
                          (better quality)
                                      ↓
                          Scoring is cheaper
                          & more effective
```
