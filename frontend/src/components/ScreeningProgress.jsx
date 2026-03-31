import { motion } from 'framer-motion'
import clsx from 'clsx'

/**
 * Real-time screening progress dashboard with live metrics.
 */
export default function ScreeningProgress({ status, events = [] }) {
  const lastEvent = events[events.length - 1]

  // Extract metrics from events
  const discovery = lastEvent?.type === 'discovery_complete' ? {
    complete: true,
    count: lastEvent.tickers_found,
    elapsed: lastEvent.elapsed,
  } : { complete: false }

  const scoring = lastEvent?.type === 'screening_complete' || lastEvent?.type === 'screening_done' ? {
    complete: true,
    count: lastEvent.scored,
    elapsed: lastEvent.elapsed,
  } : { complete: false }

  const isRunning = status?.running
  const isDone = status?.done
  const hasError = status?.error

  return (
    <div className="w-full space-y-6">
      {/* Status bar */}
      <div className="bg-white border border-stone-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="font-semibold text-stone-900">Screening Status</h3>
            <p className="text-sm text-stone-500 mt-1">
              {hasError && `Error: ${hasError}`}
              {isRunning && `Step ${status.step}/3: ${status.step_label}`}
              {isDone && !hasError && '✨ Screening complete'}
            </p>
          </div>
          <div className="text-right">
            {isRunning && (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                className="text-2xl"
              >
                ⚙️
              </motion.div>
            )}
            {isDone && !hasError && <div className="text-3xl">✅</div>}
            {hasError && <div className="text-3xl">❌</div>}
          </div>
        </div>

        {/* Progress steps */}
        <div className="space-y-3">
          <ProgressStep
            step={1}
            label="Universe Discovery"
            description={discovery.complete ? `${discovery.count} candidates found` : 'Fetching companies...'}
            complete={discovery.complete}
            time={discovery.elapsed}
            active={status?.step === 1}
          />
          <ProgressStep
            step={2}
            label="Selection Team Pre-Filter"
            description={discovery.complete ? 'Running 5 agents on candidates' : 'Waiting...'}
            complete={status?.step > 2}
            active={status?.step === 2}
          />
          <ProgressStep
            step={3}
            label="Scoring Team Analysis"
            description={scoring.complete ? `${scoring.count} companies scored` : 'Analyzing pre-filtered candidates...'}
            complete={scoring.complete}
            time={scoring.elapsed}
            active={status?.step === 3}
          />
        </div>
      </div>

      {/* Key metrics grid */}
      {discovery.complete && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-4 gap-4"
        >
          <MetricBox
            label="Universe Size"
            value={discovery.count}
            unit="companies"
            icon="🌍"
            color="blue"
          />
          <MetricBox
            label="Discovery Time"
            value={discovery.elapsed?.toFixed(1)}
            unit="seconds"
            icon="⏱️"
            color="amber"
          />
          <MetricBox
            label="Pre-Filtered"
            value={scoring.complete ? scoring.count : '—'}
            unit="candidates"
            icon="⚡"
            color="emerald"
          />
          <MetricBox
            label="Cost Saved"
            value={scoring.complete ? `~${((discovery.count - scoring.count) * 1).toFixed(0)}` : '—'}
            unit="USD"
            icon="💰"
            color="gold"
          />
        </motion.div>
      )}

      {/* Event log */}
      {events.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-lg p-4">
          <h4 className="font-semibold text-sm mb-3 text-stone-900">Event Log</h4>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {[...events].reverse().slice(0, 10).map((event, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="text-xs text-stone-600 p-2 bg-stone-50 rounded flex items-start gap-2"
              >
                <span className="text-stone-400 flex-shrink-0 min-w-fit">
                  {new Date(event.timestamp * 1000).toLocaleTimeString()}
                </span>
                <span className="text-stone-700">
                  {eventLabel(event)}
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ProgressStep({ step, label, description, complete, time, active }) {
  return (
    <div className="flex items-start gap-4">
      <div className="relative">
        <div className={clsx(
          'w-8 h-8 rounded-full flex items-center justify-center font-semibold text-sm flex-shrink-0',
          complete ? 'bg-emerald-100 text-emerald-700' :
          active ? 'bg-blue-100 text-blue-700 ring-2 ring-blue-300' :
          'bg-stone-100 text-stone-400'
        )}>
          {complete ? '✓' : step}
        </div>
        {step < 3 && (
          <motion.div
            animate={{ scaleY: active ? 1 : 0.3 }}
            className="absolute top-8 left-4 w-0.5 h-8 bg-stone-200 origin-top"
          />
        )}
      </div>
      <div className="flex-1 pt-1">
        <div className={clsx(
          'font-semibold text-sm',
          complete ? 'text-emerald-700' :
          active ? 'text-blue-700' :
          'text-stone-400'
        )}>
          {label}
        </div>
        <p className="text-xs text-stone-600 mt-1">{description}</p>
        {time && (
          <p className="text-xs text-stone-400 mt-1">
            {time.toFixed(1)}s elapsed
          </p>
        )}
      </div>
    </div>
  )
}

function MetricBox({ label, value, unit, icon, color }) {
  const colorMap = {
    blue: 'bg-blue-50 border-blue-200 text-blue-600',
    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-600',
    amber: 'bg-amber-50 border-amber-200 text-amber-600',
    gold: 'bg-yellow-50 border-yellow-200 text-yellow-600',
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={clsx('p-4 border rounded-lg', colorMap[color])}
    >
      <div className="text-2xl mb-2">{icon}</div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs opacity-75">{unit}</div>
      <div className="text-xs font-semibold mt-2 opacity-75">{label}</div>
    </motion.div>
  )
}

function eventLabel(event) {
  switch (event.type) {
    case 'screening_started':
      return 'Screening started'
    case 'discovery_complete':
      return `Discovered ${event.tickers_found} companies`
    case 'screening_complete':
      return `Scored ${event.scored} companies`
    case 'screening_done':
      return 'Screening complete'
    case 'screening_error':
      return `Error: ${event.error}`
    default:
      return event.type
  }
}
