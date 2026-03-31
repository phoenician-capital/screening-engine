import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import clsx from 'clsx'
import { api } from '../api'
import AgentVisualization from '../components/AgentVisualization'
import ScreeningProgress from '../components/ScreeningProgress'
import ScorePill from '../components/ScorePill'

const fmtCap = v => {
  if (v == null) return '—'
  if (v >= 1e9) return `$${(v/1e9).toFixed(1)}B`
  if (v >= 1e6) return `$${(v/1e6).toFixed(0)}M`
  return `$${v.toLocaleString()}`
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
  const [job, setJob] = useState(null)
  const [topN, setTopN] = useState(null)
  const [starting, setStarting] = useState(false)
  const [events, setEvents] = useState([])
  const [view, setView] = useState('progress') // 'progress' or 'agents'

  // Poll job status
  useEffect(() => {
    api.screeningStatus().then(s => {
      if (s && (s.running || s.done)) setJob(s)
      if (s?.done && !s.running) loadTopN()
    }).catch(() => {})
  }, [])

  // Subscribe to SSE events
  useEffect(() => {
    const eventSource = new EventSource('/api/v1/screening/events')

    const handleMessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        setEvents(prev => [...prev, data])
      } catch (e) {
        console.error('Failed to parse SSE event:', e)
      }
    }

    eventSource.addEventListener('message', handleMessage)

    return () => {
      eventSource.removeEventListener('message', handleMessage)
      eventSource.close()
    }
  }, [])

  // Poll job status during run
  useEffect(() => {
    if (!job?.running) return
    const id = setInterval(async () => {
      try {
        const s = await api.screeningStatus()
        setJob(s)
        if (s.done && !s.running) {
          clearInterval(id)
          loadTopN()
        }
      } catch {}
    }, 3500)
    return () => clearInterval(id)
  }, [job?.running])

  const loadTopN = async () => {
    try {
      setTopN(await api.recommendations(10))
    } catch {}
  }

  const startRun = async () => {
    setStarting(true)
    setTopN(null)
    setEvents([])
    setView('agents') // Switch to agent visualization when running
    try {
      const res = await api.startScreening(maxCompanies)
      if (res.ok) {
        setJob(await api.screeningStatus())
      } else {
        alert(res.message)
      }
    } catch (e) {
      alert(`Failed to start: ${e.message}`)
    } finally {
      setStarting(false)
    }
  }

  const isRunning = job?.running
  const isDone = job?.done

  return (
    <div className="px-10 pt-10 pb-16">
      <div className="mb-8">
        <div className="section-label mb-2">Engine</div>
        <h2 className="font-display text-4xl font-light text-stone-800">Run Screening</h2>
        <p className="text-sm text-stone-500 mt-2">Watch the multi-agent system work in real-time</p>
      </div>

      {/* Controls */}
      <div className="stat-card mb-6 max-w-sm">
        <div className="flex items-end gap-6 mb-5">
          <div>
            <label className="block text-xs text-stone-500 mb-1.5">Companies to screen</label>
            <input
              type="number"
              min={5}
              max={500}
              step={5}
              value={maxCompanies}
              onChange={e => setMaxCompanies(Math.min(500, Math.max(5, +e.target.value)))}
              disabled={isRunning}
              className="w-24 py-2 px-3 text-sm font-mono bg-stone-50 border border-stone-200 rounded-xs
                         focus:outline-none focus:border-gold-400 disabled:opacity-40"
            />
          </div>
        </div>

        <button
          onClick={startRun}
          disabled={isRunning || starting}
          className={clsx(
            'w-full py-2.5 text-sm font-semibold rounded-xs transition-all',
            isRunning || starting
              ? 'bg-stone-100 text-stone-400 cursor-not-allowed'
              : 'bg-stone-900 text-white hover:bg-stone-800 shadow-luxury'
          )}
        >
          {isRunning ? '⚙️ Run in Progress…' : starting ? '⏳ Starting…' : '▶ Execute Screening Run'}
        </button>

        {isRunning && (
          <p className="text-center text-xs text-stone-400 mt-2 font-mono">{job?.elapsed ?? 0}s elapsed</p>
        )}
      </div>

      {/* View toggle — only show during/after run */}
      {(isRunning || isDone) && (
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setView('progress')}
            className={clsx(
              'px-4 py-2 text-sm font-medium rounded-xs transition',
              view === 'progress'
                ? 'bg-stone-900 text-white'
                : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
            )}
          >
            📊 Progress
          </button>
          <button
            onClick={() => setView('agents')}
            className={clsx(
              'px-4 py-2 text-sm font-medium rounded-xs transition',
              view === 'agents'
                ? 'bg-stone-900 text-white'
                : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
            )}
          >
            🤖 Agents
          </button>
        </div>
      )}

      {/* Content */}
      {isRunning || isDone ? (
        <motion.div
          key={view}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-8"
        >
          {view === 'progress' && (
            <ScreeningProgress status={job} events={events} />
          )}

          {view === 'agents' && (
            <AgentVisualization events={events} />
          )}
        </motion.div>
      ) : null}

      {/* Results */}
      {isDone && !job?.error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          <MiniTable rows={topN} />
        </motion.div>
      )}

      {/* Error */}
      {job?.error && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm"
        >
          <div className="font-semibold mb-1">❌ Screening failed</div>
          <p className="font-mono text-xs">{job.error}</p>
        </motion.div>
      )}
    </div>
  )
}
