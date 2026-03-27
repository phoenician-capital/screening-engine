import clsx from 'clsx'

const CONFIG = {
  pending:     { label: 'Pending',     cls: 'bg-stone-100 text-stone-500 ring-stone-200' },
  researching: { label: 'Researching', cls: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  watched:     { label: 'Watched',     cls: 'bg-amber-50 text-amber-700 ring-amber-200' },
  rejected:    { label: 'Passed',      cls: 'bg-red-50 text-red-600 ring-red-200' },
}

export default function StatusBadge({ status }) {
  const c = CONFIG[status] ?? { label: status, cls: 'bg-stone-100 text-stone-500' }
  return (
    <span className={clsx('tag ring-1', c.cls)}>
      {c.label}
    </span>
  )
}
