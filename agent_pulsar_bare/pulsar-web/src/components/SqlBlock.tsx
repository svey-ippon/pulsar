import { useMemo } from 'react'
import hljs from 'highlight.js/lib/core'
import sql from 'highlight.js/lib/languages/sql'
import 'highlight.js/styles/github-dark-dimmed.css'

hljs.registerLanguage('sql', sql)

export function SqlBlock({ sql: statement }: { sql: string }) {
  const html = useMemo(() => hljs.highlight(statement, { language: 'sql' }).value, [statement])
  return (
    <pre className="overflow-x-auto rounded-lg bg-slate-950 p-3 font-mono text-xs leading-relaxed text-slate-300">
      <code dangerouslySetInnerHTML={{ __html: html }} />
    </pre>
  )
}
