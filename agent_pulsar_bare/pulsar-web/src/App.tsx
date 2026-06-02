import { useCallback, useEffect, useRef, useState } from 'react'
import { acceptChart, createThread, deleteThread, getThread, listThreads, streamQuestion } from './api'
import { Chat } from './components/Chat'
import { Sidebar } from './components/Sidebar'
import type { ChatMessage, Segment, StreamEvent, ThreadMeta } from './types'

/** Fold one SSE event into the segment list of the assistant turn being streamed. */
function applyEvent(segments: Segment[], event: StreamEvent): Segment[] {
  switch (event.type) {
    case 'text_token': {
      const last = segments[segments.length - 1]
      if (last?.type === 'text') {
        return [...segments.slice(0, -1), { ...last, content: last.content + event.content }]
      }
      return [...segments, { type: 'text', content: event.content }]
    }
    case 'tool_call':
      return [...segments, { type: 'tool', id: event.id, tool: event.tool, args: event.args }]
    case 'tool_result':
      return segments.map((segment) =>
        segment.type === 'tool' && segment.id === event.id
          ? { ...segment, summary: event.summary }
          : segment,
      )
    case 'display_table': {
      const { type: _type, id: _id, ...table } = event
      return [...segments, { type: 'table', ...table }]
    }
    case 'chart': {
      const { type: _type, ...chart } = event
      // mode 'render' = the user explicitly asked: no consent step
      return [...segments, { type: 'chart', ...chart, accepted: chart.mode === 'render' }]
    }
    case 'error':
      return [...segments, { type: 'error', message: event.message }]
    default:
      return segments
  }
}

export default function App() {
  const [threads, setThreads] = useState<ThreadMeta[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const refreshThreads = useCallback(() => listThreads().then(setThreads).catch(console.error), [])

  useEffect(() => {
    void refreshThreads()
  }, [refreshThreads])

  const openThread = useCallback(async (id: string) => {
    abortRef.current?.abort()
    setActiveId(id)
    const thread = await getThread(id)
    setMessages(thread.messages)
  }, [])

  const newThread = useCallback(() => {
    abortRef.current?.abort()
    setActiveId(null)
    setMessages([])
  }, [])

  const removeThread = useCallback(
    async (id: string) => {
      await deleteThread(id)
      if (id === activeId) newThread()
      void refreshThreads()
    },
    [activeId, newThread, refreshThreads],
  )

  const showChart = useCallback(
    async (callId: string) => {
      if (activeId === null) return
      await acceptChart(activeId, callId)
      setMessages((previous) =>
        previous.map((message) =>
          message.role === 'assistant'
            ? {
                ...message,
                segments: message.segments.map((segment) =>
                  segment.type === 'chart' && segment.id === callId
                    ? { ...segment, accepted: true }
                    : segment,
                ),
              }
            : message,
        ),
      )
    },
    [activeId],
  )

  const send = useCallback(
    async (question: string) => {
      if (streaming) return
      let threadId = activeId
      if (threadId === null) {
        const created = await createThread()
        threadId = created.id
        setActiveId(threadId)
      }

      setMessages((previous) => [
        ...previous,
        { role: 'user', content: question },
        { role: 'assistant', segments: [] },
      ])
      setStreaming(true)
      const controller = new AbortController()
      abortRef.current = controller

      const updateLast = (event: StreamEvent) =>
        setMessages((previous) => {
          const last = previous[previous.length - 1]
          if (last?.role !== 'assistant') return previous
          return [...previous.slice(0, -1), { ...last, segments: applyEvent(last.segments, event) }]
        })

      try {
        for await (const event of streamQuestion(threadId, question, controller.signal)) {
          updateLast(event)
        }
      } catch (error) {
        if ((error as Error).name !== 'AbortError') {
          updateLast({ type: 'error', message: (error as Error).message })
        }
      } finally {
        setStreaming(false)
        abortRef.current = null
        void refreshThreads()
      }
    },
    [activeId, refreshThreads, streaming],
  )

  return (
    <div className="flex h-full">
      <Sidebar
        threads={threads}
        activeId={activeId}
        onSelect={(id) => void openThread(id)}
        onNew={newThread}
        onDelete={(id) => void removeThread(id)}
      />
      <Chat
        messages={messages}
        streaming={streaming}
        onSend={(q) => void send(q)}
        onShowChart={(callId) => void showChart(callId)}
      />
    </div>
  )
}
