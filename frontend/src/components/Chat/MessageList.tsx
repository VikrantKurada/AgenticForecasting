import type { Message } from '../../types'
import MarkdownBody from '../MarkdownBody'

export default function MessageList({
  messages,
  onOpenRun,
}: {
  messages: Message[]
  onOpenRun: (runId: string) => void
}) {
  return (
    <div className="space-y-4">
      {messages.map((message) =>
        message.role === 'user' ? (
          <div key={message.id} className="flex justify-end">
            <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-slate-900 px-4 py-2.5 text-sm text-white dark:bg-slate-100 dark:text-slate-900">
              {message.content}
            </div>
          </div>
        ) : (
          <div key={message.id} className="flex justify-start">
            <div className="max-w-[92%] text-sm leading-relaxed">
              <MarkdownBody className="[&_h1]:text-lg [&_h2]:text-base [&_h3]:text-sm">
                {message.content}
              </MarkdownBody>
              {message.run_id && (
                <button
                  onClick={() => onOpenRun(message.run_id!)}
                  className="mt-2 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  Open output panel
                </button>
              )}
            </div>
          </div>
        ),
      )}
    </div>
  )
}
