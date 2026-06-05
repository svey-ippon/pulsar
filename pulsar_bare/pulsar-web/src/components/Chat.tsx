import { useEffect, useRef, useState } from 'react'
import type { ChatMessage, Segment } from '../types'
import { Markdown } from './Markdown'
import { TableCard } from './TableCard'
import { ToolChip } from './ToolChip'

interface ChatProps {
  messages: ChatMessage[]
  streaming: boolean
  onSend: (question: string) => void
}

export function Chat({ messages, streaming, onSend }: ChatProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  return (
    <main className="flex min-w-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-8">
          {messages.length === 0 ? (
            <Welcome />
          ) : (
            messages.map((message, index) => (
              <MessageView key={index} message={message} streaming={streaming && index === messages.length - 1} />
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      <Composer disabled={streaming} onSend={onSend} />
    </main>
  )
}

function Welcome() {
  return (
    <div className="mt-24 text-center">
      <p className="text-lg font-medium text-slate-300">Ask a question about your data.</p>
      <p className="mt-2 text-sm text-slate-500">
        The agent grounds every query in the semantic contract, writes the SQL, and shows its work.
      </p>
    </div>
  )
}

function MessageView({ message, streaming }: { message: ChatMessage; streaming: boolean }) {
  if (message.role === 'user') {
    return (
      <div className="mb-6 flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-violet-600/90 px-4 py-2.5 text-sm text-white">
          {message.content}
        </div>
      </div>
    )
  }
  return (
    <div className="mb-8">
      <div className="space-y-3">
        {message.segments.map((segment, index) => (
          <SegmentView key={index} segment={segment} />
        ))}
        {streaming && <Pulse working={message.segments.length === 0} />}
      </div>
    </div>
  )
}

function SegmentView({ segment }: { segment: Segment }) {
  switch (segment.type) {
    case 'text':
      return <Markdown content={segment.content} />
    case 'tool':
      return <ToolChip segment={segment} />
    case 'table':
      return <TableCard table={segment} />
    case 'error':
      return (
        <div className="rounded-lg border border-red-900/60 bg-red-950/40 px-3 py-2 text-sm text-red-300">
          {segment.message}
        </div>
      )
  }
}

function Pulse({ working }: { working: boolean }) {
  return (
    <div className="flex items-center gap-2 text-xs text-slate-500">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-500" />
      {working ? 'thinking…' : ''}
    </div>
  )
}

function Composer({ disabled, onSend }: { disabled: boolean; onSend: (question: string) => void }) {
  const [value, setValue] = useState('')

  const submit = () => {
    const question = value.trim()
    if (question === '' || disabled) return
    onSend(question)
    setValue('')
  }

  return (
    <div className="border-t border-slate-800 bg-slate-950/95 px-4 py-4">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              submit()
            }
          }}
          rows={Math.min(4, value.split('\n').length)}
          placeholder="Ask about revenue, work orders, satisfaction…"
          className="flex-1 resize-none rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-200 placeholder:text-slate-600 focus:border-violet-600 focus:outline-none"
        />
        <button
          onClick={submit}
          disabled={disabled || value.trim() === ''}
          className="rounded-xl bg-violet-600 px-4 py-3 text-sm font-medium text-white transition enabled:hover:bg-violet-500 disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </div>
  )
}
