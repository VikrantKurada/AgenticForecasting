import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { Artifact } from '../../types'
import { XIcon } from '../icons'

export default function SaveDialog({
  artifact,
  onClose,
}: {
  artifact: Artifact
  onClose: () => void
}) {
  const [directory, setDirectory] = useState('')
  const [filename, setFilename] = useState('')
  const [result, setResult] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.getDefaultDir().then((d) => setDirectory(d.path)).catch(() => undefined)
  }, [])

  const save = async () => {
    setSaving(true)
    setError('')
    setResult('')
    try {
      const resp = await api.saveArtifact(artifact.id, directory, filename || undefined)
      setResult(resp.path)
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-xl dark:border-slate-700 dark:bg-slate-900">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Save "{artifact.title}"</h3>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:text-slate-600">
            <XIcon />
          </button>
        </div>
        <label className="mb-1 block text-xs font-medium text-slate-500">Save to folder</label>
        <input
          value={directory}
          onChange={(e) => setDirectory(e.target.value)}
          className="mb-3 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-slate-500 dark:border-slate-600 dark:bg-slate-950"
        />
        <label className="mb-1 block text-xs font-medium text-slate-500">
          Filename (optional, extension added automatically)
        </label>
        <input
          value={filename}
          onChange={(e) => setFilename(e.target.value)}
          placeholder={artifact.title}
          className="mb-4 w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-slate-500 dark:border-slate-600 dark:bg-slate-950"
        />
        {result && (
          <p className="mb-3 rounded-md bg-emerald-50 px-3 py-2 text-xs text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
            Saved to {result}
          </p>
        )}
        {error && (
          <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950 dark:text-red-300">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm dark:border-slate-600"
          >
            {result ? 'Done' : 'Cancel'}
          </button>
          <button
            onClick={save}
            disabled={saving || !directory}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
