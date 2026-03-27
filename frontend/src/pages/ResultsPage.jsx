import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, ChevronDown, ChevronUp, X, ExternalLink, ChevronRight } from 'lucide-react'
import clsx from 'clsx'
import { useApi } from '../hooks/useApi'
import { api } from '../api'
import ScorePill from '../components/ScorePill'
import ScoreBar from '../components/ScoreBar'
import StatusBadge from '../components/StatusBadge'
import VerdictBanner from '../components/VerdictBanner'
import { TableSkeleton } from '../components/Skeleton'

// ── Formatting ────────────────────────────────────────────────────────────────
const fmtPct  = v => v == null ? '—' : `${v > 10 ? v.toFixed(1) : v.toFixed(1)}%`
const fmtMult = v => v == null ? '—' : `${v.toFixed(1)}x`
const fmtCap  = v => {
  if (v == null) return '—'
  if (v >= 1e9) return `$${(v/1e9).toFixed(1)}B`
  if (v >= 1e6) return `$${(v/1e6).toFixed(0)}M`
  return `$${v.toLocaleString()}`
}

// ── Stats bar ─────────────────────────────────────────────────────────────────
function StatsBar({ rows }) {
  if (!rows.length) return null
  const avgFit  = (rows.reduce((s, r) => s + r.fit_score, 0) / rows.length).toFixed(1)
  const avgRisk = (rows.reduce((s, r) => s + r.risk_score, 0) / rows.length).toFixed(1)
  const inResearch = rows.filter(r => r.status === 'researching').length
  const founders   = rows.filter(r => r.founder_led).length

  return (
    <div className="grid grid-cols-4 gap-4 mb-6">
      {[
        { label: 'Companies',  value: rows.length,  mono: true },
        { label: 'Avg Fit',    value: avgFit,        mono: true, green: true },
        { label: 'Avg Risk',   value: avgRisk,       mono: true, red: true },
        { label: 'In Research',value: inResearch,    mono: true, blue: true },
      ].map(({ label, value, mono, green, red, blue }) => (
        <div key={label} className="stat-card">
          <div className="section-label mb-2">{label}</div>
          <div className={clsx(
            'text-2xl font-semibold',
            mono && 'font-mono',
            green && 'text-emerald-600',
            red   && 'text-red-500',
            blue  && 'text-blue-600',
            !green && !red && !blue && 'text-stone-800'
          )}>
            {value}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Filter bar ────────────────────────────────────────────────────────────────
function FilterBar({ rows, filters, setFilters }) {
  const sectors = useMemo(
    () => [...new Set(rows.map(r => r.sector).filter(Boolean))].sort(),
    [rows]
  )

  return (
    <div className="flex items-center gap-3 mb-5 flex-wrap">
      {/* Search */}
      <div className="relative">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
        <input
          value={filters.search}
          onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
          placeholder="Search ticker or name…"
          className="pl-8 pr-3 py-1.5 text-sm bg-white border border-stone-200 rounded-xs
                     focus:outline-none focus:border-gold-400 focus:ring-1 focus:ring-gold-200
                     w-52 placeholder:text-stone-300 transition"
        />
      </div>

      {/* Min Fit */}
      <Select
        value={filters.minFit}
        onChange={v => setFilters(f => ({ ...f, minFit: v }))}
        options={[
          { value: '0',  label: 'Any fit' },
          { value: '40', label: 'Fit 40+' },
          { value: '50', label: 'Fit 50+' },
          { value: '60', label: 'Fit 60+' },
          { value: '70', label: 'Fit 70+' },
        ]}
      />

      {/* Max Risk */}
      <Select
        value={filters.maxRisk}
        onChange={v => setFilters(f => ({ ...f, maxRisk: v }))}
        options={[
          { value: '100', label: 'Any risk' },
          { value: '15',  label: 'Risk < 15' },
          { value: '25',  label: 'Risk < 25' },
          { value: '40',  label: 'Risk < 40' },
        ]}
      />

      {/* Status */}
      <Select
        value={filters.status}
        onChange={v => setFilters(f => ({ ...f, status: v }))}
        options={[
          { value: '',           label: 'All status' },
          { value: 'pending',    label: 'Pending' },
          { value: 'researching',label: 'Researching' },
          { value: 'watched',    label: 'Watched' },
          { value: 'rejected',   label: 'Passed' },
        ]}
      />

      {/* Sector */}
      <Select
        value={filters.sector}
        onChange={v => setFilters(f => ({ ...f, sector: v }))}
        options={[{ value: '', label: 'All sectors' }, ...sectors.map(s => ({ value: s, label: s }))]}
        wide
      />

      {/* Sort */}
      <Select
        value={filters.sort}
        onChange={v => setFilters(f => ({ ...f, sort: v }))}
        options={[
          { value: 'score',  label: 'Sort: Score' },
          { value: 'fit',    label: 'Sort: Fit' },
          { value: 'risk',   label: 'Sort: Risk ↑' },
          { value: 'mcap',   label: 'Sort: Mkt Cap' },
        ]}
      />

      {/* Count */}
      <span className="ml-auto text-xs text-stone-400 font-mono">
        {rows.length} companies
      </span>
    </div>
  )
}

function Select({ value, onChange, options, wide }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className={clsx(
        'py-1.5 px-3 text-xs bg-white border border-stone-200 rounded-xs',
        'focus:outline-none focus:border-gold-400 focus:ring-1 focus:ring-gold-200',
        'text-stone-600 appearance-none cursor-pointer transition',
        wide ? 'w-44' : 'w-36'
      )}
    >
      {options.map(o => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  )
}

// ── Table ─────────────────────────────────────────────────────────────────────
const COLS = [
  { key: '#',         label: '#',         w: 'w-12',  align: 'left'  },
  { key: 'ticker',    label: 'Ticker',    w: 'w-28',  align: 'left'  },
  { key: 'name',      label: 'Company',   w: 'w-44',  align: 'left'  },
  { key: 'mcap',      label: 'Mkt Cap',   w: 'w-24',  align: 'right' },
  { key: 'fit',       label: 'Fit',       w: 'w-16',  align: 'right' },
  { key: 'risk',      label: 'Risk',      w: 'w-16',  align: 'right' },
  { key: 'score',     label: 'Score',     w: 'w-16',  align: 'right' },
  { key: 'gm',        label: 'Gross Mgn', w: 'w-24',  align: 'right' },
  { key: 'roic',      label: 'ROIC',      w: 'w-20',  align: 'right' },
  { key: 'fcf',       label: 'FCF Yld',   w: 'w-20',  align: 'right' },
  { key: 'revgth',    label: 'Rev Gth',   w: 'w-20',  align: 'right' },
  { key: 'ndebitda',  label: 'ND/EBITDA', w: 'w-24',  align: 'right' },
  { key: 'status',    label: 'Status',    w: 'w-28',  align: 'left'  },
]

function RankBadge({ rank }) {
  if (rank <= 3) return (
    <span className="inline-flex items-center justify-center w-6 h-6 rounded-full
                     bg-gradient-to-br from-gold-400 to-gold-600 text-white
                     font-mono text-[11px] font-bold shadow-gold">
      {rank}
    </span>
  )
  return <span className="font-mono text-xs text-stone-400">{rank}</span>
}

function TableRow({ row, rank, selected, onClick }) {
  return (
    <tr
      onClick={onClick}
      className={clsx(
        'data-row group',
        selected && 'bg-gold-50/50 border-b-gold-200'
      )}
    >
      <td className="px-5 py-3"><RankBadge rank={rank} /></td>
      <td className="px-3 py-3">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-sm font-bold text-stone-800">{row.ticker}</span>
          {row.founder_led && (
            <span className="tag bg-blue-50 text-blue-600 ring-1 ring-blue-200">F</span>
          )}
          {row.inspired_by && (
            <span className="tag bg-gold-50 text-gold-700 ring-1 ring-gold-200">
              ↳ {row.inspired_by}
            </span>
          )}
        </div>
        <div className="text-[10px] text-stone-400 mt-0.5">{row.exchange} · {row.country}</div>
      </td>
      <td className="px-3 py-3 max-w-[176px]">
        <div className="text-sm text-stone-700 truncate">{row.name}</div>
        <div className="text-[10px] text-stone-400 truncate mt-0.5">{row.sector}</div>
      </td>
      <td className="px-3 py-3 text-right font-mono text-sm text-stone-600">{fmtCap(row.market_cap)}</td>
      <td className="px-3 py-3 text-right"><ScorePill score={row.fit_score} /></td>
      <td className="px-3 py-3 text-right"><ScorePill score={row.risk_score} inverted /></td>
      <td className="px-3 py-3 text-right"><ScorePill score={row.rank_score} /></td>
      <td className="px-3 py-3 text-right font-mono text-sm text-stone-600">{fmtPct(row.gross_margin)}</td>
      <td className="px-3 py-3 text-right font-mono text-sm text-stone-600">{fmtPct(row.roic)}</td>
      <td className="px-3 py-3 text-right font-mono text-sm text-stone-600">{fmtPct(row.fcf_yield)}</td>
      <td className="px-3 py-3 text-right font-mono text-sm text-stone-600">{fmtPct(row.revenue_growth_yoy)}</td>
      <td className="px-3 py-3 text-right font-mono text-sm text-stone-600">{fmtMult(row.net_debt_ebitda)}</td>
      <td className="px-3 py-3"><StatusBadge status={row.status} /></td>
    </tr>
  )
}

// ── Detail Drawer ─────────────────────────────────────────────────────────────
function DetailDrawer({ row, onClose, onFeedback }) {
  const [tab, setTab]           = useState('memo')
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [submitting, setSubmitting]     = useState(false)

  const TABS = ['memo', 'scoring', 'diligence', 'actions']

  const handleFeedback = async (action, reason = null) => {
    setSubmitting(true)
    try {
      await api.feedback(row.ticker, action, reason)
      onFeedback(row.ticker, action)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <motion.div
      initial={{ x: '100%', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: '100%', opacity: 0 }}
      transition={{ type: 'spring', damping: 32, stiffness: 350 }}
      className="fixed right-0 top-0 bottom-0 w-[540px] bg-white border-l border-stone-150
                 shadow-luxury-lg z-30 flex flex-col overflow-hidden"
    >
      {/* Header */}
      <div className="px-7 pt-7 pb-5 border-b border-stone-100 flex-shrink-0">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-2xl font-bold text-stone-900">{row.ticker}</span>
              {row.founder_led && (
                <span className="tag bg-blue-50 text-blue-600 ring-1 ring-blue-200">Founder-Led</span>
              )}
              <StatusBadge status={row.status} />
            </div>
            <div className="text-sm text-stone-500">{row.name}</div>
            <div className="text-xs text-stone-400 mt-0.5">
              {row.exchange} · {row.country} · {row.sector}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xs hover:bg-stone-100 text-stone-400 hover:text-stone-600 transition"
          >
            <X size={16} />
          </button>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-4 gap-3 mt-5">
          {[
            { label: 'Fit Score',  value: row.fit_score,   pill: true },
            { label: 'Risk Score', value: row.risk_score,  pill: true, inv: true },
            { label: 'Rank Score', value: row.rank_score?.toFixed(1) },
            { label: 'Mkt Cap',    value: fmtCap(row.market_cap) },
          ].map(({ label, value, pill, inv }) => (
            <div key={label} className="bg-stone-50 rounded-xs p-3 border border-stone-100">
              <div className="section-label mb-1.5">{label}</div>
              {pill
                ? <ScorePill score={value} inverted={inv} size="lg" />
                : <div className="font-mono text-lg font-semibold text-stone-800">{value}</div>
              }
            </div>
          ))}
        </div>
      </div>

      {/* Verdict banner */}
      {(row.verdict || row.thesis) && (
        <div className="px-7 pt-4 pb-2 flex-shrink-0">
          <VerdictBanner verdict={row.verdict} thesis={row.thesis} />
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-stone-100 px-7 flex-shrink-0">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={clsx(
              'py-3 pr-5 text-xs font-semibold tracking-wide uppercase transition-colors relative',
              tab === t
                ? 'text-stone-900 after:absolute after:bottom-0 after:left-0 after:right-4 after:h-0.5 after:bg-gold-500'
                : 'text-stone-400 hover:text-stone-600'
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto px-7 py-5">
        {tab === 'memo' && (
          <div className="animate-fade-in">
            {row.memo_text
              ? <p className="text-sm text-stone-600 leading-relaxed whitespace-pre-line">
                  {row.memo_text}
                </p>
              : <p className="text-sm text-stone-400 italic">No memo generated — re-run screening.</p>
            }
          </div>
        )}

        {tab === 'scoring' && (
          <div className="animate-fade-in">
            {row.dimensions?.length > 0 ? (
              <>
                <div className="section-label mb-4">AI Analyst Dimensions</div>
                {row.dimensions.map(d => (
                  <ScoreBar
                    key={d.name}
                    score={d.score}
                    label={d.label}
                    evidence={d.evidence}
                  />
                ))}
              </>
            ) : (
              <p className="text-sm text-stone-400">No scoring detail available.</p>
            )}
          </div>
        )}

        {tab === 'diligence' && (
          <div className="animate-fade-in">
            {row.diligence?.length > 0 ? (
              <>
                <div className="section-label mb-4">Key Diligence Questions</div>
                <div className="space-y-3">
                  {row.diligence.map((q, i) => (
                    <div key={i} className="flex gap-3 p-4 bg-amber-50 border border-amber-100 rounded-xs">
                      <span className="font-mono text-xs font-bold text-gold-600 flex-shrink-0 mt-0.5">
                        {i + 1}.
                      </span>
                      <p className="text-sm text-stone-700 leading-relaxed">{q}</p>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-sm text-stone-400">No diligence questions generated.</p>
            )}
          </div>
        )}

        {tab === 'actions' && (
          <div className="animate-fade-in space-y-4">
            <div className="section-label mb-4">Analyst Decision</div>

            <div className="grid grid-cols-3 gap-2">
              <ActionBtn
                label="Research Now"
                color="emerald"
                active={row.verdict === 'RESEARCH NOW'}
                disabled={submitting}
                onClick={() => handleFeedback('research_now')}
              />
              <ActionBtn
                label="Watch"
                color="amber"
                disabled={submitting}
                onClick={() => handleFeedback('watch')}
              />
              <ActionBtn
                label="Pass"
                color="stone"
                disabled={submitting}
                onClick={() => setFeedbackOpen(f => !f)}
              />
            </div>

            {feedbackOpen && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 bg-stone-50 border border-stone-200 rounded-xs space-y-3"
              >
                <div className="section-label">Pass Reason</div>
                <select
                  value={rejectReason}
                  onChange={e => setRejectReason(e.target.value)}
                  className="w-full py-2 px-3 text-sm bg-white border border-stone-200 rounded-xs
                             focus:outline-none focus:border-gold-400"
                >
                  <option value="">Select reason…</option>
                  {[
                    'Too expensive', 'Weak moat / low quality', 'Poor unit economics',
                    'No insider alignment', 'Too well-covered', 'Limited growth runway',
                    'Too risky', 'Already known',
                    ...(row.diligence?.slice(0, 3).map(q => `Unresolved: ${q.slice(0, 60)}`) ?? []),
                  ].map(r => <option key={r} value={r}>{r}</option>)}
                </select>
                <button
                  disabled={submitting || !rejectReason}
                  onClick={() => handleFeedback('reject', rejectReason)}
                  className="w-full py-2 text-sm font-medium bg-stone-800 text-white rounded-xs
                             hover:bg-stone-900 disabled:opacity-40 transition"
                >
                  Confirm Pass
                </button>
              </motion.div>
            )}

            {/* Financials summary */}
            <div className="mt-6">
              <div className="section-label mb-3">Key Metrics</div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: 'Gross Margin',  value: fmtPct(row.gross_margin) },
                  { label: 'ROIC',          value: fmtPct(row.roic) },
                  { label: 'FCF Yield',     value: fmtPct(row.fcf_yield) },
                  { label: 'Rev Growth',    value: fmtPct(row.revenue_growth_yoy) },
                  { label: 'ND / EBITDA',   value: fmtMult(row.net_debt_ebitda) },
                  { label: 'EV / EBIT',     value: fmtMult(row.ev_ebit) },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between px-3 py-2 bg-stone-50 border border-stone-100 rounded-xs">
                    <span className="text-xs text-stone-500">{label}</span>
                    <span className="font-mono text-xs font-semibold text-stone-800">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}

function ActionBtn({ label, color, active, disabled, onClick }) {
  const colors = {
    emerald: 'bg-emerald-600 hover:bg-emerald-700 text-white',
    amber:   'bg-amber-500 hover:bg-amber-600 text-white',
    stone:   'bg-white hover:bg-stone-50 text-stone-700 border border-stone-200',
  }
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'py-2.5 text-sm font-medium rounded-xs transition disabled:opacity-40',
        colors[color],
        active && 'ring-2 ring-offset-1 ring-emerald-500'
      )}
    >
      {label}
    </button>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function ResultsPage() {
  const { data: rows, loading, error, reload } = useApi(() => api.recommendations(500))
  const [selected, setSelected] = useState(null)
  const [filters, setFilters]   = useState({
    search: '', minFit: '0', maxRisk: '100', status: '', sector: '', sort: 'score'
  })

  const filtered = useMemo(() => {
    if (!rows) return []
    let out = [...rows]

    if (filters.search) {
      const s = filters.search.toUpperCase()
      out = out.filter(r => r.ticker.includes(s) || (r.name || '').toUpperCase().includes(s))
    }
    if (+filters.minFit  > 0)   out = out.filter(r => r.fit_score  >= +filters.minFit)
    if (+filters.maxRisk < 100) out = out.filter(r => r.risk_score  < +filters.maxRisk)
    if (filters.status)         out = out.filter(r => r.status === filters.status)
    if (filters.sector)         out = out.filter(r => r.sector === filters.sector)

    if (filters.sort === 'fit')  out.sort((a, b) => b.fit_score  - a.fit_score)
    else if (filters.sort === 'risk') out.sort((a, b) => a.risk_score - b.risk_score)
    else if (filters.sort === 'mcap') out.sort((a, b) => (b.market_cap ?? 0) - (a.market_cap ?? 0))
    else                         out.sort((a, b) => b.rank_score - a.rank_score)

    return out
  }, [rows, filters])

  const selectedRow = selected ? filtered.find(r => r.ticker === selected) : null

  const handleFeedback = (ticker, action) => {
    // Optimistic update
    reload()
    setSelected(null)
  }

  return (
    <div className="relative">
      {/* Overlay when drawer is open */}
      <AnimatePresence>
        {selectedRow && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelected(null)}
            className="fixed inset-0 bg-stone-900/10 z-20"
          />
        )}
      </AnimatePresence>

      <div className={clsx(
        'transition-all duration-300',
        selectedRow ? 'pr-[540px]' : ''
      )}>
        {/* Page header */}
        <div className="px-10 pt-10 pb-0">
          <div className="flex items-end justify-between mb-8">
            <div>
              <div className="section-label mb-2">Screening Results</div>
              <h2 className="font-display text-4xl font-light text-stone-800">
                Ranked Universe
              </h2>
            </div>
            <button
              onClick={reload}
              className="text-xs text-stone-400 hover:text-gold-600 transition flex items-center gap-1.5 pb-1"
            >
              Refresh
            </button>
          </div>

          {loading && <div className="mb-4"><TableSkeleton rows={4} cols={10} /></div>}
          {error   && (
            <div className="mb-4 p-4 bg-red-50 border border-red-100 rounded-xs text-sm text-red-600">
              Failed to load: {error}
            </div>
          )}

          {!loading && rows && (
            <>
              <StatsBar rows={filtered} />
              <FilterBar rows={rows} filters={filters} setFilters={setFilters} />
            </>
          )}
        </div>

        {/* Table */}
        {!loading && filtered.length > 0 && (
          <div className="px-10 pb-16">
            <div className="bg-white border border-stone-150 rounded-sm shadow-luxury overflow-hidden">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-stone-150 bg-stone-50/70">
                    {COLS.map(c => (
                      <th
                        key={c.key}
                        className={clsx(
                          'px-3 py-3 first:px-5',
                          'text-[10px] font-semibold tracking-[0.12em] uppercase text-stone-400',
                          c.align === 'right' && 'text-right',
                          c.w
                        )}
                      >
                        {c.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row, i) => (
                    <TableRow
                      key={row.ticker}
                      row={row}
                      rank={row.rank ?? (i + 1)}
                      selected={selected === row.ticker}
                      onClick={() => setSelected(selected === row.ticker ? null : row.ticker)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {!loading && !error && filtered.length === 0 && rows?.length > 0 && (
          <div className="px-10 py-20 text-center">
            <p className="text-stone-400 text-sm">No companies match the current filters.</p>
          </div>
        )}

        {!loading && !error && (!rows || rows.length === 0) && (
          <div className="px-10 py-24 text-center">
            <div className="section-label mb-4">No data</div>
            <p className="font-display text-3xl font-light text-stone-300 mb-3">No results yet</p>
            <p className="text-sm text-stone-400">Run a screening to populate the universe.</p>
          </div>
        )}
      </div>

      {/* Detail drawer */}
      <AnimatePresence>
        {selectedRow && (
          <DetailDrawer
            row={selectedRow}
            onClose={() => setSelected(null)}
            onFeedback={handleFeedback}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
