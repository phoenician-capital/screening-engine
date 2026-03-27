import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import clsx from 'clsx'
import ResultsPage       from './pages/ResultsPage'
import ScreeningPage     from './pages/ScreeningPage'
import PortfolioPage     from './pages/PortfolioPage'
import FiltersPage       from './pages/FiltersPage'
import { usePoll } from './hooks/useApi'
import { api }           from './api'

const NAV = [
  { to: '/',          label: 'Run Screening',    sub: 'Execute & monitor' },
  { to: '/results',   label: 'Results',           sub: 'Ranked universe' },
  { to: '/portfolio', label: 'Portfolio Monitor', sub: 'Holdings & signals' },
  { to: '/filters',   label: 'Filters',           sub: 'Criteria & weights' },
]

function Sidebar() {
  const { data: stats } = usePoll(api.stats, 60000)
  const loc = useLocation()

  return (
    <aside className="fixed inset-y-0 left-0 w-64 bg-white border-r border-stone-150 flex flex-col z-20">
      {/* Brand */}
      <div className="px-7 pt-8 pb-6 border-b border-stone-100">
        <div className="section-label mb-3">Phoenician Capital</div>
        <h1 className="font-display text-3xl font-light text-stone-800 leading-tight">
          Screening<br />
          <span className="text-gold-600 italic">Engine</span>
        </h1>
        <div className="gold-rule mt-4" />
      </div>

      {/* Nav */}
      <nav className="flex-1 py-5 px-3">
        {NAV.map(({ to, label, sub }) => {
          const active = to === '/'
            ? loc.pathname === '/'
            : loc.pathname.startsWith(to)
          return (
            <NavLink
              key={to}
              to={to}
              className={clsx(
                'relative block px-4 py-3 rounded-xs mb-0.5 transition-all duration-150 group',
                active
                  ? 'bg-stone-50 border border-stone-150'
                  : 'border border-transparent hover:bg-stone-50/70'
              )}
            >
              {active && (
                <span className="absolute left-0 top-2 bottom-2 w-0.5 bg-gradient-to-b from-transparent via-gold-400 to-transparent rounded-full" />
              )}
              <div className={clsx(
                'text-sm font-medium transition-colors',
                active ? 'text-stone-900' : 'text-stone-500 group-hover:text-stone-700'
              )}>
                {label}
              </div>
              <div className="text-[11px] text-stone-400 mt-0.5">{sub}</div>
            </NavLink>
          )
        })}
      </nav>

      {/* Stats */}
      {stats && (
        <div className="mx-4 mb-4 p-4 bg-stone-50 rounded-sm border border-stone-150">
          <div className="section-label mb-3">Universe</div>
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: 'Ranked',    v: stats.ranked },
              { label: 'Research',  v: stats.in_research },
              { label: 'Watchlist', v: stats.on_watchlist },
              { label: 'Avg Fit',   v: stats.avg_fit_score },
            ].map(({ label, v }) => (
              <div key={label}>
                <div className="font-mono text-base font-semibold text-stone-800">{v ?? '—'}</div>
                <div className="text-[10px] text-stone-400">{label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-7 py-4 border-t border-stone-100">
        <p className="text-[10px] text-stone-300 tracking-wide">
          Confidential — Internal Use Only
        </p>
      </div>
    </aside>
  )
}

export default function App() {
  const loc = useLocation()

  return (
    <div className="flex min-h-screen bg-stone-50">
      <Sidebar />
      <main className="flex-1 ml-64 min-h-screen">
        <AnimatePresence mode="wait">
          <motion.div
            key={loc.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="min-h-screen"
          >
            <Routes>
              <Route path="/"          element={<ScreeningPage />} />
              <Route path="/results"   element={<ResultsPage />} />
              <Route path="/portfolio" element={<PortfolioPage />} />
              <Route path="/filters"   element={<FiltersPage />} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  )
}
