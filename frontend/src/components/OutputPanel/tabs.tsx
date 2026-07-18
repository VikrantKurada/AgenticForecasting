import type { Data as PlotlyData, Layout as PlotlyLayout } from 'plotly.js'
import Markdown from 'react-markdown'
import type { Artifact, TraceSpan } from '../../types'
import { DownloadIcon } from '../icons'
import Plot from './Plot'

function ArtifactCard({
  artifact,
  onSave,
  children,
}: {
  artifact: Artifact
  onSave: (a: Artifact) => void
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-800">
      <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2 dark:border-slate-800">
        <span className="truncate text-xs font-medium text-slate-600 dark:text-slate-300">
          {artifact.title}
        </span>
        <button
          onClick={() => onSave(artifact)}
          title="Save to file"
          className="rounded p-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
        >
          <DownloadIcon className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="p-2">{children}</div>
    </div>
  )
}

export function ChartsTab({
  artifacts,
  onSave,
}: {
  artifacts: Artifact[]
  onSave: (a: Artifact) => void
}) {
  const charts = artifacts.filter((a) => a.kind === 'chart')
  if (charts.length === 0)
    return <p className="p-4 text-xs text-slate-400">No charts for this run.</p>
  return (
    <div className="space-y-3 p-3">
      {charts.map((chart) => (
        <ArtifactCard key={chart.id} artifact={chart} onSave={onSave}>
          <Plot
            data={(chart.payload.data ?? []) as PlotlyData[]}
            layout={{ ...(chart.payload.layout as Partial<PlotlyLayout>), autosize: true }}
            useResizeHandler
            style={{ width: '100%', height: '300px' }}
            config={{ displaylogo: false, responsive: true }}
          />
        </ArtifactCard>
      ))}
    </div>
  )
}

export function DataTab({
  artifacts,
  onSave,
}: {
  artifacts: Artifact[]
  onSave: (a: Artifact) => void
}) {
  const tables = artifacts.filter((a) => a.kind === 'table')
  if (tables.length === 0)
    return <p className="p-4 text-xs text-slate-400">No data tables for this run.</p>
  return (
    <div className="space-y-3 p-3">
      {tables.map((table) => {
        const columns = (table.payload.columns ?? []) as string[]
        const rows = (table.payload.rows ?? []) as (string | number | null)[][]
        return (
          <ArtifactCard key={table.id} artifact={table} onSave={onSave}>
            <div className="max-h-72 overflow-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-white dark:bg-slate-950">
                  <tr>
                    {columns.map((col) => (
                      <th
                        key={col}
                        className="border-b border-slate-200 px-2 py-1 text-left font-medium text-slate-500 dark:border-slate-700"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {rows.slice(-200).map((row, i) => (
                    <tr key={i} className="border-b border-slate-100 dark:border-slate-800/60">
                      {row.map((cell, j) => (
                        <td key={j} className="px-2 py-1 text-slate-600 dark:text-slate-300">
                          {cell === null ? '—' : String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length > 200 && (
                <p className="px-2 py-1 text-[11px] text-slate-400">
                  Showing latest 200 of {rows.length} rows — save as CSV for the full series.
                </p>
              )}
            </div>
          </ArtifactCard>
        )
      })}
    </div>
  )
}

export function ReportTab({
  artifacts,
  onSave,
}: {
  artifacts: Artifact[]
  onSave: (a: Artifact) => void
}) {
  const reports = artifacts.filter((a) => a.kind === 'report')
  if (reports.length === 0)
    return <p className="p-4 text-xs text-slate-400">No report for this run.</p>
  return (
    <div className="space-y-3 p-3">
      {reports.map((report) => (
        <ArtifactCard key={report.id} artifact={report} onSave={onSave}>
          <div className="prose prose-sm prose-slate max-h-[60vh] max-w-none overflow-y-auto px-1 dark:prose-invert [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-[13px]">
            <Markdown>{String(report.payload.markdown ?? '')}</Markdown>
          </div>
        </ArtifactCard>
      ))}
    </div>
  )
}

function SpanNode({ span, depth }: { span: TraceSpan; depth: number }) {
  const payload = JSON.stringify(span.payload, null, 2)
  return (
    <details className="group" open={depth === 0}>
      <summary className="flex cursor-pointer items-baseline gap-2 rounded px-1.5 py-1 text-xs hover:bg-slate-100 dark:hover:bg-slate-800">
        <span className="font-medium text-slate-700 dark:text-slate-200">{span.event_type}</span>
        <span className="text-slate-400">{span.actor}</span>
        <span className="ml-auto shrink-0 text-[10px] text-slate-400">
          {span.ts?.slice(11, 19)}
        </span>
      </summary>
      <div className="ml-3 border-l border-slate-200 pl-2 dark:border-slate-700">
        {payload !== '{}' && (
          <pre className="my-1 max-h-48 overflow-auto rounded bg-slate-50 p-2 text-[10px] leading-snug text-slate-600 dark:bg-slate-900 dark:text-slate-300">
            {payload.length > 2500 ? payload.slice(0, 2500) + '…' : payload}
          </pre>
        )}
        {span.children.map((child) => (
          <SpanNode key={child.id} span={child} depth={depth + 1} />
        ))}
      </div>
    </details>
  )
}

export function TraceTab({ spans }: { spans: TraceSpan[] }) {
  if (spans.length === 0)
    return <p className="p-4 text-xs text-slate-400">No trace events recorded.</p>
  return (
    <div className="space-y-0.5 p-3">
      {spans.map((span) => (
        <SpanNode key={span.id} span={span} depth={0} />
      ))}
    </div>
  )
}
