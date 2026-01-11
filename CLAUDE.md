# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an autonomous coding agent system with a React-based UI. It uses the Claude Agent SDK to build complete applications over multiple sessions using a two-agent pattern:

1. **Initializer Agent** - First session reads an app spec and creates features in a SQLite database
2. **Coding Agent** - Subsequent sessions implement features one by one, marking them as passing

## Commands

### Quick Start (Recommended)

```bash
# Windows - launches CLI menu
start.bat

# macOS/Linux
./start.sh

# Launch Web UI (serves pre-built React app)
start_ui.bat      # Windows
./start_ui.sh     # macOS/Linux
```

### Python Backend (Manual)

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the main CLI launcher
python start.py

# Run agent directly for a project (use absolute path or registered name)
python autonomous_agent_demo.py --project-dir C:/Projects/my-app
python autonomous_agent_demo.py --project-dir my-app  # if registered

# YOLO mode: rapid prototyping without browser testing
python autonomous_agent_demo.py --project-dir my-app --yolo
```

### YOLO Mode (Rapid Prototyping)

YOLO mode skips all testing for faster feature iteration:

```bash
# CLI
python autonomous_agent_demo.py --project-dir my-app --yolo

# UI: Toggle the lightning bolt button before starting the agent
```

**What's different in YOLO mode:**
- No regression testing (skips `feature_get_for_regression`)
- No Playwright MCP server (browser automation disabled)
- Features marked passing after lint/type-check succeeds
- Faster iteration for prototyping

**What's the same:**
- Lint and type-check still run to verify code compiles
- Feature MCP server for tracking progress
- All other development tools available

**When to use:** Early prototyping when you want to quickly scaffold features without verification overhead. Switch back to standard mode for production-quality development.

### React UI (in ui/ directory)

```bash
cd ui
npm install
npm run dev      # Development server (hot reload)
npm run build    # Production build (required for start_ui.bat)
npm run lint     # Run ESLint
```

**Note:** The `start_ui.bat` script serves the pre-built UI from `ui/dist/`. After making UI changes, run `npm run build` in the `ui/` directory.

## Architecture

### Core Python Modules

- `start.py` - CLI launcher with project creation/selection menu
- `autonomous_agent_demo.py` - Entry point for running the agent
- `agent.py` - Agent session loop using Claude Agent SDK
- `client.py` - ClaudeSDKClient configuration with security hooks and MCP servers
- `security.py` - Bash command allowlist validation (ALLOWED_COMMANDS whitelist)
- `prompts.py` - Prompt template loading with project-specific fallback
- `progress.py` - Progress tracking, database queries, webhook notifications
- `registry.py` - Project registry for mapping names to paths (cross-platform)

### Project Registry

Projects can be stored in any directory. The registry maps project names to paths using SQLite:
- **All platforms**: `~/.autocoder/registry.db`

The registry uses:
- SQLite database with SQLAlchemy ORM
- POSIX path format (forward slashes) for cross-platform compatibility
- SQLite's built-in transaction handling for concurrency safety

### Server API (server/)

The FastAPI server provides REST endpoints for the UI:

- `server/routers/projects.py` - Project CRUD with registry integration
- `server/routers/features.py` - Feature management
- `server/routers/agent.py` - Agent control (start/stop/pause/resume)
- `server/routers/filesystem.py` - Filesystem browser API with security controls
- `server/routers/spec_creation.py` - WebSocket for interactive spec creation
- `server/routers/iteration.py` - WebSocket for brownfield iteration planning

### Feature Management

Features are stored in SQLite (`features.db`) via SQLAlchemy. The agent interacts with features through an MCP server:

- `mcp_server/feature_mcp.py` - MCP server exposing feature management tools
- `api/database.py` - SQLAlchemy models (Feature table with priority, category, name, description, steps, passes)

MCP tools available to the agent:
- `feature_get_stats` - Progress statistics
- `feature_get_next` - Get highest-priority pending feature
- `feature_get_for_regression` - Random passing features for regression testing
- `feature_mark_passing` - Mark feature complete
- `feature_skip` - Move feature to end of queue
- `feature_create_bulk` - Initialize all features (used by initializer)

### Brownfield Development & Iterations

The system supports expanding existing projects through **iterations** - a versioned approach to adding new features to brownfield codebases.

**Project Types:**
- **Greenfield**: New project with no features yet (initial implementation)
- **Brownfield**: Existing project with features already implemented (expansion mode)

**Iteration System Files:**

- `server/services/iteration_manager.py` - Core iteration management logic
  - `detect_project_type()` - Auto-detects greenfield vs brownfield
  - `create_iteration()` - Creates versioned backups and iteration instructions
  - `cancel_iteration()` - Cancels active iteration and removes its features
  - `get_active_iteration()` - Checks for pending iterations

- `server/services/iteration_chat_session.py` - Interactive iteration planning session
  - Conversational interface for planning project expansions
  - Integrates with iteration MCP server
  - Creates iteration files when planning is complete

- `mcp_server/iteration_mcp.py` - MCP server for autonomous iteration completion
  - `iteration_complete` tool - Called by Claude when iteration planning is finished
  - Eliminates manual "Complete" button - Claude controls the flow
  - Returns metadata (version, backups, next steps)

**Iteration Workflow:**

1. User clicks 🌿 GitBranch button in UI (for brownfield projects)
2. Chat opens via WebSocket (`/api/iteration/ws/{project_name}`)
3. Claude asks questions to understand expansion requirements
4. User describes what they want to add through natural conversation
5. When ready, Claude asks: "Should I finalize this iteration?"
6. User confirms: "Yes"
7. **Claude autonomously calls `iteration_complete` MCP tool** with:
   - Detailed markdown instructions
   - Brief summary of changes
8. Iteration system creates:
   - Versioned spec backup: `prompts/app_spec.txt.v{N}`
   - Versioned database backup: `features.db.v{N}`
   - Iteration instructions: `prompts/iteration_v{N}_instructions.md`
   - Metadata file: `prompts/iteration_v{N}_metadata.json`
9. UI shows completion screen with metadata
10. User closes chat and clicks ▶️ Play
11. Initializer Agent processes iteration file and creates new features

**Key Design: Autonomous Completion via MCP Tool**

Unlike manual button-based flows, iteration completion is **tool-driven**:
- No "Complete Iteration" button in the UI
- Claude decides when planning is complete (not the user)
- Natural conversational flow with confirmation
- Consistent with Expand Project pattern
- Better UX - Claude knows when it has enough information

**Versioning System:**

Each iteration gets a sequential version number (v1, v2, v3...):
- Backups preserve project state before expansion
- Instructions guide Initializer Agent on what to add
- Metadata tracks iteration status (active/cancelled/completed)
- Priority values ensure new features append after existing ones

**Iteration Instructions Format:**

```markdown
# Iteration v{N} Instructions

**Project Type:** brownfield
**Date:** [ISO timestamp]
**Previous Spec Backup:** app_spec.txt.v{N}
**Previous DB Backup:** features.db.v{N}

## Expansion Requirements
[User's requirements from chat conversation]

## Instructions for Initializer Agent
1. Read PREVIOUS spec to understand existing features
2. Update CURRENT app_spec.txt (preserve + add new)
3. Create ONLY NEW features via feature_create_bulk
4. Set priority starting from {next_priority}
5. DO NOT recreate project structure or overwrite code
```

**Cancellation Support:**

Active iterations can be cancelled via UI:
- Removes all features created in that iteration (by priority range)
- Optionally restores backups (spec + database)
- Updates iteration metadata to "cancelled" status
- Triggered by X button on iteration indicator

### React UI (ui/)

- Tech stack: React 18, TypeScript, TanStack Query, Tailwind CSS v4, Radix UI
- `src/App.tsx` - Main app with project selection, kanban board, agent controls
- `src/hooks/useWebSocket.ts` - Real-time updates via WebSocket
- `src/hooks/useProjects.ts` - React Query hooks for API calls
- `src/hooks/useIterationChat.ts` - WebSocket hook for iteration planning chat
- `src/lib/api.ts` - REST API client
- `src/lib/types.ts` - TypeScript type definitions
- `src/components/FolderBrowser.tsx` - Server-side filesystem browser for project folder selection
- `src/components/NewProjectModal.tsx` - Multi-step project creation wizard
- `src/components/IterationChat.tsx` - Conversational iteration planning interface
- `src/components/IterationChatModal.tsx` - Modal wrapper for iteration chat

### Project Structure for Generated Apps

Projects can be stored in any directory (registered in `~/.autocoder/registry.db`). Each project contains:
- `prompts/app_spec.txt` - Application specification (XML format)
- `prompts/initializer_prompt.md` - First session prompt
- `prompts/coding_prompt.md` - Continuation session prompt
- `features.db` - SQLite database with feature test cases
- `.agent.lock` - Lock file to prevent multiple agent instances

### Security Model

Defense-in-depth approach configured in `client.py`:
1. OS-level sandbox for bash commands
2. Filesystem restricted to project directory only
3. Bash commands validated against `ALLOWED_COMMANDS` in `security.py`

## Claude Code Integration

- `.claude/commands/create-spec.md` - `/create-spec` slash command for interactive spec creation
- `.claude/skills/frontend-design/SKILL.md` - Skill for distinctive UI design
- `.claude/templates/` - Prompt templates copied to new projects

## Key Patterns

### Prompt Loading Fallback Chain

1. Project-specific: `{project_dir}/prompts/{name}.md`
2. Base template: `.claude/templates/{name}.template.md`

### Agent Session Flow

1. Check if `features.db` has features (determines initializer vs coding agent)
2. Create ClaudeSDKClient with security settings
3. Send prompt and stream response
4. Auto-continue with 3-second delay between sessions

### Real-time UI Updates

The UI receives updates via WebSocket (`/ws/projects/{project_name}`):
- `progress` - Test pass counts
- `agent_status` - Running/paused/stopped/crashed
- `log` - Agent output lines (streamed from subprocess stdout)
- `feature_update` - Feature status changes

### Design System

The UI uses a **neobrutalism** design with Tailwind CSS v4:
- CSS variables defined in `ui/src/styles/globals.css` via `@theme` directive
- Custom animations: `animate-slide-in`, `animate-pulse-neo`, `animate-shimmer`
- Color tokens: `--color-neo-pending` (yellow), `--color-neo-progress` (cyan), `--color-neo-done` (green)
