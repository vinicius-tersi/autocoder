---
description: Add interactive chat interface for Add Iteration (brownfield)
order: 6
optional: true
---

# OBJETIVO

Criar interface de **chat interativo** para "Add Iteration", permitindo que o usuário converse com o Initializer Agent para planejar iterações brownfield, em vez de apenas digitar texto no modal.

**Combina:**
- ✅ Interatividade do **Expand Project** (chat com Claude)
- ✅ Segurança do **Add Iteration** (backups + versionamento)

**Pré-requisitos:** Comandos 01-05 completos.

---

# CONTEXTO

Atualmente existem 2 fluxos para adicionar features:

## Fluxo 1: Expand Project (Chat)
```
Usuário clica ✨ → ExpandProjectChat → Conversa interativa → Features criadas direto no DB
```
**Pros:** Interativo, esclarece dúvidas
**Cons:** Sem backup, sem versionamento, spec desatualizado

## Fluxo 2: Add Iteration (Modal)
```
Usuário clica 🌿 → AddIterationModal → Textarea → Submete → Backups criados → Agent processa
```
**Pros:** Backups, versionamento, spec atualizado
**Cons:** Não interativo, usuário precisa saber exatamente o que quer

## Fluxo 3 (NOVO): Add Iteration Chat
```
Usuário clica 🌿 → IterationChat → Conversa com Initializer → Backups criados → Instruções geradas
```
**Pros:** Interativo + Backups + Versionamento + Spec atualizado
**Cons:** Mais complexo de implementar

---

# ARQUITETURA

## Backend (Novo)

```
server/routers/iteration.py (NOVO)
  ├─ POST /api/iteration/{project_name}/start
  │    └─ Cria sessão de chat
  ├─ WebSocket /ws/iteration/{project_name}
  │    └─ Stream de mensagens
  └─ POST /api/iteration/{project_name}/complete
       └─ Finaliza chat, cria backups + iteration file

server/services/iteration_chat_session.py (NOVO)
  ├─ IterationChatSession class
  │    ├─ Similar a ExpandChatSession
  │    ├─ Usa brownfield-iteration.md skill
  │    └─ Chama iteration_manager no final
  └─ Session management (create, get, remove)
```

## Frontend (Novo)

```
ui/src/components/IterationChat.tsx (NOVO)
  └─ Similar a ExpandProjectChat
       ├─ WebSocket connection
       ├─ Mensagens do usuário
       ├─ Respostas do Claude
       └─ Botão "Complete Iteration"

ui/src/components/IterationChatModal.tsx (NOVO)
  └─ Wrapper full-screen
       └─ IterationChat component

ui/src/hooks/useIterationChat.ts (NOVO)
  └─ WebSocket logic + state management
```

## UI Flow

```
App.tsx
  └─ showIterationChat state (NOVO)
       ├─ Abre via botão 🌿 OU atalho 'i'
       └─ Renderiza <IterationChatModal>
            └─ <IterationChat>
                 ├─ Conecta WebSocket
                 ├─ Envia mensagens
                 ├─ Recebe respostas
                 └─ Completa iteração
```

---

# TAREFAS

## PARTE 1: Backend

### 1.1 Criar `server/services/iteration_chat_session.py`

**Base:** Copiar de `expand_chat_session.py` e adaptar

**Mudanças principais:**

```python
"""
Iteration Chat Session
======================

Manages interactive iteration planning conversation with Claude.
Uses the brownfield-iteration.md skill to help users plan project iterations.

Unlike ExpandChatSession:
1. Reads existing app_spec.txt and features.db for context
2. Has conversation to understand iteration goals
3. At the END, calls iteration_manager.create_iteration()
4. Does NOT create features directly (Initializer Agent does that later)
"""

import asyncio
import json
import logging
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from dotenv import load_dotenv

from ..schemas import ImageAttachment

load_dotenv()


class IterationChatSession:
    """
    Manages an iteration planning conversation.

    Key differences from ExpandChatSession:
    - Uses /brownfield-iteration skill (not /expand-project)
    - Does NOT create features directly
    - Calls iteration_manager.create_iteration() at completion
    - Returns iteration metadata (version, backups, etc.)
    """

    def __init__(self, project_name: str, project_dir: Path):
        self.project_name = project_name
        self.project_dir = project_dir
        self.session_id = str(uuid.uuid4())
        self.messages = []
        self.client: Optional[ClaudeSDKClient] = None
        self.lock = threading.Lock()
        self._complete = False
        self._iteration_created = False
        self._iteration_metadata = None

    def is_complete(self) -> bool:
        """Check if iteration planning is complete."""
        return self._complete

    def get_iteration_metadata(self) -> Optional[dict]:
        """Get metadata about created iteration (version, backups, etc.)."""
        return self._iteration_metadata

    async def start(self) -> AsyncGenerator[dict, None]:
        """
        Start iteration planning session.

        Yields initial greeting and project context.
        """
        # Read existing project state
        spec_file = self.project_dir / "prompts" / "app_spec.txt"
        features_db = self.project_dir / "features.db"

        # Get feature count
        feature_count = 0
        if features_db.exists():
            import sqlite3
            conn = sqlite3.connect(str(features_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM features")
            feature_count = cursor.fetchone()[0]
            conn.close()

        # Read spec summary
        spec_summary = "No specification found"
        if spec_file.exists():
            spec_content = spec_file.read_text(encoding='utf-8')
            # Extract project name and overview (simplified)
            lines = spec_content.split('\n')[:20]
            spec_summary = '\n'.join(lines)

        # Create Claude client with brownfield-iteration skill
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            yield {
                "type": "error",
                "content": "ANTHROPIC_API_KEY not found in environment"
            }
            return

        # Start session with context
        initial_context = f"""You are helping plan an iteration for project: {self.project_name}

Current State:
- Features in database: {feature_count}
- Project directory: {self.project_dir}

Project Specification (first 20 lines):
{spec_summary}

Your goal: Understand what the user wants to add/change, then prepare structured iteration instructions.

Remember: You will NOT create features directly. At the end, you'll call iteration_manager.create_iteration() with the final instructions.

Start by greeting the user and asking what they want to add to this iteration.
"""

        # Initialize client
        options = ClaudeAgentOptions(
            api_key=api_key,
            model="claude-sonnet-4-5-20250929",
        )

        self.client = ClaudeSDKClient(options=options)

        yield {
            "type": "status",
            "content": "Session started"
        }

        # Send initial context and get first response
        try:
            await self.client.query(initial_context)

            async for msg in self.client.receive_response():
                if hasattr(msg, 'content'):
                    for block in msg.content:
                        if hasattr(block, 'text'):
                            self.messages.append({
                                "role": "assistant",
                                "content": block.text,
                                "timestamp": datetime.now().isoformat()
                            })
                            yield {
                                "type": "message",
                                "role": "assistant",
                                "content": block.text
                            }
        except Exception as e:
            logging.error(f"Error starting iteration session: {e}")
            yield {
                "type": "error",
                "content": f"Failed to start session: {str(e)}"
            }

    async def send_message(
        self,
        content: str,
        attachments: list[ImageAttachment] | None = None
    ) -> AsyncGenerator[dict, None]:
        """
        Send user message and stream response.

        Similar to ExpandChatSession but for iteration planning.
        """
        if not self.client:
            yield {
                "type": "error",
                "content": "Session not started"
            }
            return

        # Store user message
        self.messages.append({
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

        yield {
            "type": "message",
            "role": "user",
            "content": content
        }

        try:
            await self.client.query(content)

            async for msg in self.client.receive_response():
                if hasattr(msg, 'content'):
                    for block in msg.content:
                        if hasattr(block, 'text'):
                            self.messages.append({
                                "role": "assistant",
                                "content": block.text,
                                "timestamp": datetime.now().isoformat()
                            })
                            yield {
                                "type": "message",
                                "role": "assistant",
                                "content": block.text
                            }
        except Exception as e:
            logging.error(f"Error sending message: {e}")
            yield {
                "type": "error",
                "content": f"Failed to send message: {str(e)}"
            }

    async def complete_iteration(self, final_instructions: str) -> dict:
        """
        Complete the iteration planning and create backups + iteration file.

        Calls iteration_manager.create_iteration() with final instructions.

        Returns:
            Iteration metadata (version, backup_paths, etc.)
        """
        if self._iteration_created:
            return self._iteration_metadata

        # Import iteration manager
        import sys
        root = Path(__file__).parent.parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        from server.services.iteration_manager import create_iteration

        # Create iteration
        try:
            metadata = await create_iteration(self.project_dir, final_instructions)
            self._iteration_created = True
            self._iteration_metadata = metadata
            self._complete = True

            logging.info(f"Iteration created: v{metadata['version']} for {self.project_name}")

            return metadata
        except Exception as e:
            logging.error(f"Failed to create iteration: {e}")
            raise

    async def disconnect(self):
        """Disconnect Claude client."""
        if self.client:
            # ClaudeSDKClient cleanup (if needed)
            self.client = None


# Session management (similar to expand_chat_session.py)
_iteration_sessions: dict[str, IterationChatSession] = {}
_session_lock = threading.Lock()


def create_iteration_session(project_name: str, project_dir: Path) -> IterationChatSession:
    """Create a new iteration planning session."""
    with _session_lock:
        if project_name in _iteration_sessions:
            # Remove old session
            remove_iteration_session(project_name)

        session = IterationChatSession(project_name, project_dir)
        _iteration_sessions[project_name] = session
        return session


def get_iteration_session(project_name: str) -> Optional[IterationChatSession]:
    """Get existing iteration session."""
    return _iteration_sessions.get(project_name)


def remove_iteration_session(project_name: str):
    """Remove iteration session."""
    with _session_lock:
        session = _iteration_sessions.pop(project_name, None)
        if session:
            asyncio.create_task(session.disconnect())


def list_iteration_sessions() -> list[str]:
    """List all active iteration sessions."""
    return list(_iteration_sessions.keys())


async def cleanup_all_iteration_sessions():
    """Cleanup all iteration sessions."""
    sessions = list(_iteration_sessions.values())
    _iteration_sessions.clear()

    for session in sessions:
        await session.disconnect()
```

---

### 1.2 Criar `server/routers/iteration.py`

**Similar a:** `expand_project.py`

**Endpoints:**

```python
"""
Iteration Router
================

WebSocket and REST endpoints for interactive iteration planning.
Allows planning brownfield iterations via conversational interface.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from ..services.iteration_chat_session import (
    IterationChatSession,
    create_iteration_session,
    get_iteration_session,
    list_iteration_sessions,
    remove_iteration_session,
)
from ..utils.validation import validate_project_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/iteration", tags=["iteration"])


def _get_project_path(project_name: str) -> Path:
    """Get project path from registry."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import get_project_path
    return get_project_path(project_name)


# ============================================================================
# REST Endpoints
# ============================================================================

@router.post("/sessions/{project_name}/start")
async def start_iteration_session(project_name: str):
    """Start a new iteration planning session."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir or not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if project is brownfield
    features_db = project_dir / "features.db"
    if not features_db.exists():
        raise HTTPException(
            status_code=400,
            detail="Project has no features.db - not ready for iteration"
        )

    # Create session
    session = create_iteration_session(project_name, project_dir)

    return {
        "status": "started",
        "session_id": session.session_id,
        "project_name": project_name
    }


@router.post("/sessions/{project_name}/complete")
async def complete_iteration_session(
    project_name: str,
    instructions: dict  # {"final_instructions": "..."}
):
    """
    Complete iteration planning and create backups + iteration file.

    Body:
        final_instructions: Structured iteration instructions from conversation
    """
    project_name = validate_project_name(project_name)

    session = get_iteration_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active iteration session")

    final_instructions = instructions.get("final_instructions", "")
    if not final_instructions:
        raise HTTPException(status_code=400, detail="final_instructions required")

    try:
        metadata = await session.complete_iteration(final_instructions)
        remove_iteration_session(project_name)

        return {
            "status": "completed",
            "metadata": metadata
        }
    except Exception as e:
        logger.error(f"Failed to complete iteration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_iteration_sessions_endpoint():
    """List all active iteration sessions."""
    return list_iteration_sessions()


@router.delete("/sessions/{project_name}")
async def cancel_iteration_session(project_name: str):
    """Cancel an iteration session."""
    project_name = validate_project_name(project_name)

    session = get_iteration_session(project_name)
    if not session:
        raise HTTPException(status_code=404, detail="No active iteration session")

    remove_iteration_session(project_name)
    return {"status": "cancelled"}


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/ws/{project_name}")
async def iteration_websocket(websocket: WebSocket, project_name: str):
    """
    WebSocket endpoint for iteration planning chat.

    Similar to expand project WebSocket but uses iteration_chat_session.
    """
    await websocket.accept()

    try:
        project_name = validate_project_name(project_name)
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "content": f"Invalid project name: {e}"
        })
        await websocket.close()
        return

    session = get_iteration_session(project_name)

    if not session:
        await websocket.send_json({
            "type": "error",
            "content": "No active iteration session. Call /sessions/{project_name}/start first"
        })
        await websocket.close()
        return

    try:
        # Start session and send initial messages
        async for msg in session.start():
            await websocket.send_json(msg)

        # Message loop
        while True:
            # Receive from client
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "message":
                content = data.get("content", "")
                attachments = data.get("attachments", [])

                # Send to Claude and stream responses
                async for response in session.send_message(content, attachments):
                    await websocket.send_json(response)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json({
                    "type": "error",
                    "content": f"Unknown message type: {msg_type}"
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for iteration session: {project_name}")
    except Exception as e:
        logger.error(f"Error in iteration WebSocket: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": f"Session error: {str(e)}"
            })
        except:
            pass
```

---

### 1.3 Registrar router em `server/main.py`

**Adicionar:**

```python
from .routers.iteration import router as iteration_router

# ... existing code ...

app.include_router(iteration_router)
```

---

## PARTE 2: Frontend

### 2.1 Criar `ui/src/hooks/useIterationChat.ts`

**Base:** Copiar de `useExpandChat.ts` e adaptar

**Mudanças:**
- URL: `/api/iteration/` em vez de `/api/expand/`
- WebSocket: `/ws/iteration/{project}` em vez de `/ws/expand/{project}`
- Completion: Chama `/complete` com `final_instructions`
- Não retorna `featuresCreated` (features não são criadas imediatamente)
- Retorna `iterationMetadata` (version, backups, etc.)

```typescript
import { useCallback, useEffect, useRef, useState } from 'react'
import type { ImageAttachment } from '../lib/types'

interface IterationChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

interface IterationMetadata {
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
      const wsUrl = `${protocol}//${window.location.host}/ws/iteration/${projectName}`

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
```

---

### 2.2 Criar `ui/src/components/IterationChat.tsx`

**Base:** Copiar de `ExpandProjectChat.tsx` e adaptar

**Mudanças principais:**
- Usar `useIterationChat` hook
- Botão "Complete Iteration" em vez de auto-complete
- Explicar que backups serão criados
- Mostrar metadata ao completar (version, backups)

```typescript
/**
 * Iteration Chat Component
 *
 * Interactive chat interface for planning project iterations with Claude.
 * Allows users to discuss changes in natural language.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Send, X, CheckCircle2, AlertCircle, Wifi, WifiOff, GitBranch } from 'lucide-react'
import { useIterationChat } from '../hooks/useIterationChat'
import { ChatMessage } from './ChatMessage'
import { TypingIndicator } from './TypingIndicator'

interface IterationChatProps {
  projectName: string
  onComplete: (metadata: any) => void
  onCancel: () => void
}

export function IterationChat({
  projectName,
  onComplete,
  onCancel,
}: IterationChatProps) {
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [showCompleteDialog, setShowCompleteDialog] = useState(false)
  const [finalInstructions, setFinalInstructions] = useState('')
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
    completeIteration,
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

  const handleCompleteClick = () => {
    // Build final instructions from conversation
    const instructions = messages
      .filter(m => m.role === 'user')
      .map(m => m.content)
      .join('\n\n')

    setFinalInstructions(instructions)
    setShowCompleteDialog(true)
  }

  const handleConfirmComplete = async () => {
    await completeIteration(finalInstructions)
    setShowCompleteDialog(false)
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
              <h3 className="font-bold text-lg mb-3">📦 Backups Created</h3>
              <ul className="space-y-2 text-sm font-mono">
                <li>✅ Spec: {iterationMetadata.spec_backup}</li>
                <li>✅ Database: {iterationMetadata.db_backup}</li>
                <li>✅ Instructions: {iterationMetadata.instructions_file}</li>
              </ul>

              <h3 className="font-bold text-lg mt-4 mb-3">📊 Stats</h3>
              <ul className="space-y-1 text-sm">
                <li>Version: <strong>v{iterationMetadata.version}</strong></li>
                <li>Existing Features: <strong>{iterationMetadata.feature_count}</strong></li>
                <li>Next Priority: <strong>{iterationMetadata.next_priority}</strong></li>
              </ul>
            </div>

            <div className="bg-yellow-50 border-3 border-yellow-600 p-4 mb-6 text-left">
              <p className="font-bold mb-2">⚡ Next Steps:</p>
              <ol className="list-decimal list-inside space-y-1 text-sm">
                <li>Close this dialog</li>
                <li>Click the ▶️ Play button to start the agent</li>
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

          {/* Complete button */}
          {messages.length > 2 && connectionStatus === 'connected' && (
            <button
              onClick={handleCompleteClick}
              className="neo-btn neo-btn-primary flex items-center gap-2"
              disabled={isLoading}
            >
              <CheckCircle2 size={18} />
              Complete Iteration
            </button>
          )}

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
          <ChatMessage key={i} message={msg} />
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

      {/* Complete dialog */}
      {showCompleteDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white border-3 border-black p-6 max-w-2xl w-full mx-4">
            <h3 className="font-display font-bold text-xl mb-4">
              Complete Iteration?
            </h3>

            <div className="bg-blue-50 border-3 border-blue-600 p-4 mb-4">
              <p className="font-bold mb-2">This will:</p>
              <ul className="list-disc list-inside space-y-1 text-sm">
                <li>Create versioned backups (spec + database)</li>
                <li>Generate iteration instructions file</li>
                <li>Prepare project for Initializer Agent</li>
                <li>Close this chat</li>
              </ul>
            </div>

            <p className="text-sm text-gray-600 mb-4">
              The Initializer Agent will process your iteration when you start the agent.
            </p>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowCompleteDialog(false)}
                className="neo-btn neo-btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmComplete}
                className="neo-btn neo-btn-primary flex items-center gap-2"
              >
                <CheckCircle2 size={18} />
                Complete Iteration
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

---

### 2.3 Criar `ui/src/components/IterationChatModal.tsx`

**Simples wrapper:**

```typescript
/**
 * Iteration Chat Modal
 *
 * Full-screen modal wrapper for the IterationChat component.
 */

import { IterationChat } from './IterationChat'

interface IterationChatModalProps {
  isOpen: boolean
  projectName: string
  onClose: () => void
  onComplete: (metadata: any) => void
}

export function IterationChatModal({
  isOpen,
  projectName,
  onClose,
  onComplete,
}: IterationChatModalProps) {
  if (!isOpen) return null

  const handleComplete = (metadata: any) => {
    onComplete(metadata)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 bg-[var(--color-neo-bg)]">
      <IterationChat
        projectName={projectName}
        onComplete={handleComplete}
        onCancel={onClose}
      />
    </div>
  )
}
```

---

### 2.4 Modificar `ui/src/App.tsx`

**Adicionar:**

```typescript
// Import
import { IterationChatModal } from './components/IterationChatModal'

// State (substituir showAddIteration)
const [showIterationChat, setShowIterationChat] = useState(false)

// Keyboard shortcut (modificar 'i')
if ((e.key === 'i' || e.key === 'I') && selectedProject && wsState.agentStatus !== 'running') {
  e.preventDefault()
  setShowIterationChat(true)  // em vez de setShowAddIteration
}

// Modal render (substituir AddIterationModal)
{showIterationChat && selectedProject && (
  <IterationChatModal
    isOpen={showIterationChat}
    projectName={selectedProject}
    onClose={() => setShowIterationChat(false)}
    onComplete={(metadata) => {
      console.log('Iteration created:', metadata)
      // Refresh features list
      queryClient.invalidateQueries({ queryKey: ['features', selectedProject] })
    }}
  />
)}
```

---

### 2.5 Modificar `ui/src/components/KanbanColumn.tsx`

**Mudar handler:**

```typescript
// Em vez de onAddIteration={() => setShowAddIteration(true)}
// Usar: onAddIteration={() => setShowIterationChat(true)}
```

---

## PARTE 3: Skill Update

### 3.1 Modificar `.claude/commands/brownfield-iteration.md`

**Adicionar nota no início:**

```markdown
---
description: Create a new iteration for brownfield project expansion
---

**NOTE:** This skill can be used in two modes:
1. **CLI Mode** - Via `/brownfield-iteration` command (direct invocation)
2. **Chat Mode** - Via Iteration Chat interface (WebSocket session)

In Chat Mode, focus on understanding user needs through conversation.
At the end, they'll click "Complete Iteration" which calls your final output as instructions.
```

---

## PARTE 4: Build e Testes

### 4.1 Build

```bash
# Frontend
cd ui
npm run build

# Backend (verify imports)
python -c "from server.services.iteration_chat_session import IterationChatSession; print('OK')"
python -c "from server.routers.iteration import router; print('OK')"
```

### 4.2 Teste Fluxo Completo

1. **Iniciar servidor**
   ```bash
   ./start_ui.sh
   ```

2. **Selecionar projeto brownfield**

3. **Clicar botão GitBranch (🌿) ou pressionar 'i'**
   - Modal full-screen abre
   - Chat iniciado
   - Claude pergunta o que quer adicionar

4. **Conversar**
   - "Quero adicionar autenticação de usuários"
   - Claude faz perguntas
   - "Sim, com JWT e recuperação de senha"
   - Etc.

5. **Clicar "Complete Iteration"**
   - Confirmação dialog
   - Confirmar
   - Backups criados
   - Tela de sucesso com metadata

6. **Fechar e rodar agent**
   ```bash
   python autonomous_agent_demo.py --project-dir nome-projeto
   ```
   - Agent detecta iteration_vN_instructions.md
   - Processa iteração

---

## RESULTADO FINAL

### Comparação dos 3 Fluxos

| Feature | Add Feature | Expand Project | **Add Iteration Chat** |
|---------|-------------|----------------|----------------------|
| **Interface** | Form | Chat | **Chat** |
| **Interativo** | ❌ | ✅ | **✅** |
| **Backups** | ❌ | ❌ | **✅** |
| **Versionamento** | ❌ | ❌ | **✅** |
| **Spec atualizado** | ❌ | ❌ | **✅** |
| **Features via** | Manual | Direto DB | **Initializer** |
| **Qualidade** | Variável | Variável | **Consistente** |
| **Rollback** | ❌ | ❌ | **✅** |

**Add Iteration Chat = Melhor dos dois mundos!**

---

## VALIDAÇÃO

### Checklist Backend
- [ ] `iteration_chat_session.py` criado
- [ ] `iteration.py` router criado
- [ ] Router registrado em `main.py`
- [ ] Endpoints funcionam
- [ ] WebSocket conecta
- [ ] `complete_iteration()` chama `iteration_manager`

### Checklist Frontend
- [ ] `useIterationChat.ts` criado
- [ ] `IterationChat.tsx` criado
- [ ] `IterationChatModal.tsx` criado
- [ ] App.tsx atualizado
- [ ] Build sem erros
- [ ] Modal abre
- [ ] Chat funciona
- [ ] Complete cria backups

---

**Status:** PRONTO PARA IMPLEMENTAÇÃO 🚀

**Próximo:** Nenhum - Sistema completo com 3 métodos de expansão!