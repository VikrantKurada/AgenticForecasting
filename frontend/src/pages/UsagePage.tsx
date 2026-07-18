import type { Data as PlotlyData, Layout as PlotlyLayout } from 'plotly.js'
import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import Plot from '../components/OutputPanel/Plot'
import { useAppStore } from '../store/useAppStore'
import type { UsageSummary } from '../types'

const BLUE = '#2a78d6'
const AQUA = '#1baf7a'
const MUTED = '#898781'
const GRID = '#e1e0d9'

function layout(title: string, overrides: Partial<PlotlyLayout> = {}): Partial<PlotlyLayout> {
  return {
    title: { text: title, font: { size: 13 } },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: "system-ui, 'Segoe UI', sans-serif", size: 11, color: MUTED },
    xaxis: { gridcolor: GRID, zeroline: false },
    yaxis: { gridcolor: GRID, zeroline: false },
    legend: { orientation: 'h', y: -0.25 },
    margin: { l: 45, r: 15, t: 36, b: 30 },
    autosize: true,
    ...overrides,
  }
}

function StatTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 px-4 py-3 dark:border-slate-800">
      <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
      {sub && <p className="text-xs text-slate-400">{sub}</p>}
    </div>
  )
}

const fmt = (n: number) => n.toLocaleString('en-US')

export default function UsagePage() {
  const { projectId: paramId } = useParams<{ projectId: string }>()
  const activeProjectId = useAppStore((s) => s.activeProjectId)
  const projects = useAppStore((s) => s.projects)
  const projectId = paramId ?? activeProjectId
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [error, setError] = useState('')

  const refresh = useCallback(() => {
    if (!projectId) return
    api.getUsage(projectId).then(setUsage).catch((e) => setError(String(e)))
  }, [projectId])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 10_000)
    return () => clearInterval(timer)
  }, [refresh])

  if (!projectId) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-400">
        Select a project in the sidebar to see its usage dashboard.
      </div>
    )
  }

  const projectName = projects.find((p) => p.id === projectId)?.name ?? projectId
  if (!usage) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-400">
        {error || 'Loading usage…'}
      </div>
    )
  }

  const providerChart: PlotlyData[] = [
    {
      type: 'bar', name: 'Input tokens', marker: { color: BLUE },
      x: usage.tokens.by_provider.map((p) => p.provider ?? ''),
      y: usage.tokens.by_provider.map((p) => p.input_tokens),
    },
    {
      type: 'bar', name: 'Output tokens', marker: { color: AQUA },
      x: usage.tokens.by_provider.map((p) => p.provider ?? ''),
      y: usage.tokens.by_provider.map((p) => p.output_tokens),
    },
  ]
  const roleChart: PlotlyData[] = [
    {
      type: 'bar', name: 'Input tokens', marker: { color: BLUE },
      x: usage.tokens.by_role.map((r) => r.agent_role || '(none)'),
      y: usage.tokens.by_role.map((r) => r.input_tokens),
    },
    {
      type: 'bar', name: 'Output tokens', marker: { color: AQUA },
      x: usage.tokens.by_role.map((r) => r.agent_role || '(none)'),
      y: usage.tokens.by_role.map((r) => r.output_tokens),
    },
  ]
  const resourceChart: PlotlyData[] = [
    {
      type: 'scatter', mode: 'lines', name: 'CPU %', line: { color: BLUE, width: 2 },
      x: usage.resources.samples.map((s) => s.ts),
      y: usage.resources.samples.map((s) => s.cpu),
    },
    {
      type: 'scatter', mode: 'lines', name: 'RAM %', line: { color: AQUA, width: 2 },
      x: usage.resources.samples.map((s) => s.ts),
      y: usage.resources.samples.map((s) => s.mem),
    },
    ...(usage.resources.samples.some((s) => s.gpu !== null)
      ? [{
          type: 'scatter', mode: 'lines', name: 'GPU %',
          line: { color: '#eda100', width: 2 },
          x: usage.resources.samples.map((s) => s.ts),
          y: usage.resources.samples.map((s) => s.gpu),
        } as PlotlyData]
      : []),
  ]

  return (
    <div className="h-full overflow-y-auto px-6 py-6">
      <div className="mx-auto max-w-5xl space-y-5">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Usage — {projectName}</h1>
          <p className="text-xs text-slate-400">
            Token consumption, estimated cost, and system load. Refreshes every 10 s.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile
            label="Tokens"
            value={fmt(usage.tokens.total_input + usage.tokens.total_output)}
            sub={`${fmt(usage.tokens.total_input)} in · ${fmt(usage.tokens.total_output)} out`}
          />
          <StatTile label="Est. cost" value={`$${usage.tokens.est_cost_usd.toFixed(4)}`} />
          <StatTile
            label="Runs"
            value={String(usage.runs.total)}
            sub={`${usage.runs.completed} completed · ${usage.runs.failed} failed`}
          />
          <StatTile
            label="Avg load"
            value={`${usage.resources.avg_cpu.toFixed(0)}% CPU`}
            sub={`${usage.resources.avg_mem.toFixed(0)}% RAM${
              usage.resources.avg_gpu != null ? ` · ${usage.resources.avg_gpu.toFixed(0)}% GPU` : ''
            }`}
          />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-slate-200 p-2 dark:border-slate-800">
            <Plot data={providerChart} layout={layout('Tokens by provider', { barmode: 'group' })}
              useResizeHandler style={{ width: '100%', height: '260px' }}
              config={{ displaylogo: false, responsive: true }} />
          </div>
          <div className="rounded-lg border border-slate-200 p-2 dark:border-slate-800">
            <Plot data={roleChart} layout={layout('Tokens by agent role', { barmode: 'group' })}
              useResizeHandler style={{ width: '100%', height: '260px' }}
              config={{ displaylogo: false, responsive: true }} />
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 p-2 dark:border-slate-800">
          {usage.resources.samples.length > 0 ? (
            <Plot data={resourceChart} layout={layout('System load during runs')}
              useResizeHandler style={{ width: '100%', height: '240px' }}
              config={{ displaylogo: false, responsive: true }} />
          ) : (
            <p className="p-6 text-center text-xs text-slate-400">
              No resource samples yet — they are recorded while runs execute.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
