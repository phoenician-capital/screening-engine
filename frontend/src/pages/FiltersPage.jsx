import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { api } from '../api'
import { Skeleton } from '../components/Skeleton'

function Section({ title, sub, children }) {
  return (
    <div className="mb-8">
      <div className="mb-4 pb-3 border-b border-stone-150">
        <div className="text-xs font-semibold tracking-[0.14em] uppercase text-gold-600">{title}</div>
        {sub && <div className="text-xs text-stone-400 mt-1">{sub}</div>}
      </div>
      {children}
    </div>
  )
}

function NumberField({ label, value, onChange, min, max, step = 1, suffix }) {
  return (
    <div>
      <label className="block text-xs text-stone-500 mb-1.5">{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value}
          onChange={e => onChange(+e.target.value)}
          min={min} max={max} step={step}
          className="w-28 py-2 px-3 text-sm font-mono bg-white border border-stone-200 rounded-xs
                     focus:outline-none focus:border-gold-400 focus:ring-1 focus:ring-gold-200"
        />
        {suffix && <span className="text-xs text-stone-400">{suffix}</span>}
      </div>
    </div>
  )
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer group">
      <div
        onClick={() => onChange(!checked)}
        className={`w-9 h-5 rounded-full transition-colors relative flex-shrink-0 ${
          checked ? 'bg-stone-800' : 'bg-stone-200'
        }`}
      >
        <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
          checked ? 'translate-x-4' : 'translate-x-0.5'
        }`} />
      </div>
      <span className="text-sm text-stone-600 group-hover:text-stone-800 transition-colors">{label}</span>
    </label>
  )
}

export default function FiltersPage() {
  const { data: cfg, loading } = useApi(api.settings)
  const [saved, setSaved]      = useState(false)
  const [local, setLocal]      = useState(null)

  useEffect(() => {
    if (cfg) setLocal(JSON.parse(JSON.stringify(cfg)))
  }, [cfg])

  const hard  = local?.hard_filters ?? {}
  const rank  = local?.ranking ?? {}

  const setHard = (key, val) => setLocal(l => ({ ...l, hard_filters: { ...l.hard_filters, [key]: val } }))
  const setRank = (key, val) => setLocal(l => ({ ...l, ranking: { ...l.ranking, [key]: val } }))

  const save = async () => {
    try {
      await api.saveSettings(local)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      alert(`Save failed: ${e.message}`)
    }
  }

  if (loading || !local) return (
    <div className="px-10 pt-10 pb-16">
      <div className="section-label mb-2">Configuration</div>
      <div className="font-display text-4xl font-light text-stone-800 mb-8">Filters &amp; Settings</div>
      <Skeleton className="h-96 rounded-sm" />
    </div>
  )

  return (
    <div className="px-10 pt-10 pb-16 max-w-3xl">
      {/* Header */}
      <div className="flex items-end justify-between mb-10">
        <div>
          <div className="section-label mb-2">Configuration</div>
          <h2 className="font-display text-4xl font-light text-stone-800">
            Filters &amp; Settings
          </h2>
          <p className="text-sm text-stone-400 mt-2">Changes take effect on the next screening run.</p>
        </div>
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={save}
          className="flex items-center gap-2 px-5 py-2.5 bg-stone-900 text-white text-sm font-medium
                     rounded-xs hover:bg-stone-800 transition shadow-luxury"
        >
          {saved && <CheckCircle size={14} className="text-emerald-400" />}
          {saved ? 'Saved' : 'Save Changes'}
        </motion.button>
      </div>

      {/* Hard Filters */}
      <Section title="Hard Filters" sub="Companies failing any active filter are excluded before scoring.">
        <div className="bg-white border border-stone-150 rounded-sm shadow-luxury p-6">
          <div className="grid grid-cols-3 gap-6">
            <NumberField
              label="Min Market Cap"
              value={Math.round((hard.hard_min_market_cap ?? 100_000_000) / 1e6)}
              onChange={v => setHard('hard_min_market_cap', v * 1e6)}
              min={0} max={5000}
              suffix="$M"
            />
            <NumberField
              label="Max Market Cap"
              value={Math.round((hard.hard_max_market_cap ?? 10_000_000_000) / 1e9)}
              onChange={v => setHard('hard_max_market_cap', v * 1e9)}
              min={1} max={200}
              suffix="$B"
            />
            <NumberField
              label="Max ND / EBITDA"
              value={hard.max_leverage ?? 5.0}
              onChange={v => setHard('max_leverage', v)}
              min={0} max={20} step={0.5}
              suffix="×"
            />
          </div>

          <div className="mt-6 pt-5 border-t border-stone-100 space-y-3">
            <Toggle
              label="Exclude financial intermediaries (banks, insurers)"
              checked={hard.exclude_financials !== false}
              onChange={v => setHard('exclude_financials', v)}
            />
            <Toggle
              label="Exclude commodities and capital-intensive cyclicals"
              checked={hard.exclude_commodities !== false}
              onChange={v => setHard('exclude_commodities', v)}
            />
            <Toggle
              label="Require minimum gross margin threshold"
              checked={hard.require_gross_margin !== false}
              onChange={v => setHard('require_gross_margin', v)}
            />
          </div>
        </div>
      </Section>

      {/* Ranking */}
      <Section title="Ranking" sub="Controls how final rank scores are computed.">
        <div className="bg-white border border-stone-150 rounded-sm shadow-luxury p-6">
          <div className="grid grid-cols-3 gap-6">
            <NumberField
              label="Top N results to persist"
              value={rank.top_n_results ?? 50}
              onChange={v => setRank('top_n_results', v)}
              min={5} max={500}
            />
            <NumberField
              label="Fit score weight %"
              value={rank.fit_weight_pct ?? 70}
              onChange={v => setRank('fit_weight_pct', v)}
              min={50} max={95}
              suffix="%"
            />
            <NumberField
              label="Min fit score to rank"
              value={rank.min_fit_score ?? 30}
              onChange={v => setRank('min_fit_score', v)}
              min={0} max={80}
            />
          </div>
        </div>
      </Section>

      {/* Raw YAML preview */}
      <Section title="Raw Configuration" sub="Full scoring_weights.yaml — read-only preview.">
        <div className="bg-stone-950 rounded-sm p-5 overflow-auto max-h-80">
          <pre className="text-[11px] font-mono text-stone-400 leading-relaxed whitespace-pre">
            {JSON.stringify(local, null, 2)}
          </pre>
        </div>
      </Section>
    </div>
  )
}
