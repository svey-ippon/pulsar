import { useState } from 'react'
import type { TableData } from '../types'
import { SqlBlock } from './SqlBlock'

const NUMERIC_RE = /^-?\d+(\.\d+)?$/

function isNumeric(value: unknown): boolean {
  return typeof value === 'number' || (typeof value === 'string' && NUMERIC_RE.test(value))
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '∅'
  if (typeof value === 'number') return value.toLocaleString('en-US')
  if (typeof value === 'string' && NUMERIC_RE.test(value) && value.includes('.')) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed.toLocaleString('en-US', { maximumFractionDigits: 6 })
  }
  return String(value)
}

function toCsv(table: TableData): string {
  const quote = (value: unknown) => {
    const text = value === null || value === undefined ? '' : String(value)
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
  }
  const header = table.columns.map((column) => quote(column.name)).join(',')
  const lines = table.rows.map((row) => table.columns.map((column) => quote(row[column.name])).join(','))
  return [header, ...lines].join('\n')
}

export function TableCard({ table }: { table: TableData }) {
  const [showSql, setShowSql] = useState(false)

  const download = () => {
    const blob = new Blob([toCsv(table)], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${table.title.replace(/[^\w\d-]+/g, '_').toLowerCase() || 'table'}.csv`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-700/80 bg-slate-900/60">
      <div className="flex items-center gap-3 border-b border-slate-800 px-4 py-2.5">
        <h3 className="min-w-0 flex-1 truncate text-sm font-medium text-slate-200">{table.title}</h3>
        <span className="shrink-0 rounded-full bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
          {table.row_count} row{table.row_count === 1 ? '' : 's'}
        </span>
        <button
          onClick={() => setShowSql((value) => !value)}
          className="shrink-0 text-xs text-slate-500 hover:text-slate-300"
        >
          SQL
        </button>
        <button onClick={download} className="shrink-0 text-xs text-slate-500 hover:text-slate-300">
          CSV
        </button>
      </div>

      {showSql && (
        <div className="border-b border-slate-800 p-2">
          <SqlBlock sql={table.sql} />
        </div>
      )}

      <div className="max-h-80 overflow-auto">
        <table className="w-full border-collapse text-xs">
          <thead className="sticky top-0 bg-slate-900">
            <tr>
              {table.columns.map((column) => (
                <th
                  key={column.name}
                  className={`whitespace-nowrap border-b border-slate-700 px-3 py-2 font-semibold text-slate-300 ${
                    isNumeric(table.rows[0]?.[column.name]) ? 'text-right' : 'text-left'
                  }`}
                >
                  {column.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, index) => (
              <tr key={index} className={index % 2 === 1 ? 'bg-slate-800/30' : ''}>
                {table.columns.map((column) => (
                  <td
                    key={column.name}
                    className={`whitespace-nowrap px-3 py-1.5 text-slate-300 ${
                      isNumeric(row[column.name]) ? 'text-right font-mono tabular-nums' : 'text-left'
                    }`}
                  >
                    {formatCell(row[column.name])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
