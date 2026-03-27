import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle, Loader, AlertCircle } from 'lucide-react'
import clsx from 'clsx'
import { api } from '../api'
import ScorePill from '../components/ScorePill'

const fmtCap = v => {
  if (v == null) return '—'
  if (v >= 1e9) return `$${(v/1e9).toFixed(1)}B`
  if (v >= 1e6) return `$${(v/1e6).toFixed(0)}M`
  return `$${v.toLocaleString()}`
}

function Step({ n, label, status, detail }) {
  const icons = {
    waiting: <span className="w-6 h-6 rounded-full border-2 border-stone-200 flex items-center justify-center font-mono text-xs text-stone-300">{n}</span>,
    running: <span className="w-6 h-6 rounded-full border-2 border-gold-400 flex items-center justify-center"><Loader size={12} className="text-gold-500 animate-spin" /></span>,
    done:    <span className="w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center"><CheckCircle size={12} className="text-white" /></span>,
    error:   <span className="w-6 h-6 rounded-full bg-red-500 flex items-center justify-center"><AlertCircle size={12} className="text-white" /></span>,
  }

  return (
    <div className={clsx(
      'flex items-center gap-4 px-5 py-3 transition-colors',
      status === 'running' && 'bg-gold-50/40'
    )}>
      <div className="flex-shrink-0">{icons[status] ?? icons.waiting}</div>
      <div className="flex-1 min-w-0">
        <span className={clsx(
          'text-sm transition-colors',
          status === 'running' ? 'text-stone-900 font-semibold' :
          status === 'done'    ? 'text-stone-500' : 'text-stone-300'
        )}>
          {label}
        </span>
        {detail && <span className="ml-2 text-xs text-stone-400 font-mono">{detail}</span>}
      </div>
    </div>
  )
}

function MiniTable({ rows }) {
  if (!rows?.length) return null
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="mt-8"
    >
      <div className="section-label mb-3">Top Results</div>
      <div className="bg-white border border-stone-150 rounded-sm shadow-luxury overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-stone-50/70 border-b border-stone-150">
              {['#', 'Ticker', 'Company', 'Mkt Cap', 'Fit', 'Risk', 'Score'].map((h, i) => (
                <th key={h} className={clsx(
                  'py-3 text-[10px] font-semibold tracking-[0.12em] uppercase text-stone-400',
                  i === 0 ? 'pl-5 pr-3' : 'px-3',
                  i > 3 && 'text-right'
                )}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.ticker} className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60 transition-colors">
                <td className="pl-5 pr-3 py-3">
                  {i < 3
                    ? <span className="inline-flex w-5 h-5 rounded-full bg-gradient-to-br from-gold-400 to-gold-600 text-white items-center justify-center font-mono text-[10px] font-bold">{r.rank ?? i+1}</span>
                    : <span className="font-mono text-xs text-stone-400">{r.rank ?? i+1}</span>
                  }
                </td>
                <td className="px-3 py-3 font-mono text-sm font-bold text-stone-800">{r.ticker}</td>
                <td className="px-3 py-3 text-sm text-stone-600 max-w-[180px] truncate">{r.name}</td>
                <td className="px-3 py-3 font-mono text-sm text-stone-500">{fmtCap(r.market_cap)}</td>
                <td className="px-3 py-3 text-right"><ScorePill score={r.fit_score} /></td>
                <td className="px-3 py-3 text-right"><ScorePill score={r.risk_score} inverted /></td>
                <td className="px-3 py-3 text-right"><ScorePill score={r.rank_score} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}

export default function ScreeningPage() {
  const [maxCompanies, setMaxCompanies] = useState(20)
  const [job, setJob]                   = useState(null)
  const [topN, setTopN]                 = useState(null)
  const [starting, setStarting]         = useState(false)

  useEffect(() => {
    api.screeningStatus().then(s => {
      if (s && (s.running || s.done)) setJob(s)
      if (s?.done && !s.running) loadTopN()
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!job?.running) return
    const id = setInterval(async () => {
      try {
        const s = await api.screeningStatus()
        setJob(s)
        if (s.done && !s.running) { clearInterval(id); loadTopN() }
      } catch {}
    }, 3500)
    return () => clearInterval(id)
  }, [job?.running])

  const loadTopN = async () => {
    try { setTopN(await api.recommendations(10)) } catch {}
  }

  const startRun = async () => {
    setStarting(true)
    setTopN(null)
    try {
      const res = await api.startScreening(maxCompanies)
      if (res.ok) setJob(await api.screeningStatus())
      else alert(res.message)
    } catch (e) {
      alert(`Failed to start: ${e.message}`)
    } finally {
      setStarting(false)
    }
  }

  const stepStatus = n => {
    if (!job) return 'waiting'
    if (job.error) return n <= job.step ? (n < job.step ? 'done' : 'error') : 'waiting'
    if (job.done) return 'done'
    if (job.step === n) return 'running'
    if (job.step > n) return 'done'
    return 'waiting'
  }

  const STEPS = [
    { label: 'Discover companies',   detail: job?.d1 },
    { label: 'Score with AI analyst', detail: job?.d2 },
    { label: 'Rank & persist',        detail: job?.d3 },
  ]

  return (
    <div className="px-10 pt-10 pb-16 max-w-2xl">
      <div className="mb-8">
        <div className="section-label mb-2">Engine</div>
        <h2 className="font-display text-4xl font-light text-stone-800">Run Screening</h2>
      </div>

      {/* Controls */}
      <div className="stat-card mb-5">
        <div className="flex items-end gap-6 mb-5">
          <div>
            <label className="block text-xs text-stone-500 mb-1.5">Companies to screen</label>
            <input
              type="number"
              min={5} max={500} step={5}
              value={maxCompanies}
              onChange={e => setMaxCompanies(Math.min(500, Math.max(5, +e.target.value)))}
              disabled={job?.running}
              className="w-24 py-2 px-3 text-sm font-mono bg-stone-50 border border-stone-200 rounded-xs
                         focus:outline-none focus:border-gold-400 disabled:opacity-40"
            />
          </div>
        </div>

        <button
          onClick={startRun}
          disabled={job?.running || starting}
          className={clsx(
            'w-full py-2.5 text-sm font-semibold rounded-xs transition-all',
            job?.running || starting
              ? 'bg-stone-100 text-stone-400 cursor-not-allowed'
              : 'bg-stone-900 text-white hover:bg-stone-800 shadow-luxury'
          )}
        >
          {job?.running ? 'Run in Progress…' : starting ? 'Starting…' : 'Execute Screening Run'}
        </button>

        {job?.running && (
          <p className="text-center text-xs text-stone-400 mt-2 font-mono">{job.elapsed ?? 0}s elapsed</p>
        )}
      </div>

      {/* Progress */}
      {job && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white border border-stone-150 rounded-sm shadow-luxury overflow-hidden mb-2"
        >
          <div className={clsx(
            'px-5 py-2.5 border-b border-stone-100 flex items-center justify-between',
            job.done && !job.error && 'bg-emerald-50',
            job.error && 'bg-red-50',
            job.running && 'bg-gold-50/50',
          )}>
            <span className={clsx(
              'section-label',
              job.done && !job.error && 'text-emerald-600',
              job.error && 'text-red-500',
              job.running && 'text-gold-600',
            )}>
              {job.error ? 'Failed' : job.done ? 'Complete' : 'Running'}
            </span>
            {job.done && !job.error && (
              <span className="text-xs font-mono text-emerald-600">{job.elapsed}s · {job.scored} scored</span>
            )}
          </div>

          <div className="divide-y divide-stone-100">
            {STEPS.map((s, i) => (
              <Step key={i} n={i + 1} label={s.label} status={stepStatus(i + 1)} detail={s.detail} />
            ))}
          </div>

          {job.error && (
            <div className="px-5 py-3 bg-red-50 border-t border-red-100">
              <p className="text-xs text-red-600 font-mono">{job.error}</p>
            </div>
          )}
        </motion.div>
      )}

      <MiniTable rows={topN} />
    </div>
  )
}
