import { useEffect, useRef, useState } from 'react'
import type { RunPreferences, UploadedFileMeta } from '../../types'
import { PaperclipIcon, SendIcon, SpinnerIcon, XIcon } from '../icons'

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

const controlClass =
  'rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-500 outline-none hover:border-slate-300 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-400'

interface StoredPrefs {
  sources: string[]
  horizon: string
}

function loadPrefs(chatId: string): StoredPrefs {
  try {
    const raw = localStorage.getItem(`runPrefs:${chatId}`)
    if (raw) return { sources: [], horizon: '', ...JSON.parse(raw) }
  } catch {
    /* corrupted entry — fall through to defaults */
  }
  return { sources: [], horizon: '' }
}

export default function Composer({
  chatId,
  onSend,
  busy,
  showSuggestions,
  sources,
  files,
  uploading,
  onAttach,
  onRemoveFile,
}: {
  chatId: string
  onSend: (content: string, preferences?: RunPreferences) => void
  busy: boolean
  showSuggestions: boolean
  sources: { name: string; label: string }[]
  files: UploadedFileMeta[]
  uploading: boolean
  onAttach: (file: File) => void
  onRemoveFile: (fileId: string) => void
}) {
  const [draft, setDraft] = useState('')
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [horizon, setHorizon] = useState('')
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const prefs = loadPrefs(chatId)
    setSelectedSources(prefs.sources)
    setHorizon(prefs.horizon)
  }, [chatId])

  useEffect(() => {
    localStorage.setItem(
      `runPrefs:${chatId}`,
      JSON.stringify({ sources: selectedSources, horizon }),
    )
  }, [chatId, selectedSources, horizon])

  const toggleSource = (name: string) =>
    setSelectedSources((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name],
    )

  const preferences = (): RunPreferences | undefined => {
    const prefs: RunPreferences = {}
    if (selectedSources.length) prefs.sources = selectedSources
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

      {files.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {files.map((file) => (
            <span
              key={file.id}
              title={`${file.n_rows} rows · columns: ${file.columns.numeric_columns.join(', ')}${file.scope === 'project' ? ' · shared across project' : ''}`}
              className="flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            >
              <PaperclipIcon className="h-3 w-3" />
              {file.filename}
              {file.scope === 'project' && <span className="text-slate-400">(project)</span>}
              <button
                onClick={() => onRemoveFile(file.id)}
                title="Remove file"
                className="text-slate-400 hover:text-red-500"
              >
                <XIcon className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2">
        <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
          Run options
        </span>
        <div className="relative">
          <button onClick={() => setSourcesOpen(!sourcesOpen)} className={controlClass}>
            Data sources:{' '}
            {selectedSources.length ? `${selectedSources.length} selected` : 'auto'}
          </button>
          {sourcesOpen && (
            <div className="absolute bottom-full left-0 z-30 mb-1 max-h-64 w-64 overflow-y-auto rounded-lg border border-slate-200 bg-white p-2 shadow-lg dark:border-slate-700 dark:bg-slate-900">
              <p className="mb-1 px-1 text-[10px] text-slate-400">
                Pick any number of sources for this chat's runs.
              </p>
              {sources.map((source) => (
                <label
                  key={source.name}
                  className="flex cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-xs hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <input
                    type="checkbox"
                    checked={selectedSources.includes(source.name)}
                    onChange={() => toggleSource(source.name)}
                  />
                  {source.label}
                </label>
              ))}
              <button
                onClick={() => {
                  setSelectedSources([])
                  setSourcesOpen(false)
                }}
                className="mt-1 w-full rounded border border-slate-200 px-2 py-1 text-[11px] text-slate-500 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
              >
                Clear (auto)
              </button>
            </div>
          )}
        </div>
        <select value={horizon} onChange={(e) => setHorizon(e.target.value)} className={controlClass}>
          {HORIZONS.map((h) => (
            <option key={h.value} value={h.value}>
              {h.label}
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-end gap-2 rounded-xl border border-slate-200 bg-white p-2 focus-within:border-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:focus-within:border-slate-500">
        <input
          ref={fileInput}
          type="file"
          accept=".csv,.tsv,.txt,.xlsx,.xls,.json"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) onAttach(file)
            e.target.value = ''
          }}
        />
        <button
          onClick={() => fileInput.current?.click()}
          disabled={uploading}
          title="Attach a data file (CSV, Excel, TSV, JSON)"
          className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 disabled:opacity-40 dark:hover:bg-slate-800 dark:hover:text-slate-300"
        >
          {uploading ? <SpinnerIcon /> : <PaperclipIcon />}
        </button>
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
