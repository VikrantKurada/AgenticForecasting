import { XIcon } from '../icons'

// Placeholder — the Fragments-style tabbed panel lands in the next build step.
export default function OutputPanel({
  runId,
  onClose,
}: {
  runId: string
  onClose: () => void
}) {
  return (
    <aside className="flex w-[420px] shrink-0 flex-col border-l border-slate-200 dark:border-slate-800">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2.5 dark:border-slate-800">
        <span className="text-sm font-medium">Output</span>
        <button onClick={onClose} className="rounded p-1 text-slate-400 hover:text-slate-600">
          <XIcon />
        </button>
      </div>
      <div className="flex flex-1 items-center justify-center text-xs text-slate-400">
        Artifacts for run {runId.slice(0, 8)}…
      </div>
    </aside>
  )
}
