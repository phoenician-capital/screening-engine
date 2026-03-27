import { useState, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, X, Plus, Shield, TrendingDown, Globe, Building2, Filter } from 'lucide-react'
import { getData as getCountries } from 'country-list'
import { useApi } from '../hooks/useApi'
import { api } from '../api'
import { Skeleton } from '../components/Skeleton'
import { GICS_SECTORS, GICS_SUB_INDUSTRIES } from '../data/gics'

/* ─── primitives ─────────────────────────────────────────────── */

function Section({ icon: Icon, title, sub, children }) {
  return (
    <div className="mb-8">
      <div className="mb-4 pb-3 border-b border-stone-150 flex items-center gap-2.5">
        {Icon && <Icon size={13} className="text-gold-500 flex-shrink-0" />}
        <div>
          <div className="text-xs font-semibold tracking-[0.14em] uppercase text-gold-600">{title}</div>
          {sub && <div className="text-xs text-stone-400 mt-0.5">{sub}</div>}
        </div>
      </div>
      {children}
    </div>
  )
}

function NumberField({ label, hint, value, onChange, min, max, step = 1, suffix }) {
  return (
    <div>
      <label className="block text-xs font-medium text-stone-600 mb-1">{label}</label>
      {hint && <div className="text-[10px] text-stone-400 mb-1.5">{hint}</div>}
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

function Toggle({ label, hint, checked, onChange }) {
  return (
    <label className="flex items-start gap-3 cursor-pointer group">
      <div
        onClick={() => onChange(!checked)}
        className={`mt-0.5 w-9 h-5 rounded-full transition-colors relative flex-shrink-0 ${
          checked ? 'bg-stone-800' : 'bg-stone-200'
        }`}
      >
        <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
          checked ? 'translate-x-4' : 'translate-x-0.5'
        }`} />
      </div>
      <div>
        <span className="text-sm text-stone-700 group-hover:text-stone-900 transition-colors">{label}</span>
        {hint && <div className="text-[10px] text-stone-400 mt-0.5">{hint}</div>}
      </div>
    </label>
  )
}

/* ─── chip list (sectors / countries / tickers) ──────────────── */

// Built from gics.js — all 11 sector names
const SECTOR_OPTIONS = GICS_SECTORS.map(s => s.name)

// All ISO 3166-1 countries from country-list, shaped as { code, label }
const ALL_COUNTRIES = getCountries().map(c => ({ code: c.code, label: c.name }))

function ChipList({ items, onRemove, color = 'stone' }) {
  const colors = {
    stone: 'bg-stone-100 text-stone-700 ring-stone-200',
    red:   'bg-red-50 text-red-700 ring-red-200',
    amber: 'bg-amber-50 text-amber-700 ring-amber-200',
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map(item => (
        <span
          key={item}
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium ring-1 ${colors[color]}`}
        >
          {item}
          <button
            onClick={() => onRemove(item)}
            className="hover:opacity-60 transition-opacity ml-0.5"
          >
            <X size={9} strokeWidth={2.5} />
          </button>
        </span>
      ))}
    </div>
  )
}

function AddFromDropdown({ label, options, existing, onAdd, searchable = false }) {
  const [open, setOpen]     = useState(false)
  const [query, setQuery]   = useState('')

  const available = useMemo(() => {
    const base = options.filter(o => {
      const val = typeof o === 'object' ? o.code : o
      return !existing.includes(val)
    })
    if (!searchable || !query.trim()) return base
    const q = query.toLowerCase()
    return base.filter(o => {
      const text = typeof o === 'object' ? `${o.label} ${o.code}` : o
      return text.toLowerCase().includes(q)
    })
  }, [options, existing, query, searchable])

  return (
    <div className="relative">
      <button
        onClick={() => { setOpen(v => !v); setQuery('') }}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium
                   border border-dashed border-stone-300 rounded text-stone-500
                   hover:border-stone-400 hover:text-stone-700 transition-colors"
      >
        <Plus size={10} strokeWidth={2.5} /> {label}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.12 }}
            className="absolute z-20 mt-1 w-64 bg-white border border-stone-200 rounded-sm shadow-xl flex flex-col"
          >
            {searchable && (
              <div className="p-2 border-b border-stone-100">
                <input
                  autoFocus
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="Search…"
                  className="w-full px-2 py-1.5 text-xs bg-stone-50 border border-stone-200 rounded
                             focus:outline-none focus:border-gold-400"
                />
              </div>
            )}
            <div className="overflow-y-auto max-h-52">
              {available.length === 0
                ? <div className="px-3 py-3 text-xs text-stone-400">No matches</div>
                : available.map(o => {
                    const val  = typeof o === 'object' ? o.code : o
                    const text = typeof o === 'object' ? `${o.label} (${o.code})` : o
                    return (
                      <button
                        key={val}
                        onClick={() => { onAdd(val); setOpen(false); setQuery('') }}
                        className="w-full text-left px-3 py-2 text-xs text-stone-700 hover:bg-stone-50 transition-colors"
                      >
                        {text}
                      </button>
                    )
                  })
              }
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function AddTextInput({ placeholder, onAdd }) {
  const [val, setVal] = useState('')
  const submit = () => {
    const v = val.trim().toUpperCase()
    if (v) { onAdd(v); setVal('') }
  }
  return (
    <div className="flex items-center gap-2">
      <input
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && submit()}
        placeholder={placeholder}
        className="w-32 py-1.5 px-2.5 text-xs font-mono bg-white border border-stone-200 rounded-xs
                   focus:outline-none focus:border-gold-400 placeholder:text-stone-300 uppercase"
      />
      <button
        onClick={submit}
        className="inline-flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium bg-stone-900 text-white rounded hover:bg-stone-800 transition-colors"
      >
        <Plus size={10} /> Add
      </button>
    </div>
  )
}

/* ─── rule card ──────────────────────────────────────────────── */

function RuleCard({ rule, onRemove }) {
  return (
    <div className="flex items-start gap-3 px-4 py-3 bg-white border border-stone-150 rounded-sm shadow-luxury">
      <div className="flex-1 min-w-0">
        <div className="text-xs font-semibold text-stone-700">{rule.label}</div>
        <div className="text-[11px] text-stone-400 mt-0.5">{rule.description}</div>
      </div>
      <button
        onClick={onRemove}
        className="flex-shrink-0 mt-0.5 text-stone-300 hover:text-red-400 transition-colors"
      >
        <X size={13} />
      </button>
    </div>
  )
}

/* ─── main page ──────────────────────────────────────────────── */

const DEFAULT_EXCLUDED_SECTORS     = ['Energy', 'Utilities', 'Financials', 'Financial Services', 'Real Estate']
const DEFAULT_EXCLUDED_COUNTRIES   = ['CN', 'RU', 'IR', 'KP', 'SY', 'BY']

// Sub-industry options for the dropdown — name only (used as key)
const SUB_INDUSTRY_OPTIONS = GICS_SUB_INDUSTRIES.map(s => s.name).sort()

export default function FiltersPage() {
  const { data: cfg, loading } = useApi(api.settings)
  const [saved, setSaved]      = useState(false)
  const [local, setLocal]      = useState(null)

  // Editable exclusion lists — stored locally, saved to hard_filters
  const [exSectors,      setExSectors]      = useState(DEFAULT_EXCLUDED_SECTORS)
  const [exSubIndustries,setExSubIndustries] = useState([])
  const [exCountries,    setExCountries]    = useState(DEFAULT_EXCLUDED_COUNTRIES)
  const [exTickers,      setExTickers]      = useState([])

  useEffect(() => {
    if (cfg) {
      const copy = JSON.parse(JSON.stringify(cfg))
      setLocal(copy)

      const hf = copy.hard_filters ?? {}
      if (Array.isArray(hf.excluded_gics_sectors))
        setExSectors(hf.excluded_gics_sectors.filter(s => isNaN(+s)))
      if (Array.isArray(hf.excluded_gics_sub_industries))
        setExSubIndustries(hf.excluded_gics_sub_industries)
      if (Array.isArray(hf.excluded_countries))
        setExCountries(hf.excluded_countries.map(c => c.toUpperCase()))
      if (Array.isArray(hf.excluded_tickers))
        setExTickers(hf.excluded_tickers.map(t => t.toUpperCase()))
    }
  }, [cfg])

  const hard = local?.hard_filters ?? {}
  const rank = local?.ranking ?? {}

  const setHard = (key, val) =>
    setLocal(l => ({ ...l, hard_filters: { ...l.hard_filters, [key]: val } }))
  const setRank = (key, val) =>
    setLocal(l => ({ ...l, ranking: { ...l.ranking, [key]: val } }))

  const save = async () => {
    const payload = {
      ...local,
      hard_filters: {
        ...local.hard_filters,
        excluded_gics_sectors:          exSectors,
        excluded_gics_sub_industries:   exSubIndustries,
        excluded_countries:             exCountries,
        excluded_tickers:               exTickers,
      },
    }
    try {
      await api.saveSettings(payload)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      alert(`Save failed: ${e.message}`)
    }
  }

  if (loading || !local) return (
    <div className="px-10 pt-10 pb-16">
      <div className="section-label mb-2">Configuration</div>
      <div className="font-display text-4xl font-light text-stone-800 mb-8">Rules &amp; Filters</div>
      <Skeleton className="h-96 rounded-sm" />
    </div>
  )

  return (
    <div className="px-10 pt-10 pb-16 max-w-3xl">
      {/* Header */}
      <div className="flex items-end justify-between mb-10">
        <div>
          <div className="section-label mb-2">Configuration</div>
          <h2 className="font-display text-4xl font-light text-stone-800">Rules &amp; Filters</h2>
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

      {/* ── 1. Sector Exclusions ── */}
      <Section icon={Building2} title="Sector Exclusions" sub="Any company in these GICS sectors is excluded before scoring.">
        <div className="bg-white border border-stone-150 rounded-sm shadow-luxury p-5 space-y-4">
          <ChipList
            items={exSectors}
            onRemove={s => setExSectors(v => v.filter(x => x !== s))}
            color="stone"
          />
          <AddFromDropdown
            label="Add sector"
            options={SECTOR_OPTIONS}
            existing={exSectors}
            onAdd={s => setExSectors(v => [...v, s])}
          />
          <div className="text-[10px] text-stone-400 mt-1">
            {GICS_SECTORS.length} GICS sectors — use sub-industry exclusions below for finer control
          </div>
        </div>
      </Section>

      {/* ── 2. Sub-Industry Exclusions ── */}
      <Section icon={Building2} title="Sub-Industry Exclusions" sub="Granular GICS sub-industry exclusions within allowed sectors.">
        <div className="bg-white border border-stone-150 rounded-sm shadow-luxury p-5 space-y-4">
          {exSubIndustries.length > 0
            ? <ChipList items={exSubIndustries} onRemove={s => setExSubIndustries(v => v.filter(x => x !== s))} color="stone" />
            : <p className="text-xs text-stone-400">No sub-industry exclusions set.</p>
          }
          <AddFromDropdown
            label="Add sub-industry"
            options={SUB_INDUSTRY_OPTIONS}
            existing={exSubIndustries}
            onAdd={s => { if (!exSubIndustries.includes(s)) setExSubIndustries(v => [...v, s]) }}
            searchable
          />
          <div className="text-[10px] text-stone-400 mt-1">
            {GICS_SUB_INDUSTRIES.length} GICS sub-industries · type to search
          </div>
        </div>
      </Section>

      {/* ── 3. Country Exclusions ── */}
      <Section icon={Globe} title="Country Exclusions" sub="Companies domiciled in excluded countries are disqualified.">
        <div className="bg-white border border-stone-150 rounded-sm shadow-luxury p-5 space-y-4">
          <ChipList
            items={exCountries}
            onRemove={c => setExCountries(v => v.filter(x => x !== c))}
            color="red"
          />
          <AddFromDropdown
            label="Add country"
            options={ALL_COUNTRIES}
            existing={exCountries}
            onAdd={c => setExCountries(v => [...v, c])}
            searchable
          />
          <div className="text-[10px] text-stone-400 mt-1">
            {ALL_COUNTRIES.length} countries (ISO 3166-1) · type to search
          </div>
        </div>
      </Section>

      {/* ── 3. Ticker Exclusions ── */}
      <Section icon={Filter} title="Ticker Exclusions" sub="Specific companies to exclude regardless of score.">
        <div className="bg-white border border-stone-150 rounded-sm shadow-luxury p-5 space-y-4">
          {exTickers.length > 0
            ? <ChipList items={exTickers} onRemove={t => setExTickers(v => v.filter(x => x !== t))} color="amber" />
            : <p className="text-xs text-stone-400">No ticker exclusions set.</p>
          }
          <AddTextInput
            placeholder="e.g. TSLA"
            onAdd={t => { if (!exTickers.includes(t)) setExTickers(v => [...v, t]) }}
          />
        </div>
      </Section>

      {/* ── 4. Hard Filter Thresholds ── */}
      <Section icon={Shield} title="Hard Filter Thresholds" sub="Companies failing any threshold are excluded before scoring.">
        <div className="bg-white border border-stone-150 rounded-sm shadow-luxury p-6 space-y-6">

          <div className="grid grid-cols-2 gap-6">
            <NumberField
              label="Min Market Cap"
              hint="Raise to focus on larger, more liquid names"
              value={Math.round((hard.min_market_cap_usd ?? 250_000_000) / 1e6)}
              onChange={v => setHard('min_market_cap_usd', v * 1e6)}
              min={0} max={5000}
              suffix="$M"
            />
            <NumberField
              label="Max Market Cap"
              hint="Cap to stay under-followed (sweet spot ≤ $10B)"
              value={Math.round((hard.max_market_cap_usd ?? 10_000_000_000) / 1e9)}
              onChange={v => setHard('max_market_cap_usd', v * 1e9)}
              min={1} max={200}
              suffix="$B"
            />
            <NumberField
              label="Max Leverage"
              hint="Net debt / EBITDA ceiling"
              value={hard.max_leverage ?? 5.0}
              onChange={v => setHard('max_leverage', v)}
              min={0} max={20} step={0.5}
              suffix="× ND/EBITDA"
            />
            <NumberField
              label="Min Gross Margin"
              hint="Quality floor — excludes commodity-like businesses"
              value={Math.round((hard.min_gross_margin ?? 0.15) * 100)}
              onChange={v => setHard('min_gross_margin', v / 100)}
              min={0} max={80}
              suffix="%"
            />
            <NumberField
              label="Min Avg Daily Volume"
              hint="Liquidity floor to ensure tradeable positions"
              value={Math.round((hard.min_avg_daily_volume_usd ?? 250_000) / 1e3)}
              onChange={v => setHard('min_avg_daily_volume_usd', v * 1e3)}
              min={0} max={100_000}
              suffix="$K/day"
            />
            <NumberField
              label="Min Fit Score"
              hint="Minimum composite score to appear in results"
              value={hard.min_composite_score ?? 15}
              onChange={v => setHard('min_composite_score', v)}
              min={0} max={80}
              suffix="/ 100"
            />
          </div>

          <div className="pt-4 border-t border-stone-100 space-y-4">
            <Toggle
              label="Require profitability"
              hint="Exclude companies with negative net income"
              checked={hard.require_profitable !== false}
              onChange={v => setHard('require_profitable', v)}
            />
          </div>
        </div>
      </Section>

      {/* ── 5. Ranking Formula ── */}
      <Section icon={TrendingDown} title="Ranking Formula" sub="Controls how final rank scores are computed from fit and risk.">
        <div className="bg-white border border-stone-150 rounded-sm shadow-luxury p-6">
          <div className="grid grid-cols-3 gap-6">
            <NumberField
              label="Fit score weight"
              hint="Remainder goes to risk penalty"
              value={Math.round((rank.fit_weight ?? 0.70) * 100)}
              onChange={v => setRank('fit_weight', v / 100)}
              min={40} max={95}
              suffix="%"
            />
            <NumberField
              label="Top N to persist"
              hint="Limit results stored per run"
              value={rank.top_n_results ?? 50}
              onChange={v => setRank('top_n_results', v)}
              min={5} max={500}
            />
            <NumberField
              label="Feedback reject decay"
              hint="Score penalty per analyst reject (%)"
              value={Math.round((rank.feedback_decay_per_reject ?? 0.02) * 100)}
              onChange={v => setRank('feedback_decay_per_reject', v / 100)}
              min={0} max={20}
              suffix="%"
            />
          </div>
        </div>
      </Section>
    </div>
  )
}
