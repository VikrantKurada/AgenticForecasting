import type { Data as PlotlyData, Layout as PlotlyLayout } from 'plotly.js'
import { useState } from 'react'
import Markdown from 'react-markdown'
import type { Artifact, Plan, Run, TraceSpan } from '../../types'
import { DownloadIcon } from '../icons'
import Plot from './Plot'

function ArtifactCard({
  artifact,
  onSave,
  label,
  children,
}: {
  artifact: Artifact
  onSave: (a: Artifact) => void
  label?: string
  children: React.ReactNode
}) {
  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-800">
      <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2 dark:border-slate-800">
        <span className="min-w-0 truncate text-xs font-medium text-slate-600 dark:text-slate-300">
          {label && (
            <span className="mr-1.5 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              {label}
            </span>
          )}
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

function ChartBody({ artifact }: { artifact: Artifact }) {
  return (
    <Plot
      data={(artifact.payload.data ?? []) as PlotlyData[]}
      layout={{ ...(artifact.payload.layout as Partial<PlotlyLayout>), autosize: true }}
      useResizeHandler
      style={{ width: '100%', height: '300px' }}
      config={{ displaylogo: false, responsive: true }}
    />
  )
}

function TableBody({ artifact }: { artifact: Artifact }) {
  const columns = (artifact.payload.columns ?? []) as string[]
  const rows = (artifact.payload.rows ?? []) as (string | number | null)[][]
  return (
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
  )
}

/** Figure numbering must match the backend manifest: charts and tables in
 *  creation order, which is what the report's "Figure N" citations refer to. */
function figureNumbers(artifacts: Artifact[]): Map<string, number> {
  const numbers = new Map<string, number>()
  artifacts
    .filter((a) => a.kind === 'chart' || a.kind === 'table')
    .forEach((a, i) => numbers.set(a.id, i + 1))
  return numbers
}

export function ChartsTab({
  artifacts,
  onSave,
}: {
  artifacts: Artifact[]
  onSave: (a: Artifact) => void
}) {
  const charts = artifacts.filter((a) => a.kind === 'chart')
  const numbers = figureNumbers(artifacts)
  if (charts.length === 0)
    return <p className="p-4 text-xs text-slate-400">No charts for this run.</p>
  return (
    <div className="space-y-3 p-3">
      {charts.map((chart) => (
        <ArtifactCard
          key={chart.id}
          artifact={chart}
          onSave={onSave}
          label={`Figure ${numbers.get(chart.id)}`}
        >
          <ChartBody artifact={chart} />
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
  const numbers = figureNumbers(artifacts)
  if (tables.length === 0)
    return <p className="p-4 text-xs text-slate-400">No data tables for this run.</p>
  return (
    <div className="space-y-3 p-3">
      {tables.map((table) => (
        <ArtifactCard
          key={table.id}
          artifact={table}
          onSave={onSave}
          label={`Figure ${numbers.get(table.id)}`}
        >
          <TableBody artifact={table} />
        </ArtifactCard>
      ))}
    </div>
  )
}

function MarkdownArtifacts({
  artifacts,
  kind,
  emptyText,
  onSave,
}: {
  artifacts: Artifact[]
  kind: Artifact['kind']
  emptyText: string
  onSave: (a: Artifact) => void
}) {
  const docs = artifacts.filter((a) => a.kind === kind)
  if (docs.length === 0) return <p className="p-4 text-xs text-slate-400">{emptyText}</p>
  return (
    <div className="space-y-3 p-3">
      {docs.map((doc) => (
        <ArtifactCard key={doc.id} artifact={doc} onSave={onSave}>
          <div className="prose prose-sm prose-slate max-h-[70vh] max-w-none overflow-y-auto px-1 dark:prose-invert [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-[13px] [&_table]:text-xs">
            <Markdown>{String(doc.payload.markdown ?? '')}</Markdown>
          </div>
        </ArtifactCard>
      ))}
    </div>
  )
}

/** The report plus the figures it cites, rendered inline underneath it, so the
 *  narrative and the charts/tables it references live in one place. */
export function ReportTab({
  artifacts,
  onSave,
}: {
  artifacts: Artifact[]
  onSave: (a: Artifact) => void
}) {
  const reports = artifacts.filter((a) => a.kind === 'report')
  const figures = artifacts.filter((a) => a.kind === 'chart' || a.kind === 'table')
  const numbers = figureNumbers(artifacts)
  if (reports.length === 0)
    return <p className="p-4 text-xs text-slate-400">No report for this run.</p>
  return (
    <div className="space-y-3 p-3">
      {reports.map((doc) => (
        <ArtifactCard key={doc.id} artifact={doc} onSave={onSave}>
          <div className="prose prose-sm prose-slate max-w-none px-1 dark:prose-invert [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-[13px] [&_table]:text-xs">
            <Markdown>{String(doc.payload.markdown ?? '')}</Markdown>
          </div>
        </ArtifactCard>
      ))}

      {figures.length > 0 && (
        <div className="space-y-3">
          <p className="px-1 pt-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Figures referenced above
          </p>
          {figures.map((figure) => (
            <ArtifactCard
              key={figure.id}
              artifact={figure}
              onSave={onSave}
              label={`Figure ${numbers.get(figure.id)}`}
            >
              {figure.kind === 'chart' ? (
                <ChartBody artifact={figure} />
              ) : (
                <TableBody artifact={figure} />
              )}
            </ArtifactCard>
          ))}
        </div>
      )}
    </div>
  )
}

export function MethodologyTab(props: { artifacts: Artifact[]; onSave: (a: Artifact) => void }) {
  return (
    <MarkdownArtifacts
      {...props}
      kind="methodology"
      emptyText="No methodology write-up for this run."
    />
  )
}

/** Flatten the span tree so node status can be read regardless of nesting. */
function flattenSpans(spans: TraceSpan[]): TraceSpan[] {
  return spans.flatMap((span) => [span, ...flattenSpans(span.children ?? [])])
}

type NodeState = { status: 'done' | 'running' | 'pending'; output: string; tools: string[] }

function nodeStates(spans: TraceSpan[]): Record<string, NodeState> {
  const states: Record<string, NodeState> = {}
  const flat = flattenSpans(spans)
  for (const span of flat) {
    const nodeId = (span.payload as { node?: string })?.node
    if (!nodeId) continue
    const existing = states[nodeId] ?? { status: 'pending', output: '', tools: [] }
    if (span.event_type === 'node_started') existing.status = 'running'
    if (span.event_type === 'node_finished') {
      existing.status = 'done'
      existing.output = String((span.payload as { output?: string }).output ?? '')
    }
    states[nodeId] = existing
  }
  // Attribute each tool call to the node whose span contains it.
  for (const span of flat) {
    if (span.event_type !== 'node_started') continue
    const nodeId = (span.payload as { node?: string })?.node
    if (!nodeId) continue
    const tools = flattenSpans(span.children ?? [])
      .filter((c) => c.event_type === 'tool_call')
      .map((c) => {
        const p = c.payload as { tool?: string; ok?: boolean }
        return `${p.tool}${p.ok === false ? ' ✕' : ''}`
      })
    if (tools.length) states[nodeId] = { ...states[nodeId], tools }
  }
  return states
}

const STATUS_STYLES: Record<NodeState['status'], string> = {
  done: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300',
  running: 'bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300',
  pending: 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
}

/** The run's orchestrator: the planned DAG, what each step did, and controls to
 *  replay it — optionally with edited instructions. */
export function OrchestratorTab({
  run,
  spans,
  busy,
  onRerun,
}: {
  run: Run | null
  spans: TraceSpan[]
  busy: boolean
  onRerun: (plan?: Plan) => void
}) {
  const [draft, setDraft] = useState<Record<string, string>>({})
  const plan = run?.plan ?? null

  if (!plan)
    return (
      <p className="p-4 text-xs text-slate-400">
        No orchestrator plan recorded for this run.
      </p>
    )

  const states = nodeStates(spans)
  const edited = plan.nodes.some(
    (n) => draft[n.id] !== undefined && draft[n.id].trim() !== n.instructions.trim(),
  )

  const editedPlan = (): Plan => ({
    ...plan,
    nodes: plan.nodes.map((n) => ({ ...n, instructions: draft[n.id] ?? n.instructions })),
  })

  return (
    <div className="space-y-3 p-3">
      <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
        <p className="text-xs font-medium text-slate-700 dark:text-slate-200">
          Workflow — {plan.kind.replace('_', ' ')}
        </p>
        <p className="mt-0.5 text-[11px] text-slate-400">
          {plan.nodes.length} steps · planned by{' '}
          {plan.metadata?.source === 'llm'
            ? 'the planner LLM'
            : plan.metadata?.source === 'rerun'
              ? 'a previous run (replayed)'
              : 'the built-in template'}
        </p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <button
            onClick={() => onRerun()}
            disabled={busy}
            className="rounded-md bg-slate-900 px-2.5 py-1 text-[11px] font-medium text-white hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
          >
            {busy ? 'Starting…' : 'Rerun all steps'}
          </button>
          <button
            onClick={() => onRerun(editedPlan())}
            disabled={busy || !edited}
            title={edited ? 'Rerun with your edited instructions' : 'Edit a step first'}
            className="rounded-md border border-slate-300 px-2.5 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-40 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            Rerun with edits
          </button>
        </div>
      </div>

      {plan.nodes.map((node, i) => {
        const state = states[node.id] ?? { status: 'pending', output: '', tools: [] }
        return (
          <div
            key={node.id}
            className="rounded-lg border border-slate-200 p-3 dark:border-slate-800"
          >
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold text-slate-400">{i + 1}</span>
              <span className="truncate text-xs font-medium text-slate-700 dark:text-slate-200">
                {node.id}
              </span>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {node.role}
              </span>
              <span
                className={`ml-auto rounded px-1.5 py-0.5 text-[10px] font-medium ${STATUS_STYLES[state.status]}`}
              >
                {state.status}
              </span>
            </div>

            <p className="mt-1.5 text-[11px] text-slate-400">
              {node.depends_on.length
                ? `Depends on ${node.depends_on.join(', ')}`
                : 'Runs first (entry point)'}
            </p>

            <textarea
              value={draft[node.id] ?? node.instructions}
              onChange={(e) => setDraft({ ...draft, [node.id]: e.target.value })}
              rows={3}
              spellCheck={false}
              className="mt-2 w-full resize-y rounded border border-slate-200 bg-slate-50 p-1.5 text-[11px] leading-snug text-slate-600 outline-none focus:border-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
            />

            {state.tools.length > 0 && (
              <p className="mt-1.5 text-[10px] text-slate-400">
                Tools: {state.tools.join(', ')}
              </p>
            )}
            {state.output && (
              <details className="mt-1.5">
                <summary className="cursor-pointer text-[10px] text-slate-400 hover:text-slate-600">
                  Output
                </summary>
                <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-[10px] leading-snug text-slate-600 dark:bg-slate-900 dark:text-slate-300">
                  {state.output}
                </pre>
              </details>
            )}
          </div>
        )
      })}
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
