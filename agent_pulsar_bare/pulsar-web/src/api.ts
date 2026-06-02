import type { ChatMessage, StreamEvent, ThreadMeta } from './types'

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}

export function listThreads(): Promise<ThreadMeta[]> {
  return fetch('/api/threads').then((r) => json<ThreadMeta[]>(r))
}

export function createThread(): Promise<ThreadMeta> {
  return fetch('/api/threads', { method: 'POST' }).then((r) => json<ThreadMeta>(r))
}

export function getThread(id: string): Promise<ThreadMeta & { messages: ChatMessage[] }> {
  return fetch(`/api/threads/${id}`).then((r) => json<ThreadMeta & { messages: ChatMessage[] }>(r))
}

export async function acceptChart(threadId: string, callId: string): Promise<void> {
  const response = await fetch(`/api/threads/${threadId}/charts/${callId}/accept`, { method: 'POST' })
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
}

export async function deleteThread(id: string): Promise<void> {
  const response = await fetch(`/api/threads/${id}`, { method: 'DELETE' })
  if (!response.ok && response.status !== 404) {
    throw new Error(`${response.status} ${response.statusText}`)
  }
}

/** POST the question and yield the SSE events of the agent's run as they arrive. */
export async function* streamQuestion(
  threadId: string,
  question: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const response = await fetch(`/api/threads/${threadId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    signal,
  })
  if (!response.ok || response.body === null) {
    throw new Error(`${response.status} ${response.statusText}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      for (const line of frame.split('\n')) {
        if (line.startsWith('data: ')) {
          yield JSON.parse(line.slice(6)) as StreamEvent
        }
      }
    }
  }
}
