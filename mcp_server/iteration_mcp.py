"""
Iteration MCP Server
====================

MCP tools for Claude to manage brownfield iterations autonomously.
Similar to feature_mcp.py but for iteration lifecycle.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state (passed via environment)
_project_dir: Path | None = None


def get_project_dir() -> Path:
    """Get project directory from environment."""
    global _project_dir
    if _project_dir is None:
        project_dir_str = os.getenv("PROJECT_DIR", ".")
        _project_dir = Path(project_dir_str)
    return _project_dir


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
    project_dir = get_project_dir()

    instructions = arguments.get("instructions", "")
    summary = arguments.get("summary", "No summary provided")

    if not instructions:
        return [TextContent(
            type="text",
            text="ERROR: Instructions cannot be empty"
        )]

    try:
        logger.info(f"Completing iteration for project: {project_dir}")
        logger.info(f"Summary: {summary}")

        # Import iteration manager
        root = Path(__file__).parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        from server.services.iteration_manager import create_iteration

        # Create iteration
        metadata = await create_iteration(project_dir, instructions)

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
        logger.error(f"Failed to complete iteration: {e}", exc_info=True)
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
    logger.info("Starting Iteration MCP Server")
    logger.info(f"Project directory: {get_project_dir()}")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())