import clsx from 'clsx'

export default function ScorePill({ score, inverted = false, size = 'sm' }) {
  if (score == null) return <span className="text-stone-300 font-mono text-xs">—</span>

  let cls
  if (inverted) {
    cls = score >= 60 ? 'score-pill-red' : score >= 35 ? 'score-pill-amber' : 'score-pill-green'
  } else {
    cls = score >= 70 ? 'score-pill-green' : score >= 50 ? 'score-pill-amber' : 'score-pill-red'
  }

  return (
    <span className={clsx('score-pill', cls, size === 'lg' && 'text-sm px-3 py-1')}>
      {Math.round(score)}
    </span>
  )
}
