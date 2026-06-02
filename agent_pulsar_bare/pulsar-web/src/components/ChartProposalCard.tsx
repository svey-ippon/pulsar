import type { ChartData } from '../types'

export function ChartProposalCard({ chart, onAccept }: { chart: ChartData; onAccept: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-dashed border-violet-700/60 bg-violet-950/20 px-4 py-3">
      <span className="text-base">📊</span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-slate-200">
          Chart available: <span className="font-medium">{chart.title}</span>
        </p>
        <p className="text-xs text-slate-500">
          {chart.chart_type} · {chart.row_count} row{chart.row_count === 1 ? '' : 's'}
        </p>
      </div>
      <button
        onClick={onAccept}
        className="shrink-0 rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-violet-500"
      >
        Show chart
      </button>
    </div>
  )
}
