import type { EChartsOption } from 'echarts'
import type { ChartData, Row } from './types'

// slate/violet palette matching the UI theme
const PALETTE = ['#8b5cf6', '#38bdf8', '#34d399', '#fbbf24', '#fb7185', '#a3e635', '#22d3ee', '#f472b6']
const AXIS_LABEL = '#94a3b8' // slate-400
const AXIS_LINE = '#334155' // slate-700
const SPLIT_LINE = '#1e293b' // slate-800
const TOOLTIP_BG = '#0f172a' // slate-900

function toNumber(value: unknown): number | null {
  if (typeof value === 'number') return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    if (value.trim() !== '' && Number.isFinite(parsed)) return parsed
  }
  return null
}

/** Copy of the rows with the y/y2 columns coerced to numbers (Snowflake decimals arrive as strings). */
function numericRows(chart: ChartData): Row[] {
  return chart.rows.map((row) => {
    const copy: Row = { ...row }
    for (const column of [...chart.y, ...(chart.y2 ?? [])]) copy[column] = toNumber(row[column])
    return copy
  })
}

function baseOption(chart: ChartData): EChartsOption {
  return {
    color: PALETTE,
    backgroundColor: 'transparent',
    textStyle: { color: '#cbd5e1' },
    tooltip: {
      trigger: chart.chart_type === 'pie' || chart.chart_type === 'scatter' ? 'item' : 'axis',
      backgroundColor: TOOLTIP_BG,
      borderColor: AXIS_LINE,
      textStyle: { color: '#e2e8f0' },
    },
    toolbox: {
      right: 8,
      iconStyle: { borderColor: '#64748b' },
      feature: { saveAsImage: { name: chart.title || 'chart', backgroundColor: TOOLTIP_BG } },
    },
  }
}

const legend = { bottom: 0, textStyle: { color: AXIS_LABEL } }

/**
 * Compile the agent's validated chart spec into an ECharts option.
 *
 * Pure function: spec + rows in, option out. The spec was already validated server-side
 * against the result columns, so this never has to defend against missing columns.
 */
export function chartOption(chart: ChartData): EChartsOption {
  const rows = numericRows(chart)

  if (chart.chart_type === 'pie') {
    return {
      ...baseOption(chart),
      legend,
      series: [
        {
          type: 'pie',
          radius: ['38%', '68%'],
          data: rows.map((row) => ({ name: String(row[chart.x]), value: toNumber(row[chart.y[0]]) ?? 0 })),
          label: { color: '#cbd5e1' },
          itemStyle: { borderColor: TOOLTIP_BG, borderWidth: 2 },
        },
      ],
    }
  }

  const y2 = chart.y2 ?? []
  const xIsNumeric = chart.chart_type === 'scatter' && rows.every((row) => toNumber(row[chart.x]) !== null)

  const primaryAxis = {
    type: 'value' as const,
    axisLabel: { color: y2.length > 0 ? PALETTE[0] : AXIS_LABEL },
    splitLine: { lineStyle: { color: SPLIT_LINE } },
  }
  // secondary axis: scale (not zero-forced — a 4.2→4.6 score stays readable), no grid
  // lines of its own, label colored like its first series
  const secondaryAxis = {
    type: 'value' as const,
    scale: true,
    axisLabel: { color: PALETTE[chart.y.length % PALETTE.length] },
    splitLine: { show: false },
  }

  const axes: EChartsOption = {
    grid: { left: 48, right: y2.length > 0 ? 48 : 24, top: 32, bottom: 56 },
    xAxis: {
      type: xIsNumeric ? 'value' : 'category',
      axisLabel: { color: AXIS_LABEL },
      axisLine: { lineStyle: { color: AXIS_LINE } },
    },
    yAxis: y2.length > 0 ? [primaryAxis, secondaryAxis] : primaryAxis,
  }
  const resolveType = (type: ChartData['chart_type'] | NonNullable<ChartData['y2_type']>) =>
    type === 'area' ? ('line' as const) : (type as 'bar' | 'line' | 'scatter')
  const areaStyleFor = (type: string) => (type === 'area' ? { areaStyle: { opacity: 0.25 } } : {})
  const seriesType = resolveType(chart.chart_type)
  const areaStyle = areaStyleFor(chart.chart_type)

  if (chart.series) {
    // one ECharts series per distinct value of the split column, via dataset filter transforms
    const values = [...new Set(rows.map((row) => String(row[chart.series as string])))]
    return {
      ...baseOption(chart),
      ...axes,
      legend,
      dataset: [
        { source: rows },
        ...values.map((value) => ({
          transform: { type: 'filter' as const, config: { dimension: chart.series as string, value } },
        })),
      ],
      series: values.map((value, index) => ({
        type: seriesType,
        name: value,
        datasetIndex: index + 1,
        encode: { x: chart.x, y: chart.y[0] },
        ...areaStyle,
      })),
    } as EChartsOption
  }

  const y2Type = chart.y2_type ?? chart.chart_type
  return {
    ...baseOption(chart),
    ...axes,
    ...(chart.y.length + y2.length > 1 ? { legend } : {}),
    dataset: { source: rows },
    series: [
      ...chart.y.map((column) => ({
        type: seriesType,
        name: column,
        encode: { x: chart.x, y: column },
        ...(y2.length > 0 ? { yAxisIndex: 0 } : {}),
        ...areaStyle,
      })),
      ...y2.map((column) => ({
        type: resolveType(y2Type),
        name: column,
        encode: { x: chart.x, y: column },
        yAxisIndex: 1,
        ...areaStyleFor(y2Type),
      })),
    ],
  } as EChartsOption
}
