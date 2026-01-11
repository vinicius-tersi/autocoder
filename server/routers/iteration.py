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
    logger.info(f"[ITERATION START] Starting session for project: {project_name}")
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
    logger.info(f"[ITERATION START] Session created with ID: {session.session_id}")

    # Verify session was stored
    stored_session = get_iteration_session(project_name)
    logger.info(f"[ITERATION START] Session verification: {stored_session is not None}")

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


@router.get("/active/{project_name}")
async def get_active_iteration_endpoint(project_name: str):
    """
    Get the active iteration for a project.

    Returns:
        Iteration metadata if active iteration exists, None otherwise
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir or not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from server.services.iteration_manager import get_active_iteration

    active_iteration = get_active_iteration(project_dir)

    if active_iteration is None:
        return {"active": False}

    return {
        "active": True,
        "iteration": active_iteration
    }


@router.post("/cancel")
async def cancel_iteration_endpoint(request: dict):
    """
    Cancel an active iteration and remove its features.

    Body:
        project_name: Name of the project
        version: Iteration version to cancel
        restore_backups: (optional) Whether to restore backups (default: False)
    """
    project_name = validate_project_name(request.get("project_name", ""))
    version = request.get("version")
    restore_backups = request.get("restore_backups", False)

    if not version:
        raise HTTPException(status_code=400, detail="version is required")

    project_dir = _get_project_path(project_name)

    if not project_dir or not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from server.services.iteration_manager import cancel_iteration

    try:
        result = await cancel_iteration(project_dir, version, restore_backups)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/ws/{project_name}")
async def iteration_websocket(websocket: WebSocket, project_name: str):
    """
    WebSocket endpoint for iteration planning chat.

    Similar to expand project WebSocket but uses iteration_chat_session.
    """
    logger.info(f"[ITERATION WS] Connection attempt for project: {project_name}")

    # Validate BEFORE accepting the WebSocket
    try:
        project_name = validate_project_name(project_name)
        logger.info(f"[ITERATION WS] Project name validated: {project_name}")
    except Exception as e:
        logger.error(f"[ITERATION WS] Invalid project name: {e}")
        await websocket.close(code=4000, reason=f"Invalid project name: {e}")
        return

    session = get_iteration_session(project_name)
    logger.info(f"[ITERATION WS] Session lookup result: {session is not None}")

    if not session:
        logger.error(f"[ITERATION WS] No active session for {project_name}")
        await websocket.close(code=4004, reason="No active iteration session")
        return

    # Accept WebSocket AFTER validations pass
    logger.info(f"[ITERATION WS] Accepting WebSocket connection for {project_name}")
    await websocket.accept()

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