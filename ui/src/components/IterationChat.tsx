/**
 * Iteration Chat Component
 *
 * Interactive chat interface for planning project iterations with Claude.
 * Allows users to discuss changes in natural language.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Send, X, CheckCircle2, AlertCircle, Wifi, WifiOff, GitBranch } from 'lucide-react'
import { useIterationChat, type IterationMetadata } from '../hooks/useIterationChat'
import { ChatMessage } from './ChatMessage'
import { TypingIndicator } from './TypingIndicator'

interface IterationChatProps {
  projectName: string
  onComplete: (metadata: IterationMetadata) => void
  onCancel: () => void
}

export function IterationChat({
  projectName,
  onComplete,
  onCancel,
}: IterationChatProps) {
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleError = useCallback((err: string) => setError(err), [])

  const {
    messages,
    isLoading,
    isComplete,
    connectionStatus,
    iterationMetadata,
    start,
    sendMessage,
    disconnect,
  } = useIterationChat({
    projectName,
    onComplete,
    onError: handleError,
  })

  // Start session
  useEffect(() => {
    start()
    return () => disconnect()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Focus input
  useEffect(() => {
    if (!isLoading && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isLoading])

  const handleSendMessage = () => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return

    sendMessage(trimmed)
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // Completion view
  if (isComplete && iterationMetadata) {
    return (
      <div className="flex flex-col h-full bg-white">
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-2xl">
            <CheckCircle2 size={64} className="mx-auto mb-6 text-green-600" />
            <h2 className="font-display text-3xl font-bold mb-4">
              Iteration Created Successfully!
            </h2>

            <div className="text-left bg-gray-50 border-3 border-black p-6 mb-6">
              <h3 className="font-bold text-lg mb-3">Backups Created</h3>
              <ul className="space-y-2 text-sm font-mono">
                <li>Spec: {iterationMetadata.spec_backup}</li>
                <li>Database: {iterationMetadata.db_backup}</li>
                <li>Instructions: {iterationMetadata.instructions_file}</li>
              </ul>

              <h3 className="font-bold text-lg mt-4 mb-3">Stats</h3>
              <ul className="space-y-1 text-sm">
                <li>Version: <strong>v{iterationMetadata.version}</strong></li>
                <li>Existing Features: <strong>{iterationMetadata.feature_count}</strong></li>
                <li>Next Priority: <strong>{iterationMetadata.next_priority}</strong></li>
              </ul>
            </div>

            <div className="bg-yellow-50 border-3 border-yellow-600 p-4 mb-6 text-left">
              <p className="font-bold mb-2">Next Steps:</p>
              <ol className="list-decimal list-inside space-y-1 text-sm">
                <li>Close this dialog</li>
                <li>Click the Play button to start the agent</li>
                <li>The Initializer Agent will process your iteration</li>
                <li>New features will be created automatically</li>
              </ol>
            </div>

            <button
              onClick={() => onComplete(iterationMetadata)}
              className="neo-btn neo-btn-primary text-lg px-8 py-3"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b-3 border-black bg-[var(--color-neo-text)] text-white">
        <div className="flex items-center gap-3">
          <GitBranch size={24} />
          <div>
            <h2 className="font-display font-bold text-lg">Plan Iteration</h2>
            <p className="text-sm opacity-90">{projectName}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Connection status */}
          <div className="flex items-center gap-2 text-sm">
            {connectionStatus === 'connected' ? (
              <>
                <Wifi size={16} />
                <span>Connected</span>
              </>
            ) : connectionStatus === 'connecting' ? (
              <>
                <WifiOff size={16} className="animate-pulse" />
                <span>Connecting...</span>
              </>
            ) : (
              <>
                <WifiOff size={16} />
                <span>Disconnected</span>
              </>
            )}
          </div>

          {/* Close button */}
          <button
            onClick={onCancel}
            className="neo-btn neo-btn-secondary p-2"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-red-50 border-b-3 border-red-600 p-4 flex items-center gap-3">
          <AlertCircle size={20} className="text-red-600 flex-shrink-0" />
          <p className="text-red-900">{error}</p>
          <button
            onClick={() => setError(null)}
            className="ml-auto neo-btn neo-btn-sm"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((msg, i) => (
          <ChatMessage
            key={i}
            message={{
              id: `${i}`,
              role: msg.role,
              content: msg.content,
              timestamp: new Date(msg.timestamp)
            }}
          />
        ))}
        {isLoading && <TypingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t-3 border-black p-4">
        <div className="flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe what you want to add..."
            className="flex-1 border-3 border-black p-3 font-sans"
            disabled={isLoading || connectionStatus !== 'connected'}
          />
          <button
            onClick={handleSendMessage}
            disabled={!input.trim() || isLoading || connectionStatus !== 'connected'}
            className="neo-btn neo-btn-primary px-6"
          >
            <Send size={20} />
          </button>
        </div>
      </div>

    </div>
  )
}