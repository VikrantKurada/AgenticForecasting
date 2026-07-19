import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import Composer from '../components/Chat/Composer'
import MessageList from '../components/Chat/MessageList'
import RunProgress from '../components/Chat/RunProgress'
import { useRunStream } from '../components/Chat/useRunStream'
import ExportDialog from '../components/ExportDialog'
import OutputPanel from '../components/OutputPanel'
import { DownloadIcon } from '../components/icons'
import { useAppStore } from '../store/useAppStore'
import type { Message, Plan, RunPreferences, UploadedFileMeta } from '../types'

export default function ChatPage() {
  const { chatId } = useParams<{ chatId: string }>()
  const setActiveChat = useAppStore((s) => s.setActiveChat)
  const loadChats = useAppStore((s) => s.loadChats)
  const [messages, setMessages] = useState<Message[]>([])
  const [chatTitle, setChatTitle] = useState('')
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const [projectId, setProjectId] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [panelRunId, setPanelRunId] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [sources, setSources] = useState<{ name: string; label: string }[]>([])
  const [files, setFiles] = useState<UploadedFileMeta[]>([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const { events, done } = useRunStream(activeRunId)

  const plan = useMemo<Plan | null>(() => {
    const planEvent = events.find((e) => e.type === 'plan_created')
    return planEvent ? (planEvent.payload as unknown as Plan) : null
  }, [events])
  const runFailed = events.some((e) => e.type === 'run_failed')

  useEffect(() => {
    api
      .getDatasources()
      .then((all) =>
        setSources(all.filter((s) => s.available).map(({ name, label }) => ({ name, label }))),
      )
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!chatId) return
    setMessages([])
    setActiveRunId(null)
    setPanelRunId(null)
    setError('')
    api
      .getMessages(chatId)
      .then(setMessages)
      .catch((e) => setError(String(e)))
    api
      .getChat(chatId)
      .then((chat) => {
        setActiveChat(chat.project_id, chat.id)
        setProjectId(chat.project_id)
        setChatTitle(chat.title)
      })
      .catch(() => undefined)
    api.listChatFiles(chatId).then(setFiles).catch(() => undefined)
  }, [chatId, setActiveChat])

  const onAttach = useCallback(
    async (file: File) => {
      if (!chatId) return
      setUploading(true)
      setError('')
      try {
        await api.uploadChatFile(chatId, file)
        setFiles(await api.listChatFiles(chatId))
      } catch (e) {
        setError(`Upload failed: ${e}`)
      } finally {
        setUploading(false)
      }
    },
    [chatId],
  )

  const onRemoveFile = useCallback(
    async (fileId: string) => {
      await api.deleteUploadedFile(fileId).catch(() => undefined)
      if (chatId) setFiles(await api.listChatFiles(chatId).catch(() => []))
    },
    [chatId],
  )

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, events.length])

  const refreshSidebar = useCallback(() => {
    if (projectId) loadChats(projectId)
  }, [projectId, loadChats])

  useEffect(() => {
    if (!done || !activeRunId || !chatId) return
    const finishedRun = activeRunId
    setActiveRunId(null)
    api.getMessages(chatId).then(setMessages).catch(() => undefined)
    setPanelRunId(finishedRun)
  }, [done, activeRunId, chatId])

  const onSend = useCallback(
    async (content: string, preferences?: RunPreferences) => {
      if (!chatId) return
      setSending(true)
      setError('')
      const firstMessage = messages.length === 0
      try {
        const resp = await api.postMessage(chatId, content, preferences)
        setMessages((prev) => [...prev, resp.user_message])
        if (resp.assistant_message) {
          setMessages((prev) => [...prev, resp.assistant_message!])
        }
        if (resp.run_id && !resp.assistant_message) {
          setActiveRunId(resp.run_id)
        } else if (resp.run_id) {
          setPanelRunId(resp.run_id)
        }
        if (firstMessage) {
          api.getChat(chatId).then((chat) => setChatTitle(chat.title)).catch(() => undefined)
          refreshSidebar()
        }
      } catch (e) {
        setError(String(e))
      } finally {
        setSending(false)
      }
    },
    [chatId, messages.length, refreshSidebar],
  )

  const saveTitle = async () => {
    if (!chatId) return
    const next = titleDraft.trim()
    setEditingTitle(false)
    if (!next || next === chatTitle) return
    const chat = await api.renameChat(chatId, next)
    setChatTitle(chat.title)
    refreshSidebar()
  }

  const busy = sending || activeRunId !== null

  return (
    <div className="flex h-full min-w-0">
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-6 py-2.5 dark:border-slate-800">
          {editingTitle ? (
            <input
              autoFocus
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={saveTitle}
              onKeyDown={(e) => e.key === 'Enter' && saveTitle()}
              className="w-full max-w-md rounded-md border border-slate-300 bg-white px-2 py-1 text-sm outline-none dark:border-slate-600 dark:bg-slate-950"
            />
          ) : (
            <button
              onClick={() => {
                setTitleDraft(chatTitle)
                setEditingTitle(true)
              }}
              title="Click to rename"
              className="min-w-0 truncate text-sm font-medium hover:text-slate-500"
            >
              {chatTitle || 'Chat'}
            </button>
          )}
          <button
            onClick={() => setExporting(true)}
            className="flex shrink-0 items-center gap-1.5 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <DownloadIcon className="h-3.5 w-3.5" /> Export chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="mx-auto max-w-3xl space-y-4">
            <MessageList messages={messages} onOpenRun={setPanelRunId} />
            {activeRunId && <RunProgress plan={plan} events={events} failed={runFailed} />}
            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
                {error}
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>
        <div className="border-t border-slate-200 px-6 py-3 dark:border-slate-800">
          <div className="mx-auto max-w-3xl">
            <Composer
              chatId={chatId ?? ''}
              onSend={onSend}
              busy={busy}
              showSuggestions={messages.length === 0}
              sources={sources}
              files={files}
              uploading={uploading}
              onAttach={onAttach}
              onRemoveFile={onRemoveFile}
            />
          </div>
        </div>
      </div>
      {panelRunId && <OutputPanel runId={panelRunId} onClose={() => setPanelRunId(null)} />}
      {exporting && chatId && (
        <ExportDialog
          title={`Export "${chatTitle}"`}
          onExport={(directory) => api.exportChat(chatId, directory)}
          onClose={() => setExporting(false)}
        />
      )}
    </div>
  )
}
