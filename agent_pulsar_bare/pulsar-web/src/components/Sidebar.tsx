import type { ThreadMeta } from '../types'

interface SidebarProps {
  threads: ThreadMeta[]
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
}

export function Sidebar({ threads, activeId, onSelect, onNew, onDelete }: SidebarProps) {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-900/60">
      <div className="flex items-center gap-2 px-4 py-4">
        <span className="h-2.5 w-2.5 rounded-full bg-violet-500 shadow-[0_0_8px] shadow-violet-500/80" />
        <h1 className="text-sm font-semibold tracking-wide text-slate-100">Pulsar</h1>
        <span className="text-xs text-slate-500">data analyst</span>
      </div>

      <button
        onClick={onNew}
        className="mx-3 mb-3 rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-2 text-left text-sm text-slate-200 transition hover:border-violet-600 hover:bg-slate-800"
      >
        + New conversation
      </button>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-4">
        {threads.map((thread) => (
          <div
            key={thread.id}
            className={`group flex items-center rounded-lg px-2 py-1.5 text-sm transition ${
              thread.id === activeId
                ? 'bg-violet-600/20 text-violet-200'
                : 'text-slate-400 hover:bg-slate-800/80 hover:text-slate-200'
            }`}
          >
            <button
              onClick={() => onSelect(thread.id)}
              className="min-w-0 flex-1 truncate text-left"
              title={thread.title ?? 'New conversation'}
            >
              {thread.title ?? 'New conversation'}
            </button>
            <button
              onClick={() => onDelete(thread.id)}
              className="ml-1 hidden rounded px-1 text-slate-500 hover:text-red-400 group-hover:block"
              title="Delete conversation"
            >
              ×
            </button>
          </div>
        ))}
        {threads.length === 0 && (
          <p className="px-2 py-1 text-xs text-slate-600">No conversations yet.</p>
        )}
      </nav>
    </aside>
  )
}
