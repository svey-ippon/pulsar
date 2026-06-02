import { useState } from 'react'
import type { Segment } from '../types'
import { SqlBlock } from './SqlBlock'

type ToolSegment = Extract<Segment, { type: 'tool' }>

const TOOL_ICONS: Record<string, string> = {
  describe_domain: '📖',
  execute_sql: '🗄',
  display_table: '▦',
  display_chart: '📊',
}

function label(segment: ToolSegment): string {
  const { tool, args, summary } = segment
  if (tool === 'describe_domain') {
    return `Semantic contract — ${String(args.domain_id ?? summary?.domain_id ?? '?')}`
  }
  if (tool === 'execute_sql') {
    if (summary === undefined) return 'Running SQL…'
    if (summary.status === 'error') return 'SQL failed'
    const ms = summary.execution_time_ms
    return `SQL — ${summary.row_count} row${summary.row_count === 1 ? '' : 's'}${ms !== undefined ? ` · ${ms} ms` : ''}`
  }
  if (tool === 'display_table') {
    return `Rendering table — ${String(args.title ?? '')}`
  }
  if (tool === 'display_chart') {
    const verb = args.mode === 'render' ? 'Rendering' : 'Proposing'
    return `${verb} ${String(args.chart_type ?? '')} chart — ${String(args.title ?? '')}`
  }
  return tool
}

function StatusDot({ segment }: { segment: ToolSegment }) {
  if (segment.summary === undefined) {
    return <span className="h-3 w-3 animate-spin rounded-full border border-slate-500 border-t-violet-400" />
  }
  if (segment.summary.status === 'error') {
    return <span className="text-red-400">✕</span>
  }
  return <span className="text-emerald-400">✓</span>
}

export function ToolChip({ segment }: { segment: ToolSegment }) {
  const [open, setOpen] = useState(false)
  const expandable = segment.tool === 'execute_sql' || segment.summary?.status === 'error'

  return (
    <div className="text-sm">
      <button
        onClick={() => expandable && setOpen((value) => !value)}
        className={`inline-flex items-center gap-2 rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-300 ${
          expandable ? 'cursor-pointer hover:border-slate-500' : 'cursor-default'
        }`}
      >
        <StatusDot segment={segment} />
        <span className="opacity-70">{TOOL_ICONS[segment.tool] ?? '⚙'}</span>
        <span>{label(segment)}</span>
        {expandable && <span className="text-slate-500">{open ? '▾' : '▸'}</span>}
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {segment.tool === 'execute_sql' && typeof segment.args.sql === 'string' && (
            <SqlBlock sql={segment.args.sql} />
          )}
          {segment.summary?.status === 'error' && (
            <div className="rounded-lg border border-red-900/60 bg-red-950/40 px-3 py-2 text-xs text-red-300">
              {segment.summary.error_type}: {segment.summary.message}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
