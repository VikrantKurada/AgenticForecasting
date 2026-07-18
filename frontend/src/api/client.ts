import type {
  Artifact,
  Chat,
  Datasource,
  DatasourceKeyStatus,
  Integration,
  Message,
  PostMessageResponse,
  Project,
  ProviderInfo,
  Run,
  RunPreferences,
  TraceSpan,
  UsageSummary,
} from '../types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!resp.ok) {
    const detail = await resp.text()
    throw new Error(`${resp.status}: ${detail}`)
  }
  if (resp.status === 204) return undefined as T
  return resp.json()
}

export const api = {
  // projects
  listProjects: (q = '') =>
    request<Project[]>(`/api/projects${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  createProject: (name: string, description = '') =>
    request<Project>('/api/projects', { method: 'POST', body: JSON.stringify({ name, description }) }),
  deleteProject: (id: string) => request<void>(`/api/projects/${id}`, { method: 'DELETE' }),

  // chats
  listChats: (projectId: string) => request<Chat[]>(`/api/projects/${projectId}/chats`),
  createChat: (projectId: string, title = 'New chat') =>
    request<Chat>(`/api/projects/${projectId}/chats`, { method: 'POST', body: JSON.stringify({ title }) }),
  deleteChat: (id: string) => request<void>(`/api/chats/${id}`, { method: 'DELETE' }),
  getChat: (id: string) => request<Chat>(`/api/chats/${id}`),
  renameChat: (id: string, title: string) =>
    request<Chat>(`/api/chats/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) }),
  getMessages: (chatId: string) => request<Message[]>(`/api/chats/${chatId}/messages`),
  postMessage: (chatId: string, content: string, preferences?: RunPreferences) =>
    request<PostMessageResponse>(`/api/chats/${chatId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, preferences }),
    }),
  exportChat: (chatId: string, directory: string) =>
    request<{ status: string; path: string; files: number }>(`/api/chats/${chatId}/export`, {
      method: 'POST',
      body: JSON.stringify({ directory }),
    }),
  exportProject: (projectId: string, directory: string) =>
    request<{ status: string; path: string; files: number }>(
      `/api/projects/${projectId}/export`,
      { method: 'POST', body: JSON.stringify({ directory }) },
    ),

  // runs
  getRun: (id: string) => request<Run>(`/api/runs/${id}`),
  getRunArtifacts: (id: string) => request<Artifact[]>(`/api/runs/${id}/artifacts`),
  getRunTrace: (id: string) => request<{ run_id: string; spans: TraceSpan[] }>(`/api/runs/${id}/trace`),

  // telemetry
  getUsage: (projectId: string) => request<UsageSummary>(`/api/projects/${projectId}/usage`),

  // settings
  getProviders: () => request<{ order: string[]; providers: ProviderInfo[] }>('/api/settings/providers'),
  putProviders: (body: { order?: string[]; models?: Record<string, string>; enabled?: Record<string, boolean> }) =>
    request<{ status: string }>('/api/settings/providers', { method: 'PUT', body: JSON.stringify(body) }),
  testProvider: (provider: string) =>
    request<{ status: string; model?: string; reply?: string; detail?: string }>(
      '/api/settings/providers/test',
      { method: 'POST', body: JSON.stringify({ provider }) },
    ),
  getDatasources: () => request<Datasource[]>('/api/datasources'),
  getDatasourceKeys: () =>
    request<Record<string, DatasourceKeyStatus>>('/api/settings/datasource-keys'),
  putDatasourceKeys: (keys: Record<string, string>) =>
    request<{ status: string }>('/api/settings/datasource-keys', {
      method: 'PUT',
      body: JSON.stringify({ keys }),
    }),
  getIntegrations: () =>
    request<{ active: string; configs: Record<string, unknown>; integrations: Integration[] }>(
      '/api/settings/integrations',
    ),
  putIntegrations: (body: { active?: string; configs?: Record<string, unknown> }) =>
    request<{ status: string; active: string }>('/api/settings/integrations', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  // files
  getDefaultDir: () => request<{ path: string }>('/api/fs/default-dir'),
  saveArtifact: (artifactId: string, directory: string, filename?: string) =>
    request<{ status: string; path: string }>(`/api/artifacts/${artifactId}/save`, {
      method: 'POST',
      body: JSON.stringify({ directory, filename }),
    }),
}
