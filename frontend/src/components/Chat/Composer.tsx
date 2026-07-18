import { useState } from 'react'
import { SendIcon, SpinnerIcon } from '../icons'

const SUGGESTIONS = [
  'Nowcast US GDP growth for the current quarter',
  'What is the probability of a sovereign default in Argentina within 2 years?',
  'Where are US 10-year treasury yields heading over the next 6 months?',
  'How would a prolonged Red Sea shipping disruption spill over into euro area trade?',
]

export default function Composer({
  onSend,
  busy,
  showSuggestions,
}: {
  onSend: (content: string) => void
  busy: boolean
  showSuggestions: boolean
}) {
  const [draft, setDraft] = useState('')

  const submit = () => {
    const content = draft.trim()
    if (!content || busy) return
    setDraft('')
    onSend(content)
  }

  return (
    <div className="space-y-2">
      {showSuggestions && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => onSend(suggestion)}
              disabled={busy}
              className="rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:border-slate-400 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-end gap-2 rounded-xl border border-slate-200 bg-white p-2 focus-within:border-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:focus-within:border-slate-500">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
          rows={Math.min(5, Math.max(1, draft.split('\n').length))}
          placeholder="Ask a forecasting question…"
          className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-slate-400"
        />
        <button
          onClick={submit}
          disabled={busy || !draft.trim()}
          title="Send"
          className="rounded-lg bg-slate-900 p-2 text-white transition-opacity disabled:opacity-40 dark:bg-slate-100 dark:text-slate-900"
        >
          {busy ? <SpinnerIcon /> : <SendIcon />}
        </button>
      </div>
    </div>
  )
}
