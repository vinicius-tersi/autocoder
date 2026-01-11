import { useCallback, useRef, useState } from 'react'
import type { ImageAttachment } from '../lib/types'

interface IterationChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export interface IterationMetadata {
  version: number
  project_type: string
  spec_backup: string
  db_backup: string
  instructions_file: string
  feature_count: number
  next_priority: number
}

interface UseIterationChatProps {
  projectName: string
  onComplete: (metadata: IterationMetadata) => void
  onError: (error: string) => void
}

export function useIterationChat({
  projectName,
  onComplete,
  onError,
}: UseIterationChatProps) {
  const [messages, setMessages] = useState<IterationChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isComplete, setIsComplete] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const [iterationMetadata, setIterationMetadata] = useState<IterationMetadata | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 3

  const start = useCallback(async () => {
    try {
      // Start session
      const response = await fetch(`/api/iteration/sessions/${projectName}/start`, {
        method: 'POST',
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to start iteration session')
      }

      // Connect WebSocket
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/api/iteration/ws/${projectName}`

      setConnectionStatus('connecting')
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnectionStatus('connected')
        reconnectAttempts.current = 0
      }

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)

        if (data.type === 'message') {
          setMessages(prev => [...prev, {
            role: data.role,
            content: data.content,
            timestamp: new Date().toISOString()
          }])
          setIsLoading(false)

          // Detect completion message from Claude (via MCP tool)
          if (data.content.includes('✅ **Iteration Completed Successfully!**')) {
            // Parse metadata from the message
            const parseMetadata = (content: string): IterationMetadata | null => {
              try {
                const versionMatch = content.match(/\*\*Version:\*\* v(\d+)/)
                const specMatch = content.match(/- Spec: `([^`]+)`/)
                const dbMatch = content.match(/- Database: `([^`]+)`/)
                const instructionsMatch = content.match(/- Instructions: `([^`]+)`/)
                const featureCountMatch = content.match(/- Existing Features: <strong>(\d+)<\/strong>/)
                const nextPriorityMatch = content.match(/- Next Priority: <strong>(\d+)<\/strong>/)

                if (versionMatch && specMatch && dbMatch && instructionsMatch) {
                  return {
                    version: parseInt(versionMatch[1]),
                    project_type: 'brownfield',
                    spec_backup: specMatch[1],
                    db_backup: dbMatch[1],
                    instructions_file: instructionsMatch[1],
                    feature_count: featureCountMatch ? parseInt(featureCountMatch[1]) : 0,
                    next_priority: nextPriorityMatch ? parseInt(nextPriorityMatch[1]) : 0,
                  }
                }
              } catch (e) {
                console.error('Failed to parse iteration metadata:', e)
              }
              return null
            }

            const metadata = parseMetadata(data.content)
            if (metadata) {
              setIterationMetadata(metadata)
              setIsComplete(true)
              onComplete(metadata)
            }
          }
        } else if (data.type === 'error') {
          onError(data.content)
          setIsLoading(false)
        } else if (data.type === 'status') {
          // Status updates
          console.log('Status:', data.content)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        onError('Connection error')
        setConnectionStatus('disconnected')
      }

      ws.onclose = () => {
        setConnectionStatus('disconnected')
        if (reconnectAttempts.current < maxReconnectAttempts && !isComplete) {
          reconnectAttempts.current++
          setTimeout(() => start(), 2000)
        }
      }
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Failed to start session')
    }
  }, [projectName, onError, isComplete])

  const sendMessage = useCallback(
    async (content: string, attachments: ImageAttachment[] = []) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        onError('Not connected')
        return
      }

      setIsLoading(true)

      wsRef.current.send(JSON.stringify({
        type: 'message',
        content,
        attachments,
      }))
    },
    [onError]
  )

  const completeIteration = useCallback(
    async (finalInstructions: string) => {
      try {
        const response = await fetch(`/api/iteration/sessions/${projectName}/complete`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ final_instructions: finalInstructions }),
        })

        if (!response.ok) {
          const error = await response.json()
          throw new Error(error.detail || 'Failed to complete iteration')
        }

        const result = await response.json()
        setIterationMetadata(result.metadata)
        setIsComplete(true)
        onComplete(result.metadata)
      } catch (error) {
        onError(error instanceof Error ? error.message : 'Failed to complete iteration')
      }
    },
    [projectName, onComplete, onError]
  )

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  return {
    messages,
    isLoading,
    isComplete,
    connectionStatus,
    iterationMetadata,
    start,
    sendMessage,
    completeIteration,
    disconnect,
  }
}