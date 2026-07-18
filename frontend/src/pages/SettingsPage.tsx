import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Datasource, Integration, ProviderInfo } from '../types'

type Tab = 'providers' | 'datasources' | 'memory' | 'mcp'

function Badge({ ok, yes, no }: { ok: boolean; yes: string; no: string }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
        ok
          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
          : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
      }`}
    >
      {ok ? yes : no}
    </span>
  )
}

function ProvidersSection() {
  const [order, setOrder] = useState<string[]>([])
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [models, setModels] = useState<Record<string, string>>({})
  const [enabled, setEnabled] = useState<Record<string, boolean>>({})
  const [testResults, setTestResults] = useState<Record<string, string>>({})
  const [status, setStatus] = useState('')

  useEffect(() => {
    api.getProviders().then((data) => {
      setOrder(data.order)
      setProviders(data.providers)
      setModels(Object.fromEntries(data.providers.map((p) => [p.name, p.model])))
      setEnabled(Object.fromEntries(data.providers.map((p) => [p.name, p.enabled])))
    })
  }, [])

  const move = (name: string, delta: number) => {
    const idx = order.indexOf(name)
    const to = idx + delta
    if (idx < 0 || to < 0 || to >= order.length) return
    const next = [...order]
    next.splice(idx, 1)
    next.splice(to, 0, name)
    setOrder(next)
  }

  const save = async () => {
    setStatus('Saving…')
    await api.putProviders({ order, models, enabled })
    setStatus('Saved. The provider chain was rebuilt.')
  }

  const test = async (name: string) => {
    setTestResults({ ...testResults, [name]: '…' })
    const result = await api.testProvider(name)
    setTestResults({
      ...testResults,
      [name]: result.status === 'ok' ? `ok — "${result.reply ?? ''}"` : `error — ${result.detail}`,
    })
  }

  const byName = Object.fromEntries(providers.map((p) => [p.name, p]))
  const ordered = [...order.filter((n) => byName[n]), ...providers.map((p) => p.name).filter((n) => !order.includes(n))]

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-400">
        The first configured, enabled provider is used; the rest are fallbacks in order.
        API keys are read from <code>backend/.env</code> and never leave this machine.
      </p>
      {ordered.map((name) => {
        const provider = byName[name]
        if (!provider) return null
        return (
          <div
            key={name}
            className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 px-3 py-2.5 dark:border-slate-800"
          >
            <div className="flex flex-col">
              <button onClick={() => move(name, -1)} className="text-[10px] text-slate-400 hover:text-slate-600">▲</button>
              <button onClick={() => move(name, 1)} className="text-[10px] text-slate-400 hover:text-slate-600">▼</button>
            </div>
            <span className="w-24 text-sm font-medium capitalize">{name}</span>
            <Badge ok={provider.configured} yes="key found" no="no key" />
            <input
              value={models[name] ?? ''}
              onChange={(e) => setModels({ ...models, [name]: e.target.value })}
              className="w-56 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs outline-none focus:border-slate-400 dark:border-slate-700 dark:bg-slate-950"
            />
            <label className="flex items-center gap-1.5 text-xs text-slate-500">
              <input
                type="checkbox"
                checked={enabled[name] ?? true}
                onChange={(e) => setEnabled({ ...enabled, [name]: e.target.checked })}
              />
              enabled
            </label>
            <button
              onClick={() => test(name)}
              disabled={!provider.configured}
              className="rounded-md border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:hover:bg-slate-800"
            >
              Test
            </button>
            {testResults[name] && (
              <span className="max-w-xs truncate text-[11px] text-slate-400">{testResults[name]}</span>
            )}
          </div>
        )
      })}
      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={save}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white dark:bg-slate-100 dark:text-slate-900"
        >
          Save providers
        </button>
        <span className="text-xs text-slate-400">{status}</span>
      </div>
    </div>
  )
}

function DatasourcesSection() {
  const [sources, setSources] = useState<Datasource[]>([])
  useEffect(() => {
    api.getDatasources().then(setSources)
  }, [])
  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-400">
        Economic data connectors. Keys go in <code>backend/.env</code> (FRED_API_KEY, BLS_API_KEY).
      </p>
      {sources.map((source) => (
        <div
          key={source.name}
          className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 px-3 py-2.5 dark:border-slate-800"
        >
          <span className="w-44 text-sm font-medium">{source.label}</span>
          <Badge ok={source.available} yes="available" no="planned" />
          {source.needs_key && <Badge ok={source.key_present} yes="key found" no="key missing" />}
          <span className="text-xs text-slate-400">{source.note}</span>
        </div>
      ))}
    </div>
  )
}

function MemorySection() {
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [active, setActive] = useState('builtin')
  const [status, setStatus] = useState('')

  useEffect(() => {
    api.getIntegrations().then((data) => {
      setIntegrations(data.integrations)
      setActive(data.active)
    })
  }, [])

  const activate = async (name: string) => {
    setStatus('')
    try {
      const resp = await api.putIntegrations({ active: name })
      setActive(resp.active)
      setStatus(`Active memory backend: ${resp.active}`)
    } catch (e) {
      setStatus(String(e))
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-400">
        Agents keep semantic, episodic, procedural, short-term and long-term memory. The
        built-in SQLite backend always works; cloud platforms can take over when their key is set.
      </p>
      {integrations.map((integration) => (
        <label
          key={integration.name}
          className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 ${
            active === integration.name
              ? 'border-slate-400 dark:border-slate-500'
              : 'border-slate-200 dark:border-slate-800'
          } ${integration.status === 'configurable' ? 'opacity-60' : ''}`}
        >
          <input
            type="radio"
            name="memory-backend"
            checked={active === integration.name}
            disabled={integration.status === 'configurable'}
            onChange={() => activate(integration.name)}
          />
          <span className="w-40 text-sm font-medium">{integration.label}</span>
          <Badge
            ok={integration.status !== 'configurable'}
            yes={integration.status === 'builtin' ? 'built-in' : 'adapter ready'}
            no="connect stub"
          />
          <span className="text-xs text-slate-400">{integration.note}</span>
        </label>
      ))}
      {status && <p className="text-xs text-slate-400">{status}</p>}
    </div>
  )
}

function MCPSection() {
  const [servers, setServers] = useState<Record<string, { url: string; note?: string }>>({})
  const [newName, setNewName] = useState('')
  const [newUrl, setNewUrl] = useState('')
  const [status, setStatus] = useState('')

  useEffect(() => {
    fetch('/api/settings/mcp')
      .then((r) => r.json())
      .then((data) => setServers(data.servers ?? {}))
  }, [])

  const save = async (next: typeof servers) => {
    setServers(next)
    await fetch('/api/settings/mcp', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ servers: next }),
    })
    setStatus('Saved.')
  }

  const add = () => {
    if (!newName.trim() || !newUrl.trim()) return
    save({ ...servers, [newName.trim()]: { url: newUrl.trim() } })
    setNewName('')
    setNewUrl('')
  }

  const remove = (name: string) => {
    const next = { ...servers }
    delete next[name]
    save(next)
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-400">
        Agents can call tools on any MCP server you register here (streamable-HTTP transport).
      </p>
      {Object.entries(servers).map(([name, cfg]) => (
        <div
          key={name}
          className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2.5 dark:border-slate-800"
        >
          <span className="w-36 truncate text-sm font-medium">{name}</span>
          <span className="flex-1 truncate text-xs text-slate-400">{cfg.url}</span>
          <button onClick={() => remove(name)} className="text-xs text-slate-400 hover:text-red-500">
            remove
          </button>
        </div>
      ))}
      <div className="flex gap-2">
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="name"
          className="w-36 rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs outline-none dark:border-slate-700 dark:bg-slate-950"
        />
        <input
          value={newUrl}
          onChange={(e) => setNewUrl(e.target.value)}
          placeholder="https://host/mcp"
          className="flex-1 rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs outline-none dark:border-slate-700 dark:bg-slate-950"
        />
        <button
          onClick={add}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white dark:bg-slate-100 dark:text-slate-900"
        >
          Add
        </button>
      </div>
      {status && <p className="text-xs text-slate-400">{status}</p>}
    </div>
  )
}

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>('providers')
  const tabs: { key: Tab; label: string }[] = [
    { key: 'providers', label: 'LLM providers' },
    { key: 'datasources', label: 'Data sources' },
    { key: 'memory', label: 'Memory' },
    { key: 'mcp', label: 'MCP servers' },
  ]
  return (
    <div className="h-full overflow-y-auto px-6 py-6">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-lg font-semibold tracking-tight">Settings</h1>
        <div className="mt-4 flex gap-1 border-b border-slate-200 dark:border-slate-800">
          {tabs.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                tab === key
                  ? 'border-slate-900 text-slate-900 dark:border-slate-100 dark:text-slate-100'
                  : 'border-transparent text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="py-4">
          {tab === 'providers' && <ProvidersSection />}
          {tab === 'datasources' && <DatasourcesSection />}
          {tab === 'memory' && <MemorySection />}
          {tab === 'mcp' && <MCPSection />}
        </div>
      </div>
    </div>
  )
}
