import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export function Markdown({ content }: { content: string }) {
  return (
    <div className="prose prose-sm prose-invert max-w-none prose-p:my-2 prose-pre:bg-slate-900 prose-pre:text-xs prose-table:text-xs">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}
