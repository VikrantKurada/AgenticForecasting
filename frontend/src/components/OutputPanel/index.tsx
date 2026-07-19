import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { Artifact, Plan, Run, TraceSpan } from '../../types'
import { XIcon } from '../icons'
import SaveDialog from './SaveDialog'
import {
  ChartsTab,
  DataTab,
  MethodologyTab,
  OrchestratorTab,
  ReportTab,
  TraceTab,
} from './tabs'

type Tab = 'charts' | 'data' | 'report' | 'methodology' | 'orchestrator' | 'trace'

const MIN_WIDTH = 340
const DEFAULT_WIDTH = 460

function clampWidth(width: number): number {
  const max = Math.max(MIN_WIDTH, Math.floor(window.innerWidth * 0.72))
  return Math.min(Math.max(width, MIN_WIDTH), max)
}

export default function OutputPanel({
  runId,
  onClose,
  onRerun,
}: {
  runId: string
  onClose: () => void
  /** Called with the new run id after a rerun is started. */
  onRerun?: (newRunId: string) => void
}) {
  const [run, setRun] = useState<Run | null>(null)
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [spans, setSpans] = useState<TraceSpan[]>([])
  const [tab, setTab] = useState<Tab>('charts')
  const [saveTarget, setSaveTarget] = useState<Artifact | null>(null)
  const [rerunning, setRerunning] = useState(false)
  const [rerunError, setRerunError] = useState('')
  const [width, setWidth] = useState(() =>
    clampWidth(Number(localStorage.getItem('outputPanelWidth')) || DEFAULT_WIDTH),
  )
  const widthRef = useRef(width)
  const dragging = useRef(false)

  useEffect(() => {
    api.getRun(runId).then(setRun).catch(() => undefined)
    api
      .getRunArtifacts(runId)
      .then((items) => {
        setArtifacts(items)
        if (!items.some((a) => a.kind === 'chart')) {
          setTab(items.some((a) => a.kind === 'report') ? 'report' : 'trace')
        }
      })
      .catch(() => undefined)
    api.getRunTrace(runId).then((t) => setSpans(t.spans)).catch(() => undefined)
  }, [runId])

  const onDragStart = useCallback((event: React.PointerEvent) => {
    dragging.current = true
    ;(event.target as HTMLElement).setPointerCapture(event.pointerId)
  }, [])

  const onDragMove = useCallback((event: React.PointerEvent) => {
    if (!dragging.current) return
    const next = clampWidth(window.innerWidth - event.clientX)
    widthRef.current = next
    setWidth(next)
  }, [])

  const onDragEnd = useCallback((event: React.PointerEvent) => {
    if (!dragging.current) return
    dragging.current = false
    ;(event.target as HTMLElement).releasePointerCapture(event.pointerId)
    localStorage.setItem('outputPanelWidth', String(widthRef.current))
  }, [])

  const startRerun = useCallback(
    async (plan?: Plan) => {
      setRerunning(true)
      setRerunError('')
      try {
        const { run_id } = await api.rerunRun(runId, plan)
        onRerun?.(run_id)
      } catch (e) {
        setRerunError(String(e))
      } finally {
        setRerunning(false)
      }
    },
    [runId, onRerun],
  )

  const counts = {
    charts: artifacts.filter((a) => a.kind === 'chart').length,
    data: artifacts.filter((a) => a.kind === 'table').length,
    report: artifacts.filter((a) => a.kind === 'report').length,
    methodology: artifacts.filter((a) => a.kind === 'methodology').length,
    orchestrator: run?.plan?.nodes.length ?? 0,
    trace: spans.length,
  }

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: 'charts', label: 'Charts', count: counts.charts },
    { key: 'data', label: 'Data', count: counts.data },
    { key: 'report', label: 'Report', count: counts.report },
    { key: 'methodology', label: 'Method', count: counts.methodology },
    { key: 'orchestrator', label: 'Steps', count: counts.orchestrator },
    { key: 'trace', label: 'Trace', count: counts.trace },
  ]

  return (
    <aside
      style={{ width }}
      className="relative flex shrink-0 flex-col border-l border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950"
    >
      <div
        onPointerDown={onDragStart}
        onPointerMove={onDragMove}
        onPointerUp={onDragEnd}
        title="Drag to resize"
        className="absolute inset-y-0 -left-1 z-10 w-2 cursor-col-resize hover:bg-slate-300/50 dark:hover:bg-slate-600/50"
      />
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-3 py-2 dark:border-slate-800">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium text-slate-700 dark:text-slate-200">
            {run?.question ?? 'Run output'}
          </p>
          <p className="text-[10px] text-slate-400">
            {run ? `${run.status}${run.plan ? ` · ${run.plan.kind.replace('_', ' ')}` : ''}` : ''}
          </p>
        </div>
        <button onClick={onClose} className="rounded p-1 text-slate-400 hover:text-slate-600">
          <XIcon />
        </button>
      </div>

      <div className="flex border-b border-slate-200 text-xs dark:border-slate-800">
        {tabs.map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex-1 border-b-2 px-1.5 py-2 font-medium transition-colors ${
              tab === key
                ? 'border-slate-900 text-slate-900 dark:border-slate-100 dark:text-slate-100'
                : 'border-transparent text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
            }`}
          >
            {label}
            {count > 0 && <span className="ml-1 text-[10px] text-slate-400">{count}</span>}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {run?.status === 'failed' && (
          <p className="m-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            Run failed: {run.error}
          </p>
        )}
        {tab === 'charts' && <ChartsTab artifacts={artifacts} onSave={setSaveTarget} />}
        {tab === 'data' && <DataTab artifacts={artifacts} onSave={setSaveTarget} />}
        {tab === 'report' && <ReportTab artifacts={artifacts} onSave={setSaveTarget} />}
        {tab === 'methodology' && (
          <MethodologyTab artifacts={artifacts} onSave={setSaveTarget} />
        )}
        {tab === 'orchestrator' && (
          <>
            {rerunError && (
              <p className="m-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
                {rerunError}
              </p>
            )}
            <OrchestratorTab
              run={run}
              spans={spans}
              busy={rerunning}
              onRerun={startRerun}
            />
          </>
        )}
        {tab === 'trace' && <TraceTab spans={spans} />}
      </div>

      {saveTarget && <SaveDialog artifact={saveTarget} onClose={() => setSaveTarget(null)} />}
    </aside>
  )
}
