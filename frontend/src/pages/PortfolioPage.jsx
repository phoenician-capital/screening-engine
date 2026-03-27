import { motion } from 'framer-motion'
import clsx from 'clsx'
import { useApi } from '../hooks/useApi'
import { api } from '../api'
import { Skeleton } from '../components/Skeleton'

const fmtPct   = v => v == null ? '—' : `${Number(v).toFixed(1)}%`
const fmtMult  = v => v == null ? '—' : `${v.toFixed(1)}x`
const fmtDate  = v => v ? new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'
const fmtMoney = v => {
  if (v == null) return '—'
  if (v >= 1e6) return `$${(v/1e6).toFixed(1)}M`
  if (v >= 1e3) return `$${(v/1e3).toFixed(0)}K`
  return `$${v.toFixed(0)}`
}

function InsiderRow({ p }) {
  return (
    <div className={clsx(
      'flex items-center gap-4 px-5 py-3.5 border-b border-stone-100 last:border-0',
      p.is_cluster && 'bg-gold-50/30'
    )}>
      <div className="flex-shrink-0">
        <span className="font-mono text-sm font-bold text-stone-800">{p.ticker}</span>
        {p.is_cluster && (
          <span className="ml-2 tag bg-gold-50 text-gold-700 ring-1 ring-gold-200">Cluster</span>
        )}
        {p.near_52wk_low && (
          <span className="ml-1 tag bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200">52wk Low</span>
        )}
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
  const { data: portfolio, loading: loadP } = useApi(api.portfolio)
  const { data: insiders,  loading: loadI } = useApi(() => api.insiders(30))

  const holdings = portfolio?.holdings ?? []
  const summary  = portfolio?.summary  ?? {}
  const clusters = insiders?.cluster_buys ?? []
  const recent   = insiders?.recent?.slice(0, 20) ?? []

  const hasMetrics = summary.avg_gross_margin != null || summary.avg_roic != null

  return (
    <div className="px-10 pt-10 pb-16">
      {/* Header */}
      <div className="mb-8">
        <div className="section-label mb-2">Portfolio</div>
        <h2 className="font-display text-4xl font-light text-stone-800">Holdings</h2>
      </div>

      {/* Summary — only show if we have metric data */}
      {!loadP && hasMetrics && (
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Holdings',      value: holdings.length,                    accent: 'border-t-gold-400' },
            { label: 'Avg Gross Mgn', value: fmtPct(summary.avg_gross_margin),   accent: 'border-t-emerald-500' },
            { label: 'Avg ROIC',      value: fmtPct(summary.avg_roic),           accent: 'border-t-blue-500' },
            { label: 'Avg Rev Growth',value: fmtPct(summary.avg_revenue_growth), accent: 'border-t-violet-500' },
          ].map(c => (
            <div key={c.label} className={clsx('stat-card border-t-2', c.accent)}>
              <div className="section-label mb-2">{c.label}</div>
              <div className="font-mono text-2xl font-semibold text-stone-800">{c.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Holdings count badge when no metrics */}
      {!loadP && !hasMetrics && holdings.length > 0 && (
        <div className="flex items-center gap-3 mb-6">
          <span className="font-mono text-2xl font-semibold text-stone-800">{holdings.length}</span>
          <span className="text-sm text-stone-400">active holdings — run a screening pass to populate financial metrics</span>
        </div>
      )}

      <div className="grid grid-cols-[3fr_2fr] gap-8">
        {/* Holdings table */}
        <div>
          <div className="section-label mb-4">Current Holdings</div>
          {loadP ? (
            <Skeleton className="h-64 rounded-sm" />
          ) : holdings.length === 0 ? (
            <div className="bg-white border border-stone-150 rounded-sm p-10 text-center">
              <p className="font-display text-2xl font-light text-stone-300">No holdings</p>
            </div>
          ) : (
            <div className="bg-white border border-stone-150 rounded-sm shadow-luxury overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="bg-stone-50/70 border-b border-stone-150">
                    {['Ticker', 'Company', 'Sector', 'Added', hasMetrics && 'Gross Mgn', hasMetrics && 'ROIC'].filter(Boolean).map((h, i) => (
                      <th key={h} className={clsx(
                        'py-3 text-[10px] font-semibold tracking-[0.12em] uppercase text-stone-400',
                        i === 0 ? 'pl-5 pr-3' : 'px-3',
                        hasMetrics && i > 3 && 'text-right'
                      )}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((h, i) => (
                    <motion.tr
                      key={h.ticker}
                      initial={{ opacity: 0, x: -4 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.025 }}
                      className="border-b border-stone-100 last:border-0 hover:bg-stone-50/60 transition-colors"
                    >
                      <td className="pl-5 pr-3 py-3 font-mono text-sm font-bold text-stone-800">{h.ticker}</td>
                      <td className="px-3 py-3 text-sm text-stone-700 max-w-[160px] truncate">{h.name}</td>
                      <td className="px-3 py-3 text-xs text-stone-400 max-w-[100px] truncate">{h.sector ?? '—'}</td>
                      <td className="px-3 py-3 text-xs text-stone-500 font-mono">{fmtDate(h.date_added)}</td>
                      {hasMetrics && <td className="px-3 py-3 text-right font-mono text-sm text-stone-700">{fmtPct(h.entry_gross_margin)}</td>}
                      {hasMetrics && <td className="px-3 py-3 text-right font-mono text-sm text-stone-700">{fmtPct(h.entry_roic)}</td>}
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Insider activity */}
        <div>
          <div className="section-label mb-4">Insider Activity — Last 30 Days</div>
          {loadI ? (
            <Skeleton className="h-64 rounded-sm" />
          ) : clusters.length === 0 && recent.length === 0 ? (
            <div className="bg-white border border-stone-150 rounded-sm shadow-luxury p-8 text-center">
              <p className="text-sm text-stone-400">No insider purchases on record</p>
            </div>
          ) : (
            <>
              {clusters.length > 0 && (
                <div className="mb-5">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs font-semibold text-stone-700">Cluster Buys</span>
                    <span className="tag bg-gold-50 text-gold-700 ring-1 ring-gold-200">
                      {clusters.length} events
                    </span>
                  </div>
                  <div className="bg-white border border-stone-150 rounded-sm shadow-luxury overflow-hidden">
                    {clusters.slice(0, 6).map((p, i) => <InsiderRow key={i} p={p} />)}
                  </div>
                </div>
              )}

              {recent.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-stone-700 mb-3">Recent Purchases</div>
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
