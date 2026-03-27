import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Loader, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react'
import clsx from 'clsx'
import { useApi } from '../hooks/useApi'
import { api } from '../api'
import { Skeleton } from '../components/Skeleton'
import ScorePill from '../components/ScorePill'

const fmt    = (v, digits = 1) => v == null ? null : Number(v).toFixed(digits)
const fmtPct = v => v == null ? null : `${Number(v).toFixed(1)}%`
const fmtMkt = v => {
  if (v == null) return null
  if (v >= 1e9) return `$${(v/1e9).toFixed(1)}B`
  if (v >= 1e6) return `$${(v/1e6).toFixed(0)}M`
  return `$${v.toLocaleString()}`
}

function Metric({ label, value, positive }) {
  if (value == null) return null
  return (
    <div>
      <div className="text-[10px] font-semibold tracking-[0.1em] uppercase text-stone-400 mb-0.5">{label}</div>
      <div className={clsx('font-mono text-sm font-semibold', positive ? 'text-stone-800' : 'text-stone-800')}>{value}</div>
    </div>
  )
}

function VerdictChip({ verdict }) {
  if (!verdict) return null
  const v = verdict.trim().toUpperCase()
  if (v.includes('RESEARCH'))  return <span className="tag bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200 text-[10px] font-bold tracking-wider">Research Now</span>
  if (v.includes('WATCH'))     return <span className="tag bg-gold-50 text-gold-700 ring-1 ring-gold-200 text-[10px] font-bold tracking-wider">Watch</span>
  if (v.includes('PASS'))      return <span className="tag bg-stone-100 text-stone-500 ring-1 ring-stone-200 text-[10px] font-bold tracking-wider">Pass</span>
  return <span className="tag bg-stone-100 text-stone-500 text-[10px]">{verdict}</span>
}

function HoldingCard({ h, i }) {
  const [open, setOpen] = useState(false)
  const scored = h.fit_score != null

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: i * 0.04 }}
      className="bg-white border border-stone-150 rounded-sm shadow-luxury overflow-hidden"
    >
      {/* Card header */}
      <div
        className="px-5 py-4 flex items-start justify-between cursor-pointer hover:bg-stone-50/50 transition-colors"
        onClick={() => scored && setOpen(o => !o)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2.5 mb-1">
            <span className="font-mono text-sm font-bold text-stone-800">{h.ticker}</span>
            {h.rank && <span className="text-[10px] font-mono text-stone-400">#{h.rank}</span>}
            <VerdictChip verdict={h.verdict} />
            {!scored && <span className="text-[10px] text-stone-300 italic">not yet scanned</span>}
          </div>
          <div className="text-sm text-stone-600 truncate">{h.name}</div>
          {h.sector && <div className="text-xs text-stone-400 mt-0.5">{h.sector}</div>}
        </div>

        {/* Scores */}
        {scored && (
          <div className="flex items-center gap-2 ml-4 flex-shrink-0">
            <div className="text-right">
              <div className="text-[9px] uppercase tracking-widest text-stone-300 mb-1">Fit</div>
              <ScorePill score={h.fit_score} />
            </div>
            <div className="text-right">
              <div className="text-[9px] uppercase tracking-widest text-stone-300 mb-1">Risk</div>
              <ScorePill score={h.risk_score} inverted />
            </div>
          </div>
        )}
      </div>

      {/* Metrics bar */}
      {scored && (
        <div className="px-5 pb-4 flex flex-wrap gap-x-6 gap-y-2 border-t border-stone-50">
          <div className="pt-3 flex gap-6">
            <Metric label="Gross Mgn"   value={fmtPct(h.gross_margin)} />
            <Metric label="ROIC"        value={fmtPct(h.roic)} />
            <Metric label="Rev Growth"  value={fmtPct(h.revenue_growth)} />
            <Metric label="FCF Yield"   value={fmtPct(h.fcf_yield)} />
            <Metric label="ND/EBITDA"   value={h.net_debt_ebitda != null ? `${fmt(h.net_debt_ebitda)}x` : null} />
            <Metric label="EV/EBIT"     value={h.ev_ebit != null ? `${fmt(h.ev_ebit)}x` : null} />
            <Metric label="Mkt Cap"     value={fmtMkt(h.market_cap)} />
          </div>
        </div>
      )}

      {/* Expandable thesis */}
      {scored && open && h.thesis && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="border-t border-stone-100 px-5 py-4 bg-stone-50/40"
        >
          <div className="text-[10px] uppercase tracking-widest text-stone-400 mb-2">Analyst Thesis</div>
          <p className="text-sm text-stone-600 leading-relaxed italic">{h.thesis}</p>

          {h.diligence?.length > 0 && (
            <div className="mt-4">
              <div className="text-[10px] uppercase tracking-widest text-stone-400 mb-2">Key Questions</div>
              <div className="space-y-2">
                {h.diligence.map((q, qi) => (
                  <div key={qi} className="flex gap-2.5">
                    <span className="flex-shrink-0 w-4 h-4 rounded-full bg-gold-100 text-gold-700 text-[10px] font-bold flex items-center justify-center mt-0.5">{qi+1}</span>
                    <p className="text-xs text-stone-500 leading-relaxed">{q}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      )}
    </motion.div>
  )
}

function InsiderRow({ p }) {
  const fmtDate = v => v ? new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'
  return (
    <div className={clsx(
      'flex items-center gap-4 px-5 py-3.5 border-b border-stone-100 last:border-0',
      p.is_cluster && 'bg-gold-50/30'
    )}>
      <div className="flex-shrink-0">
        <span className="font-mono text-sm font-bold text-stone-800">{p.ticker}</span>
        {p.is_cluster && <span className="ml-2 tag bg-gold-50 text-gold-700 ring-1 ring-gold-200">Cluster</span>}
        {p.near_52wk_low && <span className="ml-1 tag bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200">52wk Low</span>}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm text-stone-700 truncate">{p.insider_name}</div>
        <div className="text-xs text-stone-400">{p.insider_title}</div>
      </div>
      <div className="text-right flex-shrink-0">
        <div className="font-mono text-sm font-semibold text-stone-800">
          {p.total_value ? `$${(p.total_value/1e3).toFixed(0)}K` : '—'}
        </div>
        <div className="text-xs text-stone-400">{fmtDate(p.transaction_date)}</div>
      </div>
    </div>
  )
}

export default function PortfolioPage() {
  const { data: portfolio, loading: loadP, reload: reloadPortfolio } = useApi(api.portfolio)
  const { data: insiders,  loading: loadI } = useApi(() => api.insiders(30))

  const [scan, setScan]         = useState(null)
  const [scanning, setScanning] = useState(false)

  const holdings = portfolio?.holdings ?? []
  const clusters = insiders?.cluster_buys ?? []
  const recent   = insiders?.recent?.slice(0, 15) ?? []

  const scored   = holdings.filter(h => h.fit_score != null)
  const unscored = holdings.filter(h => h.fit_score == null)

  useEffect(() => {
    if (!scan?.running) return
    const id = setInterval(async () => {
      try {
        const s = await api.screeningStatus()
        setScan(s)
        if (s.done && !s.running) { clearInterval(id); reloadPortfolio() }
      } catch {}
    }, 3000)
    return () => clearInterval(id)
  }, [scan?.running])

  const startScan = async () => {
    setScan(null)
    setScanning(true)
    try {
      const res = await api.scanPortfolio()
      if (res.ok) setScan(await api.screeningStatus())
      else alert(res.message)
    } catch (e) {
      alert(`Scan failed: ${e.message}`)
    } finally {
      setScanning(false)
    }
  }

  return (
    <div className="px-10 pt-10 pb-16">
      {/* Header */}
      <div className="flex items-end justify-between mb-8">
        <div>
          <div className="section-label mb-2">Portfolio</div>
          <h2 className="font-display text-4xl font-light text-stone-800">Holdings</h2>
          {scored.length > 0 && (
            <p className="text-sm text-stone-400 mt-1">{scored.length} scored · {unscored.length} pending scan</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {scan?.running && (
            <span className="text-xs font-mono text-gold-600 animate-pulse-soft">{scan.elapsed ?? 0}s · {scan.d1 || scan.d2 || 'running…'}</span>
          )}
          {scan?.done && !scan?.error && (
            <span className="flex items-center gap-1.5 text-xs text-emerald-600 font-semibold">
              <CheckCircle size={13} /> Complete · {scan.scored} scored
            </span>
          )}
          {scan?.error && (
            <span className="flex items-center gap-1.5 text-xs text-red-500">
              <AlertCircle size={13} /> {scan.error}
            </span>
          )}
          <button
            onClick={startScan}
            disabled={scan?.running || scanning}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-xs transition-all',
              scan?.running || scanning
                ? 'bg-stone-100 text-stone-400 cursor-not-allowed'
                : 'bg-stone-900 text-white hover:bg-stone-800 shadow-luxury'
            )}
          >
            {scan?.running
              ? <><Loader size={13} className="animate-spin" /> Scanning…</>
              : <><RefreshCw size={13} /> Scan Portfolio</>
            }
          </button>
        </div>
      </div>

      <div className="grid grid-cols-[1fr_320px] gap-8">
        {/* Holdings cards */}
        <div>
          {loadP ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-24 rounded-sm" />)}
            </div>
          ) : holdings.length === 0 ? (
            <div className="bg-white border border-stone-150 rounded-sm p-12 text-center">
              <p className="font-display text-2xl font-light text-stone-300">No holdings</p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Scored first */}
              {scored.map((h, i) => <HoldingCard key={h.ticker} h={h} i={i} />)}
              {/* Unscored at bottom, muted */}
              {unscored.length > 0 && (
                <>
                  {scored.length > 0 && (
                    <div className="text-[10px] uppercase tracking-widest text-stone-300 pt-2 pb-1">Pending scan</div>
                  )}
                  {unscored.map((h, i) => <HoldingCard key={h.ticker} h={h} i={scored.length + i} />)}
                </>
              )}
            </div>
          )}
        </div>

        {/* Sidebar: insider activity */}
        <div>
          <div className="section-label mb-4">Insider Activity — 30d</div>
          {loadI ? (
            <Skeleton className="h-48 rounded-sm" />
          ) : clusters.length === 0 && recent.length === 0 ? (
            <div className="bg-white border border-stone-150 rounded-sm shadow-luxury p-6 text-center">
              <p className="text-sm text-stone-400">No purchases on record</p>
            </div>
          ) : (
            <>
              {clusters.length > 0 && (
                <div className="mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-semibold text-stone-700">Cluster Buys</span>
                    <span className="tag bg-gold-50 text-gold-700 ring-1 ring-gold-200">{clusters.length}</span>
                  </div>
                  <div className="bg-white border border-stone-150 rounded-sm shadow-luxury overflow-hidden">
                    {clusters.slice(0, 5).map((p, i) => <InsiderRow key={i} p={p} />)}
                  </div>
                </div>
              )}
              {recent.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-stone-700 mb-2">Recent Purchases</div>
                  <div className="bg-white border border-stone-150 rounded-sm shadow-luxury overflow-hidden">
                    {recent.map((p, i) => <InsiderRow key={i} p={p} />)}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
