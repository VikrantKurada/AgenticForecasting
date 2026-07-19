import { create } from 'zustand'
import { api } from '../api/client'
import type { Chat, Project } from '../types'

interface AppState {
  projects: Project[]
  chatsByProject: Record<string, Chat[]>
  activeProjectId: string | null
  activeChatId: string | null
  sidebarCollapsed: boolean

  loadProjects: (q?: string) => Promise<void>
  createProject: (name: string) => Promise<Project>
  renameProject: (id: string, name: string) => Promise<void>
  deleteProject: (id: string) => Promise<void>
  loadChats: (projectId: string) => Promise<void>
  createChat: (projectId: string, title?: string) => Promise<Chat>
  renameChat: (projectId: string, chatId: string, title: string) => Promise<void>
  deleteChat: (projectId: string, chatId: string) => Promise<void>
  setActiveChat: (projectId: string, chatId: string) => void
  toggleSidebar: () => void
}

export const useAppStore = create<AppState>((set, get) => ({
  projects: [],
  chatsByProject: {},
  activeProjectId: null,
  activeChatId: null,
  sidebarCollapsed: false,

  loadProjects: async (q = '') => {
    const projects = await api.listProjects(q)
    set({ projects })
  },

  createProject: async (name) => {
    const project = await api.createProject(name)
    set({ projects: [project, ...get().projects] })
    return project
  },

  renameProject: async (id, name) => {
    const trimmed = name.trim()
    if (!trimmed) return
    const updated = await api.renameProject(id, trimmed)
    set({ projects: get().projects.map((p) => (p.id === id ? updated : p)) })
  },

  deleteProject: async (id) => {
    await api.deleteProject(id)
    const { chatsByProject } = get()
    const rest = { ...chatsByProject }
    delete rest[id]
    set({
      projects: get().projects.filter((p) => p.id !== id),
      chatsByProject: rest,
      activeProjectId: get().activeProjectId === id ? null : get().activeProjectId,
    })
  },

  loadChats: async (projectId) => {
    const chats = await api.listChats(projectId)
    set({ chatsByProject: { ...get().chatsByProject, [projectId]: chats } })
  },

  createChat: async (projectId, title = 'New chat') => {
    const chat = await api.createChat(projectId, title)
    const existing = get().chatsByProject[projectId] ?? []
    set({ chatsByProject: { ...get().chatsByProject, [projectId]: [chat, ...existing] } })
    return chat
  },

  renameChat: async (projectId, chatId, title) => {
    const trimmed = title.trim()
    if (!trimmed) return
    const updated = await api.renameChat(chatId, trimmed)
    const existing = get().chatsByProject[projectId] ?? []
    set({
      chatsByProject: {
        ...get().chatsByProject,
        [projectId]: existing.map((c) => (c.id === chatId ? updated : c)),
      },
    })
  },

  deleteChat: async (projectId, chatId) => {
    await api.deleteChat(chatId)
    const existing = get().chatsByProject[projectId] ?? []
    set({
      chatsByProject: {
        ...get().chatsByProject,
        [projectId]: existing.filter((c) => c.id !== chatId),
      },
      activeChatId: get().activeChatId === chatId ? null : get().activeChatId,
    })
  },

  setActiveChat: (projectId, chatId) =>
    set({ activeProjectId: projectId, activeChatId: chatId }),

  toggleSidebar: () => set({ sidebarCollapsed: !get().sidebarCollapsed }),
}))
