export interface Project {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
}

export interface Chat {
  id: string
  project_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  chat_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  run_id: string | null
  created_at: string
}

export interface Run {
  id: string
  chat_id: string
  project_id: string
  question: string
  status: 'planning' | 'running' | 'completed' | 'failed'
  plan: Plan | null
  error: string
  started_at: string
  finished_at: string | null
}

export interface PlanNode {
  id: string
  role: string
  instructions: string
  depends_on: string[]
}

export interface Plan {
  kind: string
  nodes: PlanNode[]
  metadata?: { source: string }
}

export interface Artifact {
  id: string
  kind: 'chart' | 'table' | 'report' | 'methodology' | 'file'
  title: string
  payload: Record<string, unknown>
  created_at: string
}

export interface RunPreferences {
  source?: string
  sources?: string[]
  horizon?: number
}

export interface UploadedFileMeta {
  id: string
  project_id: string
  chat_id: string | null
  scope: 'chat' | 'project'
  filename: string
  columns: { date_column: string | null; numeric_columns: string[]; all_columns: string[] }
  n_rows: number
  created_at: string
}

export interface RunEvent {
  id: string
  type: string
  actor: string
  span_id: string
  parent_span_id: string | null
  payload: Record<string, unknown>
  ts: string
}

export interface TraceSpan extends RunEvent {
  event_type: string
  children: TraceSpan[]
}

export interface ProviderInfo {
  name: string
  configured: boolean
  model: string
  enabled: boolean
}

export interface Datasource {
  name: string
  label: string
  category: string
  available: boolean
  needs_key: boolean
  key_present: boolean
  note: string
}

export interface DatasourceKeyStatus {
  present: boolean
  masked: string
}

export interface Integration {
  name: string
  label: string
  status: 'builtin' | 'available' | 'configurable'
  note: string
}

export interface UsageSummary {
  tokens: {
    total_input: number
    total_output: number
    est_cost_usd: number
    by_provider: GroupedUsage[]
    by_model: GroupedUsage[]
    by_role: GroupedUsage[]
  }
  resources: {
    avg_cpu: number
    avg_mem: number
    avg_gpu: number | null
    samples: { ts: string; cpu: number; mem: number; gpu: number | null; gpu_mem: number | null }[]
  }
  runs: { total: number; completed: number; failed: number; running: number }
}

export interface GroupedUsage {
  provider?: string
  model?: string
  agent_role?: string
  input_tokens: number
  output_tokens: number
  est_cost_usd: number
  calls: number
}

export interface PostMessageResponse {
  intent: 'forecast_request' | 'followup' | 'smalltalk'
  user_message: Message
  run_id?: string
  assistant_message?: Message
}
