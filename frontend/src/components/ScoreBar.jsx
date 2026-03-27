import clsx from 'clsx'

export default function ScoreBar({ score, label, evidence, showPct = true }) {
  const pct = Math.min(100, Math.max(0, score ?? 0))
  const color = pct >= 65 ? '#10b981' : pct >= 40 ? '#f59e0b' : '#ef4444'

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-medium text-stone-600">{label}</span>
        {showPct && (
          <span className="font-mono text-xs font-semibold" style={{ color }}>
            {Math.round(pct)}
          </span>
        )}
      </div>
      <div className="h-1 bg-stone-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${color}60, ${color})` }}
        />
      </div>
      {evidence && (
        <p className="mt-1.5 text-[11px] text-stone-400 leading-relaxed">{evidence}</p>
      )}
    </div>
  )
}
