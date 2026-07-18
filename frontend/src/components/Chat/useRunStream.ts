import { useEffect, useRef, useState } from 'react'
import type { RunEvent } from '../../types'

interface RunStream {
  events: RunEvent[]
  done: boolean
}

/** Subscribes to a run's SSE stream and accumulates its trace events. */
export function useRunStream(runId: string | null): RunStream {
  const [events, setEvents] = useState<RunEvent[]>([])
  const [done, setDone] = useState(false)
  const seen = useRef<Set<string>>(new Set())

  useEffect(() => {
    if (!runId) return
    setEvents([])
    setDone(false)
    seen.current = new Set()

    const source = new EventSource(`/api/runs/${runId}/stream`)
    source.addEventListener('run_event', (raw) => {
      const event = JSON.parse((raw as MessageEvent).data) as RunEvent
      if (event.id && seen.current.has(event.id)) return
      if (event.id) seen.current.add(event.id)
      setEvents((prev) => [...prev, event])
    })
    source.addEventListener('end', () => {
      setDone(true)
      source.close()
    })
    source.onerror = () => {
      // The server closes the stream after terminal events; treat as done.
      setDone(true)
      source.close()
    }
    return () => source.close()
  }, [runId])

  return { events, done }
}
