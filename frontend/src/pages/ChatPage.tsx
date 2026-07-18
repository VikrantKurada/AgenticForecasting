import { useParams } from 'react-router-dom'

export default function ChatPage() {
  const { chatId } = useParams()
  return (
    <div className="flex h-full items-center justify-center text-sm text-slate-400">
      Chat {chatId} — coming online in the next build step.
    </div>
  )
}
