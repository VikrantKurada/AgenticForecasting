import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import Composer from '../components/Chat/Composer'
import MessageList from '../components/Chat/MessageList'
import RunProgress from '../components/Chat/RunProgress'
import { useRunStream } from '../components/Chat/useRunStream'
import OutputPanel from '../components/OutputPanel'
import { useAppStore } from '../store/useAppStore'
import type { Message, Plan } from '../types'

export default function ChatPage() {
  const { chatId } = useParams<{ chatId: string }>()
  const setActiveChat = useAppStore((s) => s.setActiveChat)
  const [messages, setMessages] = useState<Message[]>([])
  const [sending, setSending] = useState(false)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [panelRunId, setPanelRunId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const { events, done } = useRunStream(activeRunId)

  const plan = useMemo<Plan | null>(() => {
    const planEvent = events.find((e) => e.type === 'plan_created')
    return planEvent ? (planEvent.payload as unknown as Plan) : null
  }, [events])
  const runFailed = events.some((e) => e.type === 'run_failed')

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
      .then((chat) => setActiveChat(chat.project_id, chat.id))
      .catch(() => undefined)
  }, [chatId, setActiveChat])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, events.length])

  useEffect(() => {
    if (!done || !activeRunId || !chatId) return
    const finishedRun = activeRunId
    setActiveRunId(null)
    api.getMessages(chatId).then(setMessages).catch(() => undefined)
    setPanelRunId(finishedRun)
  }, [done, activeRunId, chatId])

  const onSend = useCallback(
    async (content: string) => {
      if (!chatId) return
      setSending(true)
      setError('')
      try {
        const resp = await api.postMessage(chatId, content)
        setMessages((prev) => [...prev, resp.user_message])
        if (resp.assistant_message) {
          setMessages((prev) => [...prev, resp.assistant_message!])
        }
        if (resp.run_id && !resp.assistant_message) {
          setActiveRunId(resp.run_id)
        } else if (resp.run_id) {
          setPanelRunId(resp.run_id)
        }
      } catch (e) {
        setError(String(e))
      } finally {
        setSending(false)
      }
    },
    [chatId],
  )

  const busy = sending || activeRunId !== null

  return (
    <div className="flex h-full min-w-0">
      <div className="flex min-w-0 flex-1 flex-col">
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
        <div className="border-t border-slate-200 px-6 py-4 dark:border-slate-800">
          <div className="mx-auto max-w-3xl">
            <Composer onSend={onSend} busy={busy} showSuggestions={messages.length === 0} />
          </div>
        </div>
      </div>
      {panelRunId && <OutputPanel runId={panelRunId} onClose={() => setPanelRunId(null)} />}
    </div>
  )
}
