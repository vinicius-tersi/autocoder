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
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from dotenv import load_dotenv

from ..schemas import ImageAttachment

load_dotenv()

logger = logging.getLogger(__name__)


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
        self._mcp_server_process = None

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

        # Create system prompt
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

        # Get system CLI path
        system_cli = os.getenv("CLI_COMMAND", "claude")

        # Get settings file
        settings_file = Path.home() / ".claude" / "settings.json"

        # Start MCP server for iteration tools
        await self._start_mcp_server()

        # Build MCP servers config
        mcp_servers = {}
        if self._mcp_server_process:
            mcp_servers["iteration-tools"] = {
                "command": sys.executable,
                "args": [str(Path(__file__).parent.parent.parent / "mcp_server" / "iteration_mcp.py")],
                "env": {
                    **os.environ,
                    "PROJECT_DIR": str(self.project_dir.resolve()),
                }
            }

        # Initialize client (similar to expand_chat_session)
        try:
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
                    mcp_servers=mcp_servers if mcp_servers else None,
                )
            )
            await self.client.__aenter__()

        except Exception as e:
            logger.error(f"Failed to create Claude client: {e}")
            yield {
                "type": "error",
                "content": "Failed to initialize Claude client"
            }
            return

        yield {
            "type": "status",
            "content": "Session started"
        }

        # Send initial greeting request and get first response
        try:
            await self.client.query("Hello! I'd like to plan a new iteration for this project.")

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
            logger.error(f"Error starting iteration session: {e}")
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
            logger.error(f"Error sending message: {e}")
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

            logger.info(f"Iteration created: v{metadata['version']} for {self.project_name}")

            return metadata
        except Exception as e:
            logger.error(f"Failed to create iteration: {e}")
            raise

    async def _start_mcp_server(self):
        """Start the iteration MCP server process."""
        try:
            # Mark that server should start (actual process is started by Claude SDK)
            self._mcp_server_process = True
            logger.info(f"MCP server configured for project: {self.project_name}")
        except Exception as e:
            logger.error(f"Failed to configure MCP server: {e}")
            self._mcp_server_process = None

    async def disconnect(self):
        """Disconnect Claude client and cleanup MCP server."""
        if self.client:
            # ClaudeSDKClient cleanup (if needed)
            self.client = None

        self._mcp_server_process = None


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