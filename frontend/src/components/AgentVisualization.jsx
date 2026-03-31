import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import clsx from 'clsx'

/**
 * Beautiful real-time visualization of the multi-agent screening system.
 * Shows Selection Team (pre-filter) → Scoring Team (analyze) flow.
 */
export default function AgentVisualization({ events = [] }) {
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [agentMetrics, setAgentMetrics] = useState({})
  const [activePhase, setActivePhase] = useState('discovery') // discovery, selection, scoring, complete

  // Parse events to update metrics
  useEffect(() => {
    if (events.length === 0) return

    const lastEvent = events[events.length - 1]

    if (lastEvent.type === 'screening_started') {
      setActivePhase('discovery')
    } else if (lastEvent.type === 'discovery_complete') {
      setActivePhase('selection')
      setAgentMetrics(m => ({
        ...m,
        discovery: { complete: true, count: lastEvent.tickers_found }
      }))
    } else if (lastEvent.type === 'screening_complete') {
      setActivePhase('scoring')
      setAgentMetrics(m => ({
        ...m,
        scoring: { complete: true, count: lastEvent.scored }
      }))
    } else if (lastEvent.type === 'screening_done') {
      setActivePhase('complete')
    }
  }, [events])

  return (
    <div className="w-full space-y-8">
      {/* Phase header */}
      <div className="text-center mb-8">
        <div className="section-label mb-2">Multi-Agent Screening System</div>
        <h3 className="font-display text-2xl font-light text-stone-800 mb-2">
          {activePhase === 'discovery' && '🔍 Discovering Universe'}
          {activePhase === 'selection' && '⚡ Selection Team Pre-Filtering'}
          {activePhase === 'scoring' && '🧠 Scoring Team Analyzing'}
          {activePhase === 'complete' && '✨ Screening Complete'}
        </h3>
        <p className="text-sm text-stone-500">
          {activePhase === 'discovery' && 'Fetching companies from EDGAR and international sources...'}
          {activePhase === 'selection' && 'Running 5 selection agents to pre-filter candidates...'}
          {activePhase === 'scoring' && 'Scoring pre-filtered companies with AI Analyst...'}
          {activePhase === 'complete' && 'All companies processed and ranked'}
        </p>
      </div>

      {/* Agent schema diagram */}
      <div className="bg-white border border-stone-200 rounded-lg p-8 shadow-sm">
        {/* DISCOVERY PHASE */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: activePhase === 'discovery' || activePhase === 'selection' || activePhase === 'scoring' ? 1 : 0.3 }}
          className="mb-12"
        >
          <AgentPhase
            title="Phase 1: Universe Discovery"
            agents={[
              { id: 'edgar', name: 'EDGAR', icon: '📄', description: 'US companies', color: 'blue' },
              { id: 'intl', name: 'International', icon: '🌍', description: 'Global companies', color: 'purple' },
            ]}
            output="1000 candidates"
            active={activePhase === 'discovery'}
            metrics={agentMetrics.discovery}
          />
        </motion.div>

        {/* Arrow */}
        <div className="flex justify-center mb-12">
          <motion.div
            animate={{ scale: activePhase !== 'discovery' ? 1 : 0.8, opacity: activePhase !== 'discovery' ? 1 : 0.5 }}
            className="h-12 relative"
          >
            <svg className="w-8 h-12" viewBox="0 0 32 48" fill="none">
              <motion.path
                d="M16 0 L16 40 M16 40 L10 34 M16 40 L22 34"
                stroke="currentColor"
                strokeWidth="2"
                className="text-stone-400"
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: activePhase !== 'discovery' ? 1 : 0 }}
                transition={{ duration: 0.8 }}
              />
            </svg>
          </motion.div>
        </div>

        {/* SELECTION TEAM PHASE */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: activePhase === 'selection' || activePhase === 'scoring' ? 1 : 0.3 }}
          className="mb-12"
        >
          <AgentPhase
            title="Phase 2: Selection Team (Pre-Filter)"
            agents={[
              { id: 'filter', name: 'Filter Agent', icon: '🔧', description: 'Hard metrics (margins, ROIC, debt)', color: 'emerald' },
              { id: 'business', name: 'Business Model', icon: '🏢', description: 'Is the business clear?', color: 'amber' },
              { id: 'founder', name: 'Founder Agent', icon: '👔', description: 'Founder alignment & skin in game', color: 'blue' },
              { id: 'growth', name: 'Growth Agent', icon: '📈', description: 'Organic growth quality', color: 'purple' },
              { id: 'redflag', name: 'Red Flag Agent', icon: '🚩', description: 'Learned patterns & buyback ratios', color: 'red' },
            ]}
            output="40-50 selected"
            active={activePhase === 'selection'}
            metrics={agentMetrics.selection}
          />
        </motion.div>

        {/* Arrow */}
        <div className="flex justify-center mb-12">
          <motion.div
            animate={{ scale: activePhase !== 'selection' && activePhase !== 'discovery' ? 1 : 0.8, opacity: activePhase !== 'selection' && activePhase !== 'discovery' ? 1 : 0.5 }}
            className="h-12 relative"
          >
            <svg className="w-8 h-12" viewBox="0 0 32 48" fill="none">
              <motion.path
                d="M16 0 L16 40 M16 40 L10 34 M16 40 L22 34"
                stroke="currentColor"
                strokeWidth="2"
                className="text-stone-400"
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: activePhase !== 'selection' && activePhase !== 'discovery' ? 1 : 0 }}
                transition={{ duration: 0.8 }}
              />
            </svg>
          </motion.div>
        </div>

        {/* SCORING TEAM PHASE */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: activePhase === 'scoring' || activePhase === 'complete' ? 1 : 0.3 }}
          className="mb-12"
        >
          <AgentPhase
            title="Phase 3: Scoring Team (Analyze)"
            agents={[
              { id: 'analyst', name: 'AI Analyst', icon: '🧠', description: 'Business quality, unit economics, capital returns, growth, balance sheet, fit', color: 'gold' },
              { id: 'risk', name: 'Risk Scorer', icon: '⚠️', description: 'Leverage, competitive position, margin stability', color: 'red' },
              { id: 'memo', name: 'Memo Gen', icon: '📝', description: 'Investment thesis & memo', color: 'blue' },
            ]}
            output="Scored & ranked"
            active={activePhase === 'scoring'}
            metrics={agentMetrics.scoring}
          />
        </motion.div>

        {/* Arrow to results */}
        <div className="flex justify-center mb-12">
          <motion.div
            animate={{ scale: activePhase === 'complete' ? 1 : 0.8, opacity: activePhase === 'complete' ? 1 : 0.5 }}
            className="h-12 relative"
          >
            <svg className="w-8 h-12" viewBox="0 0 32 48" fill="none">
              <motion.path
                d="M16 0 L16 40 M16 40 L10 34 M16 40 L22 34"
                stroke="currentColor"
                strokeWidth="2"
                className="text-stone-400"
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: activePhase === 'complete' ? 1 : 0 }}
                transition={{ duration: 0.8 }}
              />
            </svg>
          </motion.div>
        </div>

        {/* Results */}
        <motion.div
          animate={{ opacity: activePhase === 'complete' ? 1 : 0.3 }}
          className="text-center p-6 bg-gradient-to-r from-emerald-50 to-blue-50 border border-emerald-200 rounded-lg"
        >
          <div className="section-label mb-2">Results</div>
          <div className="text-2xl font-semibold text-emerald-600">✨ Screening Complete</div>
          <p className="text-sm text-stone-600 mt-2">All companies ranked and ready for review</p>
        </motion.div>
      </div>

      {/* Data flow legend */}
      <div className="grid grid-cols-3 gap-4">
        <DataFlowBox
          title="Selection Input"
          items={['1000 candidates', 'Metrics', 'Company info']}
          color="blue"
        />
        <DataFlowBox
          title="Agent Chain"
          items={['5 parallel agents', 'Rule-based + LLM', 'Confidence scoring']}
          color="purple"
        />
        <DataFlowBox
          title="Scoring Input"
          items={['40-50 pre-filtered', 'Real data only', 'Lower LLM cost']}
          color="emerald"
        />
      </div>
    </div>
  )
}

function AgentPhase({ title, agents, output, active, metrics }) {
  return (
    <div>
      <h4 className="font-semibold text-stone-800 mb-4">{title}</h4>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        {agents.map(agent => (
          <AgentCard
            key={agent.id}
            {...agent}
            active={active}
          />
        ))}
      </div>
      <div className="flex items-center justify-end text-sm">
        <span className="text-stone-500">Output: </span>
        <motion.span
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          className="ml-2 font-semibold text-emerald-600"
        >
          {metrics?.count ? `${metrics.count} ${output}` : output}
        </motion.span>
      </div>
    </div>
  )
}

function AgentCard({ id, name, icon, description, color, active }) {
  const colorMap = {
    blue: 'bg-blue-50 border-blue-200 text-blue-700',
    emerald: 'bg-emerald-50 border-emerald-200 text-emerald-700',
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    purple: 'bg-purple-50 border-purple-200 text-purple-700',
    red: 'bg-red-50 border-red-200 text-red-700',
    gold: 'bg-yellow-50 border-yellow-200 text-yellow-700',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: active ? 1 : 0.6, y: 0 }}
      className={clsx(
        'p-3 border rounded-lg text-center cursor-pointer transition',
        colorMap[color],
        active && 'ring-2 ring-offset-2 ring-stone-400 shadow-md'
      )}
    >
      <div className="text-2xl mb-1">{icon}</div>
      <div className="text-xs font-semibold">{name}</div>
      <div className="text-[10px] opacity-70 leading-tight mt-1">{description}</div>
    </motion.div>
  )
}

function DataFlowBox({ title, items, color }) {
  const colorMap = {
    blue: 'border-blue-200 bg-blue-50',
    emerald: 'border-emerald-200 bg-emerald-50',
    purple: 'border-purple-200 bg-purple-50',
  }

  return (
    <div className={clsx('p-4 border rounded-lg', colorMap[color])}>
      <div className="font-semibold text-sm mb-2 text-stone-800">{title}</div>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="text-xs text-stone-600 flex items-center gap-2">
            <span className="w-1 h-1 bg-stone-400 rounded-full"></span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}
