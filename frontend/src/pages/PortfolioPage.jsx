import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Loader, RefreshCw, ChevronDown, ChevronUp, ExternalLink, Newspaper, Calendar, AlertCircle } from 'lucide-react'
import clsx from 'clsx'
import { useApi } from '../hooks/useApi'
import { api } from '../api'
import { Skeleton } from '../components/Skeleton'

const fmtDate = v => {
  if (!v) return null
  try { return new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }
  catch { return v }
}

const EVENT_TYPE_LABEL = {
  earnings_date:   'Earnings',
  agm:             'AGM',
  presentation:    'Presentation',
  annual_report:   'Annual Report',
  interim_report:  'Interim Report',
  press_release:   'Press Release',
  webcast:         'Webcast',
  other:           'Event',
}

const EVENT_TYPE_COLOR = {
  earnings_date:  'bg-gold-50 text-gold-700 ring-gold-200',
  annual_report:  'bg-blue-50 text-blue-700 ring-blue-200',
  interim_report: 'bg-blue-50 text-blue-700 ring-blue-200',
  presentation:   'bg-violet-50 text-violet-700 ring-violet-200',
  press_release:  'bg-stone-100 text-stone-600 ring-stone-200',
  agm:            'bg-emerald-50 text-emerald-700 ring-emerald-200',
  webcast:        'bg-emerald-50 text-emerald-700 ring-emerald-200',
}

function EventChip({ type }) {
  const label = EVENT_TYPE_LABEL[type] ?? 'Event'
  const color = EVENT_TYPE_COLOR[type] ?? 'bg-stone-100 text-stone-500 ring-stone-200'
  return <span className={`tag ring-1 text-[10px] font-semibold ${color}`}>{label}</span>
}

function SignalsPanel({ ticker }) {
  const { data, loading, error } = useApi(() => api.tickerSignals(ticker, 5), [ticker])

  if (loading) return (
    <div className="px-5 pb-4 pt-2 space-y-2">
      <Skeleton className="h-10 rounded-sm" />
      <Skeleton className="h-10 rounded-sm" />
    </div>
  )

  if (error) return (
    <div className="px-5 pb-4 pt-2 flex items-center gap-2 text-xs text-red-400">
      <AlertCircle size={12} /> Failed to load signals
    </div>
  )

  const irEvents = data?.ir_events ?? []
  const news     = data?.news ?? []
  const hasAny   = irEvents.length > 0 || news.length > 0

  if (!hasAny) return (
    <div className="px-5 pb-5 pt-2 text-xs text-stone-400">
      No signals found — run IR Scan to fetch events, or no recent news available.
    </div>
  )

  return (
    <div className="px-5 pb-5 pt-1 space-y-4">
      {/* IR Events */}
      {irEvents.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Calendar size={11} className="text-stone-400" />
            <span className="text-[10px] uppercase tracking-widest font-semibold text-stone-400">IR Events</span>
          </div>
          <div className="space-y-2">
            {irEvents.map((ev, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <EventChip type={ev.event_type} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-stone-700 leading-snug">{ev.title}</span>
                    {ev.url && (
                      <a href={ev.url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0">
                        <ExternalLink size={10} className="text-stone-300 hover:text-gold-500 transition-colors" />
                      </a>
                    )}
                  </div>
                  {ev.event_date && <div className="text-[10px] text-stone-400 mt-0.5">{fmtDate(ev.event_date)}</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* News */}
      {news.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <Newspaper size={11} className="text-stone-400" />
            <span className="text-[10px] uppercase tracking-widest font-semibold text-stone-400">Recent News</span>
          </div>
          <div className="space-y-2.5">
            {news.map((article, i) => (
              <div key={i}>
                <div className="flex items-start gap-2">
                  <div className="flex-1 min-w-0">
                    {article.url ? (
                      <a href={article.url} target="_blank" rel="noopener noreferrer"
                         className="text-xs text-stone-700 hover:text-gold-600 transition-colors leading-snug line-clamp-2">
                        {article.title}
                      </a>
                    ) : (
                      <span className="text-xs text-stone-700 leading-snug line-clamp-2">{article.title}</span>
                    )}
                    {article.published_at && (
                      <div className="text-[10px] text-stone-400 mt-0.5">{fmtDate(article.published_at)}</div>
                    )}
                    {article.snippet && (
                      <p className="text-[11px] text-stone-400 mt-0.5 line-clamp-2 leading-relaxed">{article.snippet}</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function HoldingCard({ h, i }) {
  const [open, setOpen] = useState(false)

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: i * 0.035 }}
      className="bg-white border border-stone-150 rounded-sm shadow-luxury overflow-hidden"
    >
      <div
        className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-stone-50/50 transition-colors"
        onClick={() => setOpen(o => !o)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2.5 mb-0.5">
            <span className="font-mono text-sm font-bold text-stone-800">{h.ticker}</span>
            {h.sector && <span className="text-xs text-stone-400">{h.sector}</span>}
          </div>
          <div className="text-sm text-stone-600 truncate">{h.name}</div>
        </div>
        <div className="flex items-center gap-3 ml-4 flex-shrink-0">
          {open
            ? <ChevronUp size={14} className="text-stone-400" />
            : <ChevronDown size={14} className="text-stone-400" />
          }
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="border-t border-stone-100 overflow-hidden"
          >
            <SignalsPanel ticker={h.ticker} />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default function PortfolioPage() {
  const { data: portfolio, loading: loadP } = useApi(api.portfolio)

  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState(null)
  const [scanError, setScanError]   = useState(null)

  const holdings = portfolio?.holdings ?? []

  const runIRScan = async () => {
    setScanning(true)
    setScanResult(null)
    setScanError(null)
    try {
      const res = await api.scanIR()
      setScanResult(res)
    } catch (e) {
      setScanError(e.message)
    } finally {
      setScanning(false)
    }
  }

  return (
    <div className="px-10 pt-10 pb-16 max-w-3xl">
      {/* Header */}
      <div className="flex items-end justify-between mb-8">
        <div>
          <div className="section-label mb-2">Portfolio</div>
          <h2 className="font-display text-4xl font-light text-stone-800">Holdings</h2>
          {!loadP && holdings.length > 0 && (
            <p className="text-sm text-stone-400 mt-1">{holdings.length} active holdings</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {scanResult && (
            <span className="text-xs text-emerald-600 font-semibold">
              {scanResult.new_events} new IR events found
            </span>
          )}
          {scanError && (
            <span className="text-xs text-red-500">{scanError}</span>
          )}
          <button
            onClick={runIRScan}
            disabled={scanning}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-xs transition-all',
              scanning
                ? 'bg-stone-100 text-stone-400 cursor-not-allowed'
                : 'bg-stone-900 text-white hover:bg-stone-800 shadow-luxury'
            )}
          >
            {scanning
              ? <><Loader size={13} className="animate-spin" /> Scanning IR…</>
              : <><RefreshCw size={13} /> IR Scan</>
            }
          </button>
        </div>
      </div>

      <p className="text-xs text-stone-400 mb-6">
        Click any holding to see IR events and recent news. Run <strong>IR Scan</strong> to refresh event calendars from investor relations pages.
      </p>

      {loadP ? (
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-16 rounded-sm" />)}
        </div>
      ) : (
        <div className="space-y-2">
          {holdings.map((h, i) => <HoldingCard key={h.ticker} h={h} i={i} />)}
        </div>
      )}
    </div>
  )
}
