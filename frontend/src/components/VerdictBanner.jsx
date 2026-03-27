import clsx from 'clsx'

const CFG = {
  'RESEARCH NOW': {
    tag: 'verdict-research',
    bg: 'bg-emerald-50 border-emerald-100',
    text: 'text-emerald-800',
    label: 'Research Now',
  },
  'WATCH': {
    tag: 'verdict-watch',
    bg: 'bg-amber-50 border-amber-100',
    text: 'text-amber-800',
    label: 'Watch',
  },
  'PASS': {
    tag: 'verdict-pass',
    bg: 'bg-stone-50 border-stone-200',
    text: 'text-stone-600',
    label: 'Pass',
  },
}

export default function VerdictBanner({ verdict, thesis }) {
  if (!verdict && !thesis) return null
  const c = CFG[verdict] ?? CFG['PASS']

  return (
    <div className={clsx('rounded-sm border px-5 py-4', c.bg)}>
      <div className="flex items-center gap-3 mb-2">
        <span className={clsx('tag', c.tag)}>{c.label}</span>
        <span className="section-label">AI Analyst Verdict</span>
      </div>
      {thesis && (
        <p className={clsx('text-sm leading-relaxed italic font-serif', c.text)}>
          &ldquo;{thesis}&rdquo;
        </p>
      )}
    </div>
  )
}
