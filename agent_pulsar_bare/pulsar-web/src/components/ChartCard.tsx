import { Suspense, lazy, useMemo, useState } from 'react'
import { chartOption } from '../chartOption'
import type { ChartData } from '../types'
import { SqlBlock } from './SqlBlock'

// echarts only loads when a chart actually renders — keeps the main bundle light
const EChart = lazy(() => import('./EChart').then((module) => ({ default: module.EChart })))

export function ChartCard({ chart }: { chart: ChartData }) {
  const [showSql, setShowSql] = useState(false)
  const option = useMemo(() => chartOption(chart), [chart])

  return (
    <div className="overflow-hidden rounded-xl border border-slate-700/80 bg-slate-900/60">
      <div className="flex items-center gap-3 border-b border-slate-800 px-4 py-2.5">
        <h3 className="min-w-0 flex-1 truncate text-sm font-medium text-slate-200">{chart.title}</h3>
        <span className="shrink-0 rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
          {chart.chart_type}
        </span>
        <button
          onClick={() => setShowSql((value) => !value)}
          className="shrink-0 text-xs text-slate-500 hover:text-slate-300"
        >
          SQL
        </button>
      </div>

      {showSql && (
        <div className="border-b border-slate-800 p-2">
          <SqlBlock sql={chart.sql} />
        </div>
      )}

      <div className="p-2">
        <Suspense fallback={<div className="h-80 animate-pulse rounded-lg bg-slate-800/40" />}>
          <EChart option={option} />
        </Suspense>
      </div>
    </div>
  )
}
