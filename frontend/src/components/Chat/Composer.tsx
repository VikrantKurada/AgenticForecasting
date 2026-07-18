import { useState } from 'react'
import type { RunPreferences } from '../../types'
import { SendIcon, SpinnerIcon } from '../icons'

const SUGGESTIONS = [
  'Nowcast US GDP growth for the current quarter',
  'What is the probability of a sovereign default in Argentina within 2 years?',
  'Where are US 10-year treasury yields heading over the next 6 months?',
  'How would a prolonged Red Sea shipping disruption spill over into euro area trade?',
]

const HORIZONS = [
  { value: '', label: 'Horizon: auto' },
  { value: '2', label: '2 periods' },
  { value: '4', label: '4 periods' },
  { value: '8', label: '8 periods' },
  { value: '12', label: '12 periods' },
  { value: '20', label: '20 periods' },
]

const selectClass =
  'rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-500 outline-none hover:border-slate-300 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400'

export default function Composer({
  onSend,
  busy,
  showSuggestions,
  sources,
}: {
  onSend: (content: string, preferences?: RunPreferences) => void
  busy: boolean
  showSuggestions: boolean
  sources: { name: string; label: string }[]
}) {
  const [draft, setDraft] = useState('')
  const [source, setSource] = useState('')
  const [horizon, setHorizon] = useState('')

  const preferences = (): RunPreferences | undefined => {
    const prefs: RunPreferences = {}
    if (source) prefs.source = source
    if (horizon) prefs.horizon = Number(horizon)
    return Object.keys(prefs).length ? prefs : undefined
  }

  const submit = () => {
    const content = draft.trim()
    if (!content || busy) return
    setDraft('')
    onSend(content, preferences())
  }

  return (
    <div className="space-y-2">
      {showSuggestions && (
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => onSend(suggestion, preferences())}
              disabled={busy}
              className="rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:border-slate-400 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
          Run options
        </span>
        <select value={source} onChange={(e) => setSource(e.target.value)} className={selectClass}>
          <option value="">Data source: auto</option>
          {sources.map((s) => (
            <option key={s.name} value={s.name}>
              {s.label}
            </option>
          ))}
        </select>
        <select value={horizon} onChange={(e) => setHorizon(e.target.value)} className={selectClass}>
          {HORIZONS.map((h) => (
            <option key={h.value} value={h.value}>
              {h.label}
            </option>
          ))}
        </select>
      </div>
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
