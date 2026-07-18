import type { Plan, RunEvent } from '../../types'
import { CheckIcon, SpinnerIcon, XIcon } from '../icons'

type NodeStatus = 'pending' | 'running' | 'done' | 'failed'

function nodeStatuses(plan: Plan | null, events: RunEvent[]): Record<string, NodeStatus> {
  const statuses: Record<string, NodeStatus> = {}
  if (!plan) return statuses
  for (const node of plan.nodes) statuses[node.id] = 'pending'
  for (const event of events) {
    const nodeId = event.payload?.node as string | undefined
    if (!nodeId || !(nodeId in statuses)) continue
    if (event.type === 'node_started') statuses[nodeId] = 'running'
    if (event.type === 'node_finished') statuses[nodeId] = 'done'
    if (event.type === 'node_failed') statuses[nodeId] = 'failed'
  }
  return statuses
}

const ROLE_LABELS: Record<string, string> = {
  data_scout: 'Data scout',
  data_fetcher: 'Data fetcher',
  modeler: 'Modeler',
  validator: 'Validator',
  explainer: 'Explainer',
  chart_builder: 'Chart builder',
}

export default function RunProgress({
  plan,
  events,
  failed,
}: {
  plan: Plan | null
  events: RunEvent[]
  failed: boolean
}) {
  const statuses = nodeStatuses(plan, events)
  const toolCalls = events.filter((e) => e.type === 'tool_call')

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-slate-400">
        {failed ? <XIcon className="h-3.5 w-3.5 text-red-500" /> : null}
        Agent workflow{plan ? ` — ${plan.kind.replace('_', ' ')}` : ''}
      </div>
      {!plan && (
        <div className="flex items-center gap-2 text-slate-500">
          <SpinnerIcon className="h-4 w-4" /> Planning the workflow…
        </div>
      )}
      {plan && (
        <ol className="space-y-1.5">
          {plan.nodes.map((node) => {
            const status = statuses[node.id] ?? 'pending'
            return (
              <li key={node.id} className="flex items-start gap-2">
                <span className="mt-0.5">
                  {status === 'running' && <SpinnerIcon className="h-3.5 w-3.5 text-blue-500" />}
                  {status === 'done' && <CheckIcon className="h-3.5 w-3.5 text-emerald-600" />}
                  {status === 'failed' && <XIcon className="h-3.5 w-3.5 text-red-500" />}
                  {status === 'pending' && (
                    <span className="block h-3.5 w-3.5 rounded-full border border-slate-300 dark:border-slate-600" />
                  )}
                </span>
                <div className="min-w-0">
                  <span
                    className={
                      status === 'pending'
                        ? 'text-slate-400'
                        : 'font-medium text-slate-700 dark:text-slate-200'
                    }
                  >
                    {ROLE_LABELS[node.role] ?? node.role}
                  </span>
                  <span className="ml-2 text-xs text-slate-400">{node.id}</span>
                  {status === 'running' && (
                    <p className="truncate text-xs text-slate-500">{node.instructions}</p>
                  )}
                </div>
              </li>
            )
          })}
        </ol>
      )}
      {toolCalls.length > 0 && (
        <div className="mt-2 border-t border-slate-200 pt-2 text-xs text-slate-400 dark:border-slate-800">
          {toolCalls.length} tool call{toolCalls.length === 1 ? '' : 's'} — latest:{' '}
          <code className="text-slate-500 dark:text-slate-300">
            {String(toolCalls[toolCalls.length - 1].payload?.tool ?? '')}
          </code>
        </div>
      )}
    </div>
  )
}
