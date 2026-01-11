---
description: Automate iteration completion via MCP tool instead of manual button
---

# OBJETIVO

Transformar "Complete Iteration" de um **botão manual** para uma **ferramenta MCP** que Claude chama autonomamente quando o planejamento está completo, seguindo o padrão do Expand Project.

**Motivação:**
- ✅ Consistência: Expand Project já funciona assim (Claude cria features via MCP)
- ✅ UX melhor: Claude sabe quando está pronto, não o usuário
- ✅ Fluxo natural: Claude pergunta confirmação e finaliza automaticamente

---

# CONTEXTO ATUAL

## Fluxo Atual (Manual)
```
Usuário clica 🌿 → Chat abre → Conversa → [Usuário clica "Complete Iteration"] → Backups criados
```

**Problemas:**
1. Usuário precisa decidir quando está "pronto" (deveria ser Claude)
2. Botão sempre visível (mesmo quando não faz sentido)
3. Inconsistente com Expand Project

## Fluxo Desejado (Automático)
```
Usuário clica 🌿 → Chat abre → Conversa → Claude: "Posso finalizar?" → Usuário: "Sim" →
Claude chama ferramenta MCP → Backups criados → Mensagem de sucesso no chat
```

**Vantagens:**
1. Claude controla o fluxo (como Expand Project)
2. Confirmação natural na conversa
3. UI mais limpa (sem botão manual)

---

# ARQUITETURA

## Backend Changes

### 1. Criar Ferramenta MCP: `iteration_complete`

**Arquivo:** `mcp_server/iteration_mcp.py` (novo ou expandir existente)

```python
"""
Iteration MCP Server
====================

MCP tools for Claude to manage brownfield iterations autonomously.
Similar to feature_mcp.py but for iteration lifecycle.
"""

from typing import Any
from pathlib import Path
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logger = logging.getLogger(__name__)

# Global state (passed via environment or init)
_project_dir: Path | None = None
_session_callback: callable | None = None  # Callback to iteration_chat_session


def set_iteration_context(project_dir: Path, session_callback: callable):
    """
    Set context for iteration operations.

    Args:
        project_dir: Project directory path
        session_callback: Function to call complete_iteration() on the session
    """
    global _project_dir, _session_callback
    _project_dir = project_dir
    _session_callback = session_callback


async def handle_iteration_complete(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Complete iteration planning and create backups.

    Claude calls this when iteration planning is finished.

    Arguments:
        instructions: Structured iteration instructions (markdown format)
        summary: Brief summary of changes (for logging/display)

    Returns:
        Success message with backup locations and version info
    """
    if not _project_dir or not _session_callback:
        return [TextContent(
            type="text",
            text="ERROR: Iteration context not initialized"
        )]

    instructions = arguments.get("instructions", "")
    summary = arguments.get("summary", "No summary provided")

    if not instructions:
        return [TextContent(
            type="text",
            text="ERROR: Instructions cannot be empty"
        )]

    try:
        # Call the session's complete_iteration method
        metadata = await _session_callback(instructions)

        # Format success message
        result = f"""✅ **Iteration Completed Successfully!**

**Version:** v{metadata['version']}
**Backups Created:**
- Spec: `{metadata['spec_backup']}`
- Database: `{metadata['db_backup']}`
- Instructions: `{metadata['instructions_file']}`

**Stats:**
- Existing Features: {metadata['feature_count']}
- Next Priority: {metadata['next_priority']}

**Next Steps:**
1. Close this chat
2. Click the ▶️ Play button
3. The Initializer Agent will process this iteration
4. New features will be created automatically

**Summary of Changes:**
{summary}
"""

        return [TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Failed to complete iteration: {e}")
        return [TextContent(
            type="text",
            text=f"ERROR: Failed to complete iteration: {str(e)}"
        )]


# MCP Server setup
app = Server("iteration-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available iteration tools."""
    return [
        Tool(
            name="iteration_complete",
            description="""Complete the iteration planning and create versioned backups.

Call this tool when you have finished discussing the iteration with the user and are ready to finalize it.

This will:
1. Create versioned backups (spec + database)
2. Save iteration instructions to a file
3. Prepare the project for the Initializer Agent

Always ask for user confirmation before calling this tool.

Arguments:
- instructions (required): Detailed markdown-formatted instructions for the iteration, including:
  * What to add/change
  * Specific features to implement
  * Any technical requirements
  * Priority ordering
- summary (required): Brief 1-2 sentence summary of the changes for logging
""",
            inputSchema={
                "type": "object",
                "properties": {
                    "instructions": {
                        "type": "string",
                        "description": "Detailed iteration instructions in markdown format"
                    },
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of changes (1-2 sentences)"
                    }
                },
                "required": ["instructions", "summary"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    if name == "iteration_complete":
        return await handle_iteration_complete(arguments)
    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]


async def main():
    """Run MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
```

---

### 2. Integrar MCP no `iteration_chat_session.py`

**Modificações:**

```python
class IterationChatSession:
    def __init__(self, project_name: str, project_dir: Path):
        # ... existing code ...
        self._mcp_server_process = None  # Track MCP server process

    async def start(self) -> AsyncGenerator[dict, None]:
        # ... existing code ...

        # Start MCP server for iteration tools
        mcp_server = await self._start_mcp_server()

        # Initialize client WITH iteration MCP server
        self.client = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model="claude-sonnet-4-5-20250929",
                cli_path=system_cli,
                system_prompt=system_prompt,
                allowed_tools=["Read", "Glob"],
                permission_mode="acceptEdits",
                max_turns=50,
                cwd=str(self.project_dir.resolve()),
                settings=str(settings_file.resolve()) if settings_file.exists() else None,
                mcp_servers=[mcp_server],  # ADD THIS
            )
        )

        # ... rest of existing code ...

    async def _start_mcp_server(self):
        """Start iteration MCP server with context."""
        import subprocess
        import sys

        # Start MCP server as subprocess
        mcp_script = Path(__file__).parent.parent.parent / "mcp_server" / "iteration_mcp.py"

        self._mcp_server_process = subprocess.Popen(
            [sys.executable, str(mcp_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Set context via environment or initial message
        # (depends on how MCP server receives context)

        return {
            "name": "iteration-tools",
            "process": self._mcp_server_process
        }

    async def mcp_complete_iteration(self, instructions: str) -> dict:
        """
        Callback for MCP tool to complete iteration.

        Called by the iteration_complete MCP tool.
        """
        return await self.complete_iteration(instructions)

    async def disconnect(self):
        """Disconnect Claude client and MCP server."""
        if self.client:
            self.client = None

        if self._mcp_server_process:
            self._mcp_server_process.terminate()
            self._mcp_server_process.wait()
```

---

### 3. Atualizar System Prompt

**Em `iteration_chat_session.py`, modificar system_prompt:**

```python
system_prompt = f"""You are helping plan an iteration for project: {self.project_name}

Current State:
- Features in database: {feature_count}
- Project directory: {self.project_dir}

Project Specification (first 20 lines):
{spec_summary}

Your goal: Understand what the user wants to add/change through conversation.

**IMPORTANT - Iteration Completion Flow:**
1. Discuss the iteration with the user, clarifying requirements
2. When you have enough information, present a summary of what will be done
3. Ask: "Should I finalize this iteration?"
4. If user confirms, call the `iteration_complete` tool with:
   - Detailed markdown instructions
   - Brief summary of changes
5. The tool will create backups and prepare the project

**You have access to:**
- `iteration_complete` tool - Call this when planning is finished and user confirms

Remember: You will NOT create features directly. The Initializer Agent processes the iteration file later.

Start by greeting the user and asking what they want to add to this iteration.
"""
```

---

## Frontend Changes

### 4. Remover Botão Manual

**Arquivo:** `ui/src/components/IterationChat.tsx`

**Remover:**
```tsx
// REMOVER ESTAS LINHAS:
const [showCompleteDialog, setShowCompleteDialog] = useState(false)
const [finalInstructions, setFinalInstructions] = useState('')

const handleCompleteClick = () => { ... }
const handleConfirmComplete = async () => { ... }

// REMOVER DO JSX:
{messages.length > 2 && connectionStatus === 'connected' && (
  <button onClick={handleCompleteClick} ...>
    Complete Iteration
  </button>
)}

// REMOVER TODO O DIALOG:
{showCompleteDialog && ( ... )}
```

**Manter apenas:**
- Chat de mensagens
- Input para enviar mensagens
- Botão de fechar (X)
- Connection status

---

### 5. Adicionar Handler para Sucesso

**Modificar `useIterationChat.ts`:**

```typescript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data)

  if (data.type === 'message') {
    setMessages(prev => [...prev, {
      role: data.role,
      content: data.content,
      timestamp: new Date().toISOString()
    }])
    setIsLoading(false)

    // Detectar conclusão via mensagem do Claude
    if (data.content.includes('✅ **Iteration Completed Successfully!**')) {
      // Parse metadata da mensagem se necessário
      setIsComplete(true)
      // Extrair metadata do texto ou fazer chamada adicional
      // onComplete(metadata) será chamado quando fechar
    }
  }
  // ... resto do código
}
```

**OU adicionar novo tipo de mensagem no backend:**

```python
# No iteration_mcp.py, após sucesso:
yield {
    "type": "iteration_complete",
    "metadata": metadata
}

# No frontend:
else if (data.type === 'iteration_complete') {
  setIterationMetadata(data.metadata)
  setIsComplete(true)
  onComplete(data.metadata)
}
```

---

### 6. Tela de Sucesso Simplificada

**Modificar `IterationChat.tsx` - Completion view:**

```tsx
// Completion view (triggered by isComplete=true)
if (isComplete && iterationMetadata) {
  return (
    <div className="flex flex-col h-full bg-white">
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-2xl">
          <CheckCircle2 size={64} className="mx-auto mb-6 text-green-600" />
          <h2 className="font-display text-3xl font-bold mb-4">
            Iteration Ready!
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
            </ul>
          </div>

          <div className="bg-blue-50 border-3 border-blue-600 p-4 mb-6 text-left">
            <p className="font-bold mb-2">Next Steps:</p>
            <ol className="list-decimal list-inside space-y-1 text-sm">
              <li>Close this dialog</li>
              <li>Click ▶️ Play to start the agent</li>
              <li>Agent will process the iteration automatically</li>
            </ol>
          </div>

          <button
            onClick={() => onComplete(iterationMetadata)}
            className="neo-btn neo-btn-primary text-lg px-8 py-3"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
```

---

## Fluxo Completo (Novo)

```
1. User clicks 🌿 GitBranch
   ↓
2. POST /api/iteration/sessions/{project}/start
   - Creates session
   - Starts MCP server with iteration_complete tool
   ↓
3. WebSocket /api/iteration/ws/{project} connects
   - Claude client initialized with MCP
   ↓
4. User: "I want to add authentication"
   ↓
5. Claude: [asks clarifying questions]
   ↓
6. Claude: "Got it! I'll add:
            - Login/logout
            - JWT tokens
            - Password reset
            Should I finalize this iteration?"
   ↓
7. User: "Yes"
   ↓
8. Claude calls iteration_complete tool with instructions
   ↓
9. MCP tool calls session.complete_iteration()
   - Creates backups
   - Generates iteration_v2_instructions.md
   ↓
10. Claude: "✅ Iteration v2 created! [details]"
    ↓
11. Frontend detects completion → Shows success screen
    ↓
12. User closes → Features query refreshed
    ↓
13. User clicks ▶️ Play
    ↓
14. Agent runs, finds iteration_v2_instructions.md
    ↓
15. Initializer Agent processes → Creates features
```

---

## Comparação: Antes vs Depois

### ANTES (Manual)
```
Conversa → [Usuário clica botão] → Popup confirmação → Cria backups
```
**Problemas:** Usuário decide, botão sempre visível, interrompe fluxo

### DEPOIS (Automático)
```
Conversa → Claude: "Posso finalizar?" → User: "Sim" → Claude chama tool → Backups criados
```
**Vantagens:** Claude decide, sem popup, fluxo natural

---

## TESTES

### 1. Backend - MCP Tool
```bash
# Test MCP server directly
python mcp_server/iteration_mcp.py

# Test with client
python -c "
from server.services.iteration_chat_session import create_iteration_session
from pathlib import Path

session = create_iteration_session('test', Path('/path/to/project'))
# Verify MCP server started
# Verify tools available
"
```

### 2. Frontend - Chat Flow
```
1. Open iteration chat
2. Type: "Add user profiles"
3. Claude asks questions
4. Claude asks: "Should I finalize?"
5. Type: "Yes"
6. Verify: Success screen appears
7. Verify: Backups created in project dir
```

### 3. Integration - Full Flow
```
1. Create iteration via chat
2. Close chat
3. Click Play button
4. Verify: Agent finds iteration_vN_instructions.md
5. Verify: Agent creates features
6. Verify: Features appear in Pending column
```

---

## ROLLBACK

Se precisar reverter:

```bash
# 1. Restore IterationChat.tsx
git checkout ui/src/components/IterationChat.tsx

# 2. Restore iteration_chat_session.py
git checkout server/services/iteration_chat_session.py

# 3. Remove MCP server
rm mcp_server/iteration_mcp.py
```

---

## RESULTADO ESPERADO

**Experiência do Usuário:**

1. Abre chat
2. Conversa naturalmente com Claude
3. Claude: "Posso finalizar a iteração?"
4. User: "Sim"
5. Claude: "✅ Criado! Versão v2, backups em..."
6. Fecha chat
7. Clica Play
8. Features criadas automaticamente

**Sem botões manuais. Sem popups. Fluxo conversacional natural.**

---

**Status:** PRONTO PARA IMPLEMENTAÇÃO 🚀

**Complexidade:** MÉDIA
- Backend: Criar MCP server + integrar
- Frontend: Remover botão + simplificar UI

**Tempo estimado:** 2-3 horas

**Prioridade:** ALTA (melhora significativa de UX)