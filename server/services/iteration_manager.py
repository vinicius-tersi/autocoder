"""
Iteration Manager
=================

Manages project iterations for brownfield development.
Provides versioning, backups, and iteration instructions for expanding existing projects.
"""

import sqlite3
from datetime import datetime
from pathlib import Path


def detect_project_type(project_dir: Path) -> str:
    """
    Detect if a project is greenfield (new) or brownfield (existing).

    Args:
        project_dir: Path to the project directory

    Returns:
        "greenfield" or "brownfield"

    Detection criteria:
        1. Check if features.db exists and has features -> brownfield
        2. Check if source code directories exist (src/, client/, server/) -> brownfield
        3. Check if git history exists -> brownfield
        4. Default: greenfield
    """
    # Check 1: features.db exists and has features
    features_db = project_dir / "features.db"
    if features_db.exists():
        try:
            conn = sqlite3.connect(str(features_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM features")
            count = cursor.fetchone()[0]
            conn.close()
            if count > 0:
                return "brownfield"
        except (sqlite3.Error, TypeError):
            pass

    # Check 2: Source code directories exist
    source_dirs = ["src", "client", "server", "app", "lib"]
    for dir_name in source_dirs:
        if (project_dir / dir_name).is_dir():
            # Check if directory has actual files
            try:
                if any((project_dir / dir_name).iterdir()):
                    return "brownfield"
            except PermissionError:
                pass

    # Check 3: Git history exists
    git_dir = project_dir / ".git"
    if git_dir.is_dir():
        # Check if there are commits
        refs_dir = git_dir / "refs" / "heads"
        if refs_dir.exists():
            try:
                if any(refs_dir.iterdir()):
                    return "brownfield"
            except PermissionError:
                pass

    # Default: greenfield
    return "greenfield"


def get_next_spec_version(project_dir: Path) -> int:
    """
    Get the next version number for app_spec.txt backup.

    Args:
        project_dir: Path to the project directory

    Returns:
        Next version number (1, 2, 3, etc.)
    """
    prompts_dir = project_dir / "prompts"
    if not prompts_dir.exists():
        return 1

    # Find existing backups: app_spec.txt.v1, app_spec.txt.v2, etc.
    existing_versions = []
    for file in prompts_dir.glob("app_spec.txt.v*"):
        try:
            version_str = file.suffix.lstrip(".v")
            version = int(version_str)
            existing_versions.append(version)
        except ValueError:
            continue

    if not existing_versions:
        return 1

    return max(existing_versions) + 1


def backup_app_spec(project_dir: Path) -> tuple[int, Path]:
    """
    Create a versioned backup of app_spec.txt.

    Args:
        project_dir: Path to the project directory

    Returns:
        Tuple of (version_number, backup_path)

    The backup includes XML metadata at the top:
        <!--
          BACKUP METADATA
          ===============
          Original: app_spec.txt
          Version: vN
          Backed up: [timestamp ISO]
          Project Type: [greenfield|brownfield]
        -->
    """
    prompts_dir = project_dir / "prompts"
    app_spec_file = prompts_dir / "app_spec.txt"

    version = get_next_spec_version(project_dir)
    backup_path = prompts_dir / f"app_spec.txt.v{version}"

    # Read original content
    original_content = ""
    if app_spec_file.exists():
        original_content = app_spec_file.read_text(encoding="utf-8")

    # Detect project type
    project_type = detect_project_type(project_dir)

    # Create metadata header
    timestamp = datetime.now().isoformat()
    metadata = f"""<!--
  BACKUP METADATA
  ===============
  Original: app_spec.txt
  Version: v{version}
  Backed up: {timestamp}
  Project Type: {project_type}
-->

"""

    # Write backup with metadata
    backup_content = metadata + original_content
    backup_path.write_text(backup_content, encoding="utf-8")

    return version, backup_path


def backup_database(project_dir: Path, version: int) -> Path:
    """
    Create a versioned backup of features.db.

    Args:
        project_dir: Path to the project directory
        version: Version number to use for the backup

    Returns:
        Path to the backup file
    """
    import shutil

    features_db = project_dir / "features.db"
    backup_path = project_dir / f"features.db.v{version}"

    if features_db.exists():
        shutil.copy2(str(features_db), str(backup_path))

    return backup_path


def get_existing_feature_count(project_dir: Path) -> int:
    """
    Count the number of features in the project's database.

    Args:
        project_dir: Path to the project directory

    Returns:
        Number of features, or 0 if database doesn't exist
    """
    features_db = project_dir / "features.db"
    if not features_db.exists():
        return 0

    try:
        conn = sqlite3.connect(str(features_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM features")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except (sqlite3.Error, TypeError):
        return 0


def get_next_priority(project_dir: Path) -> int:
    """
    Get the next priority value for new features.

    Args:
        project_dir: Path to the project directory

    Returns:
        MAX(priority) + 1, or 1 if database is empty
    """
    features_db = project_dir / "features.db"
    if not features_db.exists():
        return 1

    try:
        conn = sqlite3.connect(str(features_db))
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(priority) FROM features")
        result = cursor.fetchone()[0]
        conn.close()
        if result is None:
            return 1
        return result + 1
    except (sqlite3.Error, TypeError):
        return 1


async def create_iteration(project_dir: Path, instructions: str) -> dict:
    """
    Create a new project iteration.

    This is the main workflow function that:
    1. Detects project type (greenfield/brownfield)
    2. Backs up current app_spec.txt with version number
    3. Backs up current features.db
    4. Creates iteration instructions file for the Initializer Agent

    Args:
        project_dir: Path to the project directory
        instructions: User's expansion requirements

    Returns:
        Dictionary with iteration metadata:
            - version: Iteration version number
            - project_type: "greenfield" or "brownfield"
            - spec_backup: Path to spec backup
            - db_backup: Path to database backup
            - instructions_file: Path to iteration instructions
            - feature_count: Current feature count
            - next_priority: Starting priority for new features
    """
    # Step 1: Detect project type
    project_type = detect_project_type(project_dir)

    # Step 2: Backup app_spec.txt
    version, spec_backup = backup_app_spec(project_dir)

    # Step 3: Backup features.db
    db_backup = backup_database(project_dir, version)

    # Step 4: Get context for instructions
    feature_count = get_existing_feature_count(project_dir)
    next_priority = get_next_priority(project_dir)

    # Step 5: Create iteration instructions file
    prompts_dir = project_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    instructions_file = prompts_dir / f"iteration_v{version}_instructions.md"

    timestamp = datetime.now().isoformat()

    instructions_content = f"""# Iteration v{version} Instructions

**Project Type:** {project_type}
**Date:** {timestamp}
**Previous Spec Backup:** app_spec.txt.v{version}
**Previous DB Backup:** features.db.v{version}

## Expansion Requirements

{instructions}

---

## Instructions for Initializer Agent

You are expanding an existing project (brownfield).

**CRITICAL STEPS:**

1. **Read the PREVIOUS spec:** Read `prompts/app_spec.txt.v{version}` to understand what already exists

2. **Read the CURRENT database:**
   - Use `feature_get_stats` to see existing feature count
   - This project has {feature_count} features already implemented

3. **Edit app_spec.txt:** Update the CURRENT `prompts/app_spec.txt` to include:
   - All previous features (preserve them)
   - New features based on the expansion requirements above
   - Update total feature count

4. **Create ONLY NEW features:** When calling `feature_create_bulk`:
   - Create ONLY the new features (not the old ones)
   - They will be ADDED to the existing database
   - Set priority starting from {next_priority}

5. **DO NOT recreate project structure:**
   - DO NOT overwrite existing source code
   - DO NOT recreate init.sh, README.md
   - ONLY add new feature definitions

6. **Preserve git history:**
   - Commit only the spec changes
   - Message: "Iteration v{version}: [brief description]"
"""

    instructions_file.write_text(instructions_content, encoding="utf-8")

    return {
        "version": version,
        "project_type": project_type,
        "spec_backup": str(spec_backup),
        "db_backup": str(db_backup),
        "instructions_file": str(instructions_file),
        "feature_count": feature_count,
        "next_priority": next_priority,
    }