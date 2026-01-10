---
description: Create backend support for project iterations (brownfield)
order: 1
---

# OBJETIVO

Implementar o suporte backend para iterações de projeto, permitindo expansão incremental de projetos brownfield sem perder o progresso existente.

---

# CONTEXTO

Este é o primeiro passo para suportar projetos brownfield. Vamos criar:
1. Gerenciador de iterações (`iteration_manager.py`)
2. Endpoint de API para iniciar iterações
3. Lógica de detecção de modo iteração no agent

**Referência:** Ver `docs/SESSAO_ANALISE_AUTOCODER.md` seções sobre "Botão Add Iteration" e "Versionamento".

---

# TAREFAS

## 1. Criar `server/services/iteration_manager.py`

Criar arquivo completo com as seguintes funções:

### `detect_project_type(project_dir: Path) -> str`
- Retorna "greenfield" ou "brownfield"
- Critérios:
  1. Checa se `features.db` existe e tem features (brownfield)
  2. Checa se existe código fonte (src/, client/, server/) (brownfield)
  3. Checa se existe histórico git (brownfield)
  4. Default: greenfield

### `get_next_spec_version(project_dir: Path) -> int`
- Busca backups existentes: `app_spec.txt.v1`, `app_spec.txt.v2`, etc.
- Retorna próximo número de versão

### `backup_app_spec(project_dir: Path) -> tuple[int, Path]`
- Cria backup versionado: `prompts/app_spec.txt` → `prompts/app_spec.txt.vN`
- Adiciona metadados XML no topo:
  ```xml
  <!--
    BACKUP METADATA
    ===============
    Original: app_spec.txt
    Version: vN
    Backed up: [timestamp ISO]
    Project Type: [greenfield|brownfield]
  -->
  ```
- Retorna `(version, backup_path)`

### `backup_database(project_dir: Path, version: int) -> Path`
- Cria backup: `features.db` → `features.db.vN`
- Retorna path do backup

### `get_existing_feature_count(project_dir: Path) -> int`
- Conta features no banco SQLite
- Retorna 0 se banco não existe

### `get_next_priority(project_dir: Path) -> int`
- Retorna `MAX(priority) + 1` do banco
- Retorna 1 se banco vazio

### `create_iteration(project_dir: Path, instructions: str) -> dict`
- Workflow completo de iteração:
  1. Detecta tipo de projeto
  2. Faz backup do app_spec.txt
  3. Faz backup do features.db
  4. Cria arquivo `prompts/iteration_vN_instructions.md` com:
     - Instruções do usuário
     - Contexto do projeto (feature count, next priority)
     - Instruções para o Initializer Agent
  5. Retorna metadados

**Formato do arquivo de instruções:**

```markdown
# Iteration vN Instructions

**Project Type:** [greenfield|brownfield]
**Date:** [timestamp]
**Previous Spec Backup:** app_spec.txt.vN
**Previous DB Backup:** features.db.vN

## Expansion Requirements

[user instructions]

---

## Instructions for Initializer Agent

You are expanding an existing project (brownfield).

**CRITICAL STEPS:**

1. **Read the PREVIOUS spec:** Read `prompts/app_spec.txt.vN` to understand what already exists

2. **Read the CURRENT database:**
   - Use `feature_get_stats` to see existing feature count
   - This project has [COUNT] features already implemented

3. **Edit app_spec.txt:** Update the CURRENT `prompts/app_spec.txt` to include:
   - All previous features (preserve them)
   - New features based on the expansion requirements above
   - Update total feature count

4. **Create ONLY NEW features:** When calling `feature_create_bulk`:
   - Create ONLY the new features (not the old ones)
   - They will be ADDED to the existing database
   - Set priority starting from [NEXT_PRIORITY]

5. **DO NOT recreate project structure:**
   - DO NOT overwrite existing source code
   - DO NOT recreate init.sh, README.md
   - ONLY add new feature definitions

6. **Preserve git history:**
   - Commit only the spec changes
   - Message: "Iteration vN: [brief description]"
```

---

## 2. Adicionar endpoint em `server/routers/projects.py`

### Imports necessários
```python
from pydantic import BaseModel
```

### Model Pydantic
```python
class IterationRequest(BaseModel):
    """Request to start a new project iteration."""
    instructions: str
```

### Endpoint
```python
@router.post("/{project_name}/iteration", response_model=ProjectDetail)
async def start_iteration(project_name: str, request: IterationRequest):
    """
    Start a new iteration of a project.

    This will:
    1. Detect if project is greenfield or brownfield
    2. Backup current app_spec.txt with version number
    3. Backup current features.db
    4. Create iteration instructions file
    5. Initializer Agent will process on next run
    """
    _init_imports()
    register_project, unregister_project, get_project_path, list_registered_projects, validate_project_path = _get_registry_functions()

    project_name = validate_project_name(project_name)
    project_dir = get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    # Import iteration utilities
    from ..services.iteration_manager import create_iteration

    try:
        result = await create_iteration(project_dir, request.instructions)

        return ProjectDetail(
            name=project_name,
            path=str(project_dir),
            has_spec=_check_spec_exists(project_dir),
            **result  # includes version, backup_path, etc.
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create iteration: {str(e)}")
```

**Localização:** Adicionar após os endpoints existentes (próximo linha 200+)

---

## 3. Modificar `agent.py` para detectar modo iteração

### Localização: Após linha 145 (onde está `is_first_run = not has_features(project_dir)`)

**Adicionar:**

```python
# Check if this is a fresh start or continuation
is_first_run = not has_features(project_dir)

# NEW: Check for iteration instructions
iteration_file = None
if not is_first_run:
    prompts_dir = project_dir / "prompts"
    # Look for iteration_v*_instructions.md files
    iteration_files = sorted(prompts_dir.glob("iteration_v*_instructions.md"))
    if iteration_files:
        # Use the latest iteration file
        iteration_file = iteration_files[-1]
        print(f"⚠️  Found iteration instructions: {iteration_file.name}")
        print("Will run in ITERATION mode (preserving existing features)")
        is_first_run = True  # Force Initializer to run, but in iteration mode
```

### Localização: Na seção onde o prompt é carregado (após linha 183)

**Modificar:**

```python
if is_first_run:
    if iteration_file:
        # Load iteration instructions instead of standard initializer prompt
        iteration_instructions = iteration_file.read_text(encoding='utf-8')
        base_prompt = get_initializer_prompt(project_dir)
        prompt = f"{base_prompt}\n\n---\n\n{iteration_instructions}"

        # Delete iteration file after loading (prevent re-running)
        iteration_file.unlink()
        print(f"✅ Loaded iteration instructions (deleted {iteration_file.name})")
    else:
        # Standard initializer
        prompt = get_initializer_prompt(project_dir)

    is_first_run = False  # Only use initializer once
else:
    # Continuation session (coding agent)
    prompt = get_coding_prompt(project_dir)
```

---

# VALIDAÇÃO

Após implementação, teste:

1. **Criar projeto greenfield:**
   ```bash
   python start.py
   # Criar novo projeto "test-iteration"
   ```

2. **Simular iteração:**
   ```python
   from pathlib import Path
   from server.services.iteration_manager import create_iteration

   result = create_iteration(
       Path("generations/test-iteration"),
       "Add user profile page with avatar upload"
   )
   print(result)
   ```

3. **Verificar arquivos criados:**
   - `prompts/app_spec.txt.v1` (backup)
   - `features.db.v1` (backup)
   - `prompts/iteration_v1_instructions.md` (instruções)

4. **Rodar agent:**
   ```bash
   python autonomous_agent_demo.py --project-dir test-iteration
   ```
   - Deve detectar iteration mode
   - Deve carregar instruções
   - Deve deletar arquivo de instruções após carregar

---

# RESULTADO ESPERADO

Ao final desta etapa:
- ✅ Backend suporta criação de iterações
- ✅ Specs e databases são versionados automaticamente
- ✅ Agent detecta e processa modo iteração
- ✅ Features existentes são preservadas

**Próxima etapa:** Criar UI para botão "Add Iteration" (comando 02)