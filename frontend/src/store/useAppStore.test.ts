import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAppStore } from './useAppStore'

const projects = [
  { id: 'p1', name: 'US Macro', description: '', created_at: '', updated_at: '' },
  { id: 'p2', name: 'EU Inflation', description: '', created_at: '', updated_at: '' },
]
const chats = [{ id: 'c1', project_id: 'p1', title: 'Nowcast', created_at: '', updated_at: '' }]

function stubFetch(payload: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    })),
  )
}

describe('useAppStore', () => {
  beforeEach(() => {
    useAppStore.setState({
      projects: [],
      chatsByProject: {},
      activeProjectId: null,
      activeChatId: null,
      sidebarCollapsed: false,
    })
    vi.unstubAllGlobals()
  })

  it('loadProjects fills the project list', async () => {
    stubFetch(projects)
    await useAppStore.getState().loadProjects()
    expect(useAppStore.getState().projects).toHaveLength(2)
    expect(useAppStore.getState().projects[0].name).toBe('US Macro')
  })

  it('loadChats stores chats under their project', async () => {
    stubFetch(chats)
    await useAppStore.getState().loadChats('p1')
    expect(useAppStore.getState().chatsByProject['p1'][0].title).toBe('Nowcast')
  })

  it('renameProject replaces the project in place', async () => {
    useAppStore.setState({ projects })
    stubFetch({ ...projects[0], name: 'US Macro 2026' })
    await useAppStore.getState().renameProject('p1', 'US Macro 2026')
    const listed = useAppStore.getState().projects
    expect(listed.map((p) => p.name)).toEqual(['US Macro 2026', 'EU Inflation'])
  })

  it('renameProject ignores a blank name without calling the API', async () => {
    useAppStore.setState({ projects })
    const fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)
    await useAppStore.getState().renameProject('p1', '   ')
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(useAppStore.getState().projects[0].name).toBe('US Macro')
  })

  it('renameChat updates the chat under its project', async () => {
    useAppStore.setState({ chatsByProject: { p1: chats } })
    stubFetch({ ...chats[0], title: 'UK unemployment' })
    await useAppStore.getState().renameChat('p1', 'c1', 'UK unemployment')
    expect(useAppStore.getState().chatsByProject['p1'][0].title).toBe('UK unemployment')
  })

  it('toggleSidebar flips the collapsed flag', () => {
    expect(useAppStore.getState().sidebarCollapsed).toBe(false)
    useAppStore.getState().toggleSidebar()
    expect(useAppStore.getState().sidebarCollapsed).toBe(true)
  })

  it('setActiveChat records both project and chat', () => {
    useAppStore.getState().setActiveChat('p2', 'c9')
    expect(useAppStore.getState().activeProjectId).toBe('p2')
    expect(useAppStore.getState().activeChatId).toBe('c9')
  })
})
