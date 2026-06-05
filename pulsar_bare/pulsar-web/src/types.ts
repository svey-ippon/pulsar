export interface ThreadMeta {
  id: string
  title: string | null
  created_at: string
}

export interface Column {
  name: string
  type?: string
}

export type Row = Record<string, unknown>

export interface ToolSummary {
  status: 'ok' | 'error'
  result_id?: string
  row_count?: number
  execution_time_ms?: number
  domain_id?: string
  title?: string
  error_type?: string
  message?: string
}

export interface TableData {
  result_id: string
  title: string
  sql: string
  columns: Column[]
  rows: Row[]
  row_count: number
}

export type Segment =
  | { type: 'text'; content: string }
  | { type: 'tool'; id: string; tool: string; args: Record<string, unknown>; summary?: ToolSummary }
  | ({ type: 'table' } & TableData)
  | { type: 'error'; message: string }

export type ChatMessage =
  | { role: 'user'; content: string }
  | { role: 'assistant'; segments: Segment[] }

export type StreamEvent =
  | { type: 'text_token'; content: string }
  | { type: 'tool_call'; id: string; tool: string; args: Record<string, unknown> }
  | { type: 'tool_result'; id: string; summary: ToolSummary }
  | ({ type: 'display_table'; id: string } & TableData)
  | { type: 'answer'; text: string }
  | { type: 'error'; message: string }
  | { type: 'done' }
