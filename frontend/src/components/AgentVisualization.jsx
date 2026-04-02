import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import clsx from 'clsx'

// ── Selection agent definitions ──────────────────────────────────────────────

const SELECTION_AGENTS = [
  {
    id: 'filter',
    name: 'Filter Agent',
    icon: '🔧',
    color: 'emerald',
    role: 'Hard Metric Gates',
    checks: ['Gross margin ≥ 30%', 'ROIC ≥ 8%', 'Net Debt/EBITDA ≤ 4×', 'Revenue growth ≥ 3%'],
    rejects: 'Hard-rejects if any threshold unmet',
    passes: 'Gross margin, ROIC, leverage, growth all look clean',
  },
  {
    id: 'business_model',
    name: 'Business Model',
    icon: '🏢',
    color: 'amber',
    role: 'Clarity Check',
    checks: ['Is the business clearly understandable?', 'Single-focus vs conglomerate', 'Recurring revenue model'],
    rejects: 'Business model too complex, diversified, or unclear',
    passes: 'Clean, single-focus business with clear unit economics',
  },
  {
    id: 'founder',
    name: 'Founder Agent',
    icon: '👔',
    color: 'blue',
    role: 'Skin-in-Game Check',
    checks: ['Founder still operating?', 'Insider ownership %', 'Recent insider buys (90-day window)'],
    rejects: 'No insider ownership or alignment evidence',
    passes: 'Founder/insiders have meaningful ownership or recent buys',
  },
  {
    id: 'growth',
    name: 'Growth Agent',
    icon: '📈',
    color: 'purple',
    role: 'Growth Quality',
    checks: ['Organic revenue CAGR', 'FCF growth trajectory', 'M&A-adjusted growth rate'],
    rejects: 'Growth driven by acquisitions or declining',
    passes: 'Organic, compounding growth with FCF support',
  },
  {
    id: 'red_flag',
    name: 'Red Flag Agent',
    icon: '🚩',
    color: 'red',
    role: 'Pattern Detection',
    checks: ['Buyback-to-FCF ratio', 'SBC dilution rate', 'Learned rejection patterns from past runs'],
    rejects: 'Matches a known bad pattern (excessive SBC, buyback games, etc.)',
    passes: 'No red flag patterns detected',
  },
]

const AGENT_ORDER = SELECTION_AGENTS.map(a => a.id)

const COLOR = {
  emerald: { ring: 'ring-emerald-400', bg: 'bg-emerald-50', border: 'border-emerald-300', text: 'text-emerald-700', dot: 'bg-emerald-400', glow: 'shadow-emerald-200' },
  amber:   { ring: 'ring-amber-400',   bg: 'bg-amber-50',   border: 'border-amber-300',   text: 'text-amber-700',   dot: 'bg-amber-400',   glow: 'shadow-amber-200'   },
  blue:    { ring: 'ring-blue-400',    bg: 'bg-blue-50',    border: 'border-blue-300',    text: 'text-blue-700',    dot: 'bg-blue-400',    glow: 'shadow-blue-200'    },
  purple:  { ring: 'ring-purple-400',  bg: 'bg-purple-50',  border: 'border-purple-300',  text: 'text-purple-700',  dot: 'bg-purple-400',  glow: 'shadow-purple-200'  },
  red:     { ring: 'ring-red-400',     bg: 'bg-red-50',     border: 'border-red-300',     text: 'text-red-700',     dot: 'bg-red-400',     glow: 'shadow-red-200'     },
}

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Real-time multi-agent screening visualization.
 * Accepts `status` (polled) + `events` (SSE) for live updates.
 */
export default function AgentVisualization({ events = [], status = null }) {
  const [activePhase, setActivePhase] = useState('discovery')
  const [agentMetrics, setAgentMetrics] = useState({})

  // Derive phase from status (polled) + events (SSE)
  useEffect(() => {
    if (status?.step === 'selection') {
      setActivePhase('selection')
    } else if (status?.step === 'scoring') {
      // After selection completes, scoring starts
      setActivePhase('scoring')
    } else if (status?.done) {
      setActivePhase('complete')
    }
  }, [status?.step, status?.done])

  useEffect(() => {
    if (events.length === 0) return
    const last = events[events.length - 1]
    if (last.type === 'screening_started') setActivePhase('discovery')
    else if (last.type === 'discovery_complete') {
      setActivePhase('selection')
      setAgentMetrics(m => ({ ...m, discovery: { complete: true, count: last.tickers_found } }))
    } else if (last.type === 'screening_progress' && last.step === 'scoring') {
      setActivePhase('scoring')
      setAgentMetrics(m => ({ ...m, scoring: { complete: false, count: last.companies_scored } }))
    } else if (last.type === 'screening_complete') {
      setActivePhase('complete')
      setAgentMetrics(m => ({ ...m, scoring: { complete: true, count: last.scored } }))
    } else if (last.type === 'screening_done') {
      setActivePhase('complete')
    }
  }, [events])

  const discoveryCount = agentMetrics.discovery?.count ?? status?.tickers_found ?? 0
  const isSelectionPhase = activePhase === 'selection' || status?.step === 'selection'
  const isScoringPhase   = activePhase === 'scoring'   || status?.step === 'scoring'

  return (
    <div className="w-full space-y-6">

      {/* ── Phase header ── */}
      <div className="text-center">
        <div className="section-label mb-1">Multi-Agent Screening System</div>
        <h3 className="font-display text-xl font-light text-stone-800">
          {activePhase === 'discovery'  && '🔍 Discovering Universe'}
          {isSelectionPhase             && '⚡ Selection Team Pre-Filtering'}
          {isScoringPhase               && '🧠 Scoring with AI Analyst'}
          {activePhase === 'complete'   && '✨ Screening Complete'}
        </h3>
      </div>

      <div className="bg-white border border-stone-200 rounded-lg shadow-sm overflow-hidden">

        {/* ── Phase 1: Discovery ── */}
        <PhaseRow
          label="Phase 1 — Universe Discovery"
          done={activePhase !== 'discovery'}
          active={activePhase === 'discovery'}
        >
          <div className="flex gap-3">
            {[
              { id: 'edgar', name: 'EDGAR', icon: '📄', color: 'blue', desc: 'US companies' },
              { id: 'intl',  name: 'International', icon: '🌍', color: 'purple', desc: 'Global search' },
            ].map(a => (
              <SmallAgentBadge key={a.id} {...a} active={activePhase === 'discovery'} />
            ))}
            {discoveryCount > 0 && (
              <div className="ml-auto flex items-center text-sm font-semibold text-stone-600">
                {discoveryCount} candidates found
              </div>
            )}
          </div>
        </PhaseRow>

        {/* ── Connector ── */}
        <PhaseConnector active={isSelectionPhase || isScoringPhase || activePhase === 'complete'} />

        {/* ── Phase 2: Selection (the star of the show) ── */}
        <PhaseRow
          label="Phase 2 — Selection Team (Pre-Filter)"
          done={isScoringPhase || activePhase === 'complete'}
          active={isSelectionPhase}
        >
          <SelectionChain
            status={status}
            isSelectionPhase={isSelectionPhase}
            isScoringDone={isScoringPhase || activePhase === 'complete'}
          />
        </PhaseRow>

        {/* ── Connector ── */}
        <PhaseConnector active={isScoringPhase || activePhase === 'complete'} />

        {/* ── Phase 3: Scoring ── */}
        <PhaseRow
          label="Phase 3 — Scoring Team (AI Analyst)"
          done={activePhase === 'complete'}
          active={isScoringPhase}
        >
          <div className="flex gap-3 flex-wrap">
            {[
              { id: 'analyst', name: 'AI Analyst', icon: '🧠', color: 'amber',  desc: 'Business quality + fit' },
              { id: 'risk',    name: 'Risk Scorer', icon: '⚠️',  color: 'red',   desc: 'Leverage, moat, margins' },
              { id: 'memo',    name: 'Memo Gen',    icon: '📝',  color: 'blue',  desc: 'Investment thesis' },
            ].map(a => (
              <SmallAgentBadge key={a.id} {...a} active={isScoringPhase} done={activePhase === 'complete'} />
            ))}
            {(isScoringPhase || activePhase === 'complete') && status?.companies_scored > 0 && (
              <div className="ml-auto flex items-center text-sm font-semibold text-stone-600">
                {status.companies_scored} scored
              </div>
            )}
          </div>
        </PhaseRow>

      </div>

    </div>
  )
}

// ── Selection chain (always rendered in Phase 2) ─────────────────────────────

function SelectionChain({ status, isSelectionPhase, isScoringDone }) {
  const currentAgent  = status?.current_agent  ?? null
  const currentTicker = status?.current_ticker ?? null
  const done          = status?.companies_scored ?? 0
  const total         = status?.tickers_found   ?? 0

  // Map agent id → index; -1 means none running
  const currentIdx = isSelectionPhase ? AGENT_ORDER.indexOf(currentAgent ?? '') : -1

  // Keep a rolling log of [ticker, agent] pairs we've seen
  const logRef = useRef([])

  useEffect(() => {
    if (!currentTicker || !currentAgent) return
    const entry = { ticker: currentTicker, agent: currentAgent, t: Date.now() }
    logRef.current = [...logRef.current.slice(-29), entry]
  }, [currentTicker, currentAgent])

  return (
    <div className="flex gap-6">

      {/* ── Agent chain ── */}
      <div className="flex-1 min-w-0">

        {/* Current company banner — only during selection */}
        <AnimatePresence mode="wait">
          {isSelectionPhase && currentTicker && (
            <motion.div
              key={currentTicker}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 8 }}
              className="flex items-center gap-3 mb-4 p-2.5 bg-blue-50 border border-blue-200 rounded-md"
            >
              <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse flex-shrink-0" />
              <span className="text-xs text-blue-500 font-medium">Evaluating</span>
              <span className="font-mono text-sm font-bold text-stone-800">{currentTicker}</span>
              <span className="ml-auto text-xs text-stone-400 tabular-nums">{done}/{total}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* The 5-agent vertical chain */}
        <div>
          {SELECTION_AGENTS.map((agent, i) => {
            let state
            if (isScoringDone) {
              state = 'passed'
            } else if (!isSelectionPhase) {
              state = 'pending'
            } else if (currentIdx === -1) {
              state = 'pending'
            } else if (i < currentIdx) {
              state = 'passed'
            } else if (i === currentIdx) {
              state = 'active'
            } else {
              state = 'pending'
            }

            return (
              <div key={agent.id}>
                <AgentChainNode agent={agent} state={state} />
                {i < SELECTION_AGENTS.length - 1 && (
                  <AgentConnector
                    flowing={state === 'active'}
                    done={state === 'passed'}
                    passMessage={agent.passes}
                  />
                )}
              </div>
            )
          })}
        </div>

      </div>

      {/* ── Live decision log ── */}
      {isSelectionPhase && <LiveLog logRef={logRef} />}

    </div>
  )
}

// ── Single agent node in the chain ───────────────────────────────────────────

function AgentChainNode({ agent, state }) {
  const [hovered, setHovered] = useState(false)
  const c = COLOR[agent.color]

  const isActive  = state === 'active'
  const isPassed  = state === 'passed'

  return (
    <div className="relative">
      <motion.div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        animate={{
          scale: isActive ? 1.03 : 1,
          opacity: state === 'pending' ? 0.4 : 1,
        }}
        transition={{ duration: 0.2 }}
        className={clsx(
          'flex items-center gap-3 p-3 rounded-lg border-2 cursor-default transition-shadow',
          isActive  && `${c.bg} ${c.border} ring-4 ${c.ring} shadow-xl`,
          isPassed  && 'bg-emerald-50 border-emerald-300',
          state === 'pending' && 'bg-stone-50 border-stone-200',
        )}
      >
        {/* State icon */}
        <div className="flex-shrink-0 w-7 flex items-center justify-center">
          {isActive && (
            <motion.div
              animate={{ scale: [1, 1.4, 1], opacity: [1, 0.6, 1] }}
              transition={{ repeat: Infinity, duration: 0.9 }}
              className={clsx('w-3 h-3 rounded-full', c.dot)}
            />
          )}
          {isPassed  && (
            <div className="w-5 h-5 rounded-full bg-emerald-100 border border-emerald-300 flex items-center justify-center">
              <span className="text-emerald-600 text-[10px] font-bold">✓</span>
            </div>
          )}
          {state === 'pending' && (
            <div className="w-5 h-5 rounded-full border-2 border-stone-200" />
          )}
        </div>

        {/* Agent icon */}
        <span className={clsx('text-xl leading-none', state === 'pending' && 'grayscale opacity-40')}>{agent.icon}</span>

        {/* Name + role */}
        <div className="flex-1 min-w-0">
          <div className={clsx(
            'text-xs font-bold truncate',
            isActive  ? c.text :
            isPassed  ? 'text-emerald-700' :
                        'text-stone-400'
          )}>
            {agent.name}
          </div>
          <div className="text-[10px] text-stone-400 truncate">{agent.role}</div>
        </div>

        {/* State badge */}
        <div className="flex-shrink-0">
          {isActive && (
            <span className={clsx('px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase', c.bg, c.text)}>
              ● Running
            </span>
          )}
          {isPassed && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-600">
              Passed
            </span>
          )}
          {state === 'pending' && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-stone-100 text-stone-400">
              Waiting
            </span>
          )}
        </div>
      </motion.div>

      {/* Hover tooltip */}
      <AnimatePresence>
        {hovered && (
          <AgentTooltip agent={agent} state={state} />
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Tooltip shown on hover ────────────────────────────────────────────────────

function AgentTooltip({ agent, state }) {
  const c = COLOR[agent.color]

  return (
    <motion.div
      initial={{ opacity: 0, x: 8, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 8, scale: 0.95 }}
      transition={{ duration: 0.15 }}
      className="absolute left-full top-0 ml-3 z-50 w-60 bg-white border border-stone-200 rounded-lg shadow-xl p-4"
      style={{ pointerEvents: 'none' }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xl">{agent.icon}</span>
        <div>
          <div className={clsx('text-xs font-bold', c.text)}>{agent.name}</div>
          <div className="text-[10px] text-stone-400">{agent.role}</div>
        </div>
      </div>

      {/* What it checks */}
      <div className="mb-3">
        <div className="text-[10px] font-semibold text-stone-500 uppercase tracking-wide mb-1.5">Checks</div>
        <ul className="space-y-1">
          {agent.checks.map((c, i) => (
            <li key={i} className="flex items-start gap-1.5 text-[11px] text-stone-700">
              <span className="text-stone-300 mt-0.5 flex-shrink-0">▸</span>
              {c}
            </li>
          ))}
        </ul>
      </div>

      {/* Divider */}
      <div className="border-t border-stone-100 my-3" />

      {/* Pass/reject outcome */}
      <div className="space-y-1.5">
        <div className="flex items-start gap-1.5 text-[11px]">
          <span className="text-emerald-500 flex-shrink-0">✓</span>
          <span className="text-stone-600">{agent.passes}</span>
        </div>
        <div className="flex items-start gap-1.5 text-[11px]">
          <span className="text-red-400 flex-shrink-0">✗</span>
          <span className="text-stone-600">{agent.rejects}</span>
        </div>
      </div>

      {/* Current state tag */}
      {state !== 'pending' && (
        <div className={clsx(
          'mt-3 text-center text-[10px] font-semibold py-1 rounded',
          state === 'active' ? `${COLOR[agent.color].bg} ${COLOR[agent.color].text}` : 'bg-emerald-50 text-emerald-600'
        )}>
          {state === 'active' ? '● Running now' : '✓ Already passed'}
        </div>
      )}
    </motion.div>
  )
}

// ── Arrow connector between agents ───────────────────────────────────────────

function AgentConnector({ flowing, done, passMessage }) {
  const [hovTip, setHovTip] = useState(false)

  const lineColor = flowing ? '#60a5fa' : done ? '#6ee7b7' : '#d1d5db'
  const arrowColor = flowing ? '#3b82f6' : done ? '#34d399' : '#d1d5db'

  return (
    <div
      className="relative flex items-center py-0 ml-5"
      onMouseEnter={() => setHovTip(true)}
      onMouseLeave={() => setHovTip(false)}
    >
      {/* SVG arrow: vertical line + arrowhead */}
      <svg width="24" height="32" viewBox="0 0 24 32" fill="none" className="flex-shrink-0">
        {/* Vertical stem */}
        <line x1="12" y1="0" x2="12" y2="22" stroke={lineColor} strokeWidth="2" strokeLinecap="round" />
        {/* Arrowhead */}
        <path d="M6 18 L12 26 L18 18" stroke={arrowColor} strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>

      {/* Flowing dot travelling down the arrow */}
      {flowing && (
        <motion.div
          animate={{ y: [0, 24, 0] }}
          transition={{ repeat: Infinity, duration: 0.7, ease: 'linear' }}
          className="absolute left-5 w-2 h-2 rounded-full bg-blue-400 shadow shadow-blue-300"
          style={{ top: 0, marginLeft: '-1px' }}
        />
      )}

      {/* Hover: pass message tooltip */}
      <AnimatePresence>
        {hovTip && passMessage && (
          <motion.div
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0 }}
            className="absolute left-8 z-40 bg-stone-800 text-white text-[10px] px-2 py-1 rounded whitespace-nowrap shadow-lg"
            style={{ pointerEvents: 'none', top: 8 }}
          >
            Passes if: {passMessage}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Rolling live log (right side panel) ──────────────────────────────────────

function LiveLog({ logRef }) {
  const [tick, setTick] = useState(0)

  // Refresh every 2 seconds to show latest entries
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 2000)
    return () => clearInterval(id)
  }, [])

  const entries = logRef.current.slice(-12).reverse()
  if (entries.length === 0) return null

  const agentMeta = Object.fromEntries(SELECTION_AGENTS.map(a => [a.id, a]))

  return (
    <div className="w-40 flex-shrink-0">
      <div className="text-[10px] font-semibold text-stone-400 uppercase tracking-wide mb-2">Recent</div>
      <div className="space-y-1">
        {entries.map((e, i) => {
          const meta = agentMeta[e.agent]
          return (
            <motion.div
              key={`${e.ticker}-${e.agent}-${e.t}`}
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-1.5"
            >
              <span className="text-[10px] font-mono text-stone-500 truncate flex-1">{e.ticker}</span>
              {meta && (
                <span className="text-[10px]">{meta.icon}</span>
              )}
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

// ── Shared small helpers ──────────────────────────────────────────────────────

function PhaseRow({ label, active, done, children }) {
  return (
    <motion.div
      animate={{ opacity: active || done ? 1 : 0.4 }}
      className="p-5"
    >
      <div className="flex items-center gap-2 mb-4">
        <div className={clsx(
          'w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0',
          done   ? 'bg-emerald-100 text-emerald-600' :
          active ? 'bg-blue-100 text-blue-600 ring-2 ring-blue-300' :
                   'bg-stone-100 text-stone-400'
        )}>
          {done ? '✓' : active ? '●' : '○'}
        </div>
        <span className={clsx(
          'text-xs font-semibold uppercase tracking-wide',
          done ? 'text-emerald-600' : active ? 'text-blue-700' : 'text-stone-400'
        )}>
          {label}
        </span>
      </div>
      {children}
    </motion.div>
  )
}

function PhaseConnector({ active }) {
  return (
    <div className="flex items-center px-5 py-1 gap-3">
      <div className="w-px h-6 bg-stone-200 ml-2 relative overflow-hidden">
        {active && (
          <motion.div
            animate={{ y: ['-100%', '100%'] }}
            transition={{ repeat: Infinity, duration: 0.9, ease: 'linear' }}
            className="absolute inset-x-0 h-3 bg-gradient-to-b from-transparent via-blue-400 to-transparent"
          />
        )}
      </div>
      <svg className="w-3 h-3 text-stone-300" viewBox="0 0 12 12" fill="currentColor">
        <path d="M6 0 L6 8 M6 8 L3 5 M6 8 L9 5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      </svg>
    </div>
  )
}

function SmallAgentBadge({ name, icon, color, desc, active, done }) {
  const c = COLOR[color] ?? COLOR.blue
  return (
    <div className={clsx(
      'px-2.5 py-1.5 rounded-md border text-[11px] flex items-center gap-1.5 transition',
      done   ? 'bg-emerald-50 border-emerald-200 text-emerald-700' :
      active ? `${c.bg} ${c.border} ${c.text}` :
               'bg-stone-50 border-stone-200 text-stone-400'
    )}>
      <span>{icon}</span>
      <span className="font-semibold">{name}</span>
    </div>
  )
}
