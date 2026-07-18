import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAppStore } from '../store/useAppStore'
import ExportDialog from './ExportDialog'
import {
  ChartIcon,
  ChevronIcon,
  DownloadIcon,
  GearIcon,
  PanelLeftIcon,
  PlusIcon,
  TrashIcon,
} from './icons'

export default function Sidebar() {
  const {
    projects, chatsByProject, activeProjectId, activeChatId, sidebarCollapsed,
    loadProjects, createProject, deleteProject, loadChats, createChat, deleteChat,
    setActiveChat, toggleSidebar,
  } = useAppStore()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [exportTarget, setExportTarget] = useState<{ id: string; name: string } | null>(null)

  useEffect(() => {
    loadProjects()
  }, [loadProjects])

  useEffect(() => {
    const timer = setTimeout(() => loadProjects(query), 200)
    return () => clearTimeout(timer)
  }, [query, loadProjects])

  const toggleProject = (projectId: string) => {
    const next = !expanded[projectId]
    setExpanded({ ...expanded, [projectId]: next })
    if (next && !chatsByProject[projectId]) loadChats(projectId)
  }

  const onCreateProject = async () => {
    const name = newName.trim()
    if (!name) return
    const project = await createProject(name)
    setNewName('')
    setCreating(false)
    setExpanded({ ...expanded, [project.id]: true })
  }

  const onNewChat = async (projectId: string) => {
    const chat = await createChat(projectId)
    setActiveChat(projectId, chat.id)
    navigate(`/chats/${chat.id}`)
  }

  const onOpenChat = (projectId: string, chatId: string) => {
    setActiveChat(projectId, chatId)
    navigate(`/chats/${chatId}`)
  }

  const onDeleteProject = async (projectId: string, name: string) => {
    if (window.confirm(`Delete project "${name}" and all of its chats?`)) {
      await deleteProject(projectId)
      navigate('/')
    }
  }

  if (sidebarCollapsed) {
    return (
      <aside className="flex h-full w-12 flex-col items-center gap-3 border-r border-slate-200 bg-slate-50 py-3 dark:border-slate-800 dark:bg-slate-900">
        <button
          onClick={toggleSidebar}
          title="Expand sidebar"
          className="rounded-md p-2 text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-800"
        >
          <PanelLeftIcon />
        </button>
      </aside>
    )
  }

  return (
    <aside className="flex h-full w-72 flex-col border-r border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between px-4 py-3">
        <NavLink to="/" className="text-sm font-semibold tracking-tight">
          Agentic Forecasting
        </NavLink>
        <button
          onClick={toggleSidebar}
          title="Collapse sidebar"
          className="rounded-md p-1.5 text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-800"
        >
          <PanelLeftIcon />
        </button>
      </div>

      <div className="px-3 pb-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search projects…"
          className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-sm outline-none placeholder:text-slate-400 focus:border-slate-400 dark:border-slate-700 dark:bg-slate-950 dark:focus:border-slate-500"
        />
      </div>

      <div className="flex items-center justify-between px-4 pb-1 pt-2">
        <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
          Projects
        </span>
        <button
          onClick={() => setCreating(!creating)}
          title="New project"
          className="rounded p-1 text-slate-500 hover:bg-slate-200 dark:hover:bg-slate-800"
        >
          <PlusIcon className="h-3.5 w-3.5" />
        </button>
      </div>

      {creating && (
        <div className="flex gap-1.5 px-3 pb-2">
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onCreateProject()}
            placeholder="Project name"
            className="w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-sm outline-none dark:border-slate-600 dark:bg-slate-950"
          />
          <button
            onClick={onCreateProject}
            className="rounded-md bg-slate-900 px-2 text-xs font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900"
          >
            Add
          </button>
        </div>
      )}

      <nav className="flex-1 overflow-y-auto px-2 pb-2">
        {projects.length === 0 && (
          <p className="px-2 py-4 text-xs text-slate-400">
            No projects yet. Create one to start forecasting.
          </p>
        )}
        {projects.map((project) => (
          <div key={project.id} className="mb-0.5">
            <div
              className={`group flex items-center gap-1 rounded-md px-2 py-1.5 text-sm hover:bg-slate-200/70 dark:hover:bg-slate-800 ${
                activeProjectId === project.id ? 'bg-slate-200/70 dark:bg-slate-800' : ''
              }`}
            >
              <button
                onClick={() => toggleProject(project.id)}
                className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
              >
                <ChevronIcon
                  className={`h-3 w-3 text-slate-400 transition-transform ${expanded[project.id] ? 'rotate-90' : ''}`}
                />
                <span className="truncate font-medium">{project.name}</span>
              </button>
              <button
                onClick={() => onNewChat(project.id)}
                title="New chat"
                className="hidden rounded p-1 text-slate-400 hover:text-slate-700 group-hover:block dark:hover:text-slate-200"
              >
                <PlusIcon className="h-3 w-3" />
              </button>
              <button
                onClick={() => setExportTarget({ id: project.id, name: project.name })}
                title="Export project to folder"
                className="hidden rounded p-1 text-slate-400 hover:text-slate-700 group-hover:block dark:hover:text-slate-200"
              >
                <DownloadIcon className="h-3 w-3" />
              </button>
              <button
                onClick={() => onDeleteProject(project.id, project.name)}
                title="Delete project"
                className="hidden rounded p-1 text-slate-400 hover:text-red-500 group-hover:block"
              >
                <TrashIcon className="h-3 w-3" />
              </button>
            </div>

            {expanded[project.id] && (
              <div className="ml-4 border-l border-slate-200 pl-2 dark:border-slate-700">
                {(chatsByProject[project.id] ?? []).map((chat) => (
                  <div
                    key={chat.id}
                    className={`group flex items-center rounded-md px-2 py-1 text-[13px] hover:bg-slate-200/70 dark:hover:bg-slate-800 ${
                      activeChatId === chat.id
                        ? 'bg-slate-200/70 font-medium dark:bg-slate-800'
                        : 'text-slate-600 dark:text-slate-300'
                    }`}
                  >
                    <button
                      onClick={() => onOpenChat(project.id, chat.id)}
                      className="min-w-0 flex-1 truncate text-left"
                    >
                      {chat.title}
                    </button>
                    <button
                      onClick={() => deleteChat(project.id, chat.id)}
                      title="Delete chat"
                      className="hidden rounded p-0.5 text-slate-400 hover:text-red-500 group-hover:block"
                    >
                      <TrashIcon className="h-3 w-3" />
                    </button>
                  </div>
                ))}
                {(chatsByProject[project.id] ?? []).length === 0 && (
                  <button
                    onClick={() => onNewChat(project.id)}
                    className="px-2 py-1 text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                  >
                    + first chat
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </nav>

      <div className="border-t border-slate-200 p-2 dark:border-slate-800">
        <NavLink
          to={activeProjectId ? `/projects/${activeProjectId}/usage` : '/usage'}
          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-slate-600 hover:bg-slate-200/70 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          <ChartIcon /> Usage
        </NavLink>
        <NavLink
          to="/settings"
          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-slate-600 hover:bg-slate-200/70 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          <GearIcon /> Settings
        </NavLink>
      </div>
      {exportTarget && (
        <ExportDialog
          title={`Export project "${exportTarget.name}"`}
          onExport={(directory) => api.exportProject(exportTarget.id, directory)}
          onClose={() => setExportTarget(null)}
        />
      )}
    </aside>
  )
}
