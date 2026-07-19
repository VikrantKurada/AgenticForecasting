import Markdown from 'react-markdown'

/**
 * Shared markdown renderer for chat messages, reports and methodology.
 *
 * Inline-code styling must be scoped to `:not(pre) > code`. Applying it to every
 * `code` element also hits the `code` inside a fenced block, layering a light
 * chip background over the dark `pre` and making code blocks unreadable.
 */
const PROSE = [
  'prose prose-sm prose-slate max-w-none dark:prose-invert',
  // headings sized for a narrow panel
  '[&_h1]:text-base [&_h2]:text-sm [&_h3]:text-[13px]',
  // inline code only — never inside a fenced block
  '[&_:not(pre)>code]:rounded [&_:not(pre)>code]:bg-slate-100',
  '[&_:not(pre)>code]:px-1 [&_:not(pre)>code]:py-0.5',
  '[&_:not(pre)>code]:text-[12px] [&_:not(pre)>code]:font-normal',
  '[&_:not(pre)>code]:text-slate-800 dark:[&_:not(pre)>code]:bg-slate-800',
  'dark:[&_:not(pre)>code]:text-slate-100',
  // react-markdown emits no ``, so strip the prose plugin's quote marks
  "[&_:not(pre)>code]:before:content-[''] [&_:not(pre)>code]:after:content-['']",
  // fenced blocks: dark, monospace, horizontally scrollable, never wrapped
  '[&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-slate-900',
  '[&_pre]:p-3 [&_pre]:text-[12px] [&_pre]:leading-relaxed',
  '[&_pre_code]:whitespace-pre [&_pre_code]:text-slate-100',
  '[&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:font-mono',
  // wide tables scroll instead of forcing the page sideways
  '[&_table]:text-xs [&_table]:block [&_table]:overflow-x-auto',
].join(' ')

export default function MarkdownBody({
  children,
  className = '',
}: {
  children: string
  className?: string
}) {
  return (
    <div className={`${PROSE} ${className}`}>
      <Markdown>{children}</Markdown>
    </div>
  )
}
