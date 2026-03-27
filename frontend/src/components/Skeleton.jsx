import clsx from 'clsx'

export function Skeleton({ className }) {
  return <div className={clsx('skeleton', className)} />
}

export function TableSkeleton({ rows = 8, cols = 10 }) {
  return (
    <div className="animate-fade-in">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-5 py-3.5 border-b border-stone-100">
          <Skeleton className="w-6 h-6 rounded-full" />
          <Skeleton className="w-14 h-3.5" />
          <Skeleton className="w-40 h-3.5" />
          {Array.from({ length: cols - 3 }).map((_, j) => (
            <Skeleton key={j} className="w-16 h-3.5 ml-auto" />
          ))}
        </div>
      ))}
    </div>
  )
}
