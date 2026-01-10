# Análise do AutoCoder: Greenfield vs Brownfield

**Data:** 2026-01-10
**Projeto Analisado:** TrelloClone (first-test-app)
**Repositório AutoCoder:** https://github.com/leonvanzyl/autocoder

---

## 📋 Resumo da Sessão

### Contexto
Análise profunda do AutoCoder para entender se ele suporta expansão de projetos brownfield (projetos existentes) ou apenas greenfield (novos projetos do zero).

### Descobertas Principais

#### ✅ O AutoCoder FOI PROJETADO para Greenfield
- **Initializer Agent** cria projetos do zero baseado em `app_spec.txt`
- **Coding Agent** implementa features sequencialmente do banco `features.db`
- Features são criadas **uma única vez** pelo Initializer (via `feature_create_bulk`)
- Não há workflow documentado para adicionar features incrementalmente

#### ⚠️ Limitações para Brownfield
1. **Features são imutáveis**: Não há ferramentas MCP para editar/deletar features
2. **app_spec.txt é processado apenas na inicialização**: Editar o spec depois não adiciona novas features
3. **Banco de dados único**: Cada projeto tem um `features.db` isolado, sem mecanismo de merge
4. **Estrutura de código é criada, não adaptada**: Initializer gera código novo, não modifica existente

#### 🔍 Como o AutoCoder Decide Qual Agent Rodar

```python
# De agent.py:145
is_first_run = not has_features(project_dir)

# De progress.py:20-55
def has_features(project_dir: Path) -> bool:
    db_file = project_dir / "features.db"
    if not db_file.exists():
        return False

    # Verifica se tem features no banco
    cursor.execute("SELECT COUNT(*) FROM features")
    count = cursor.fetchone()[0]
    return count > 0

# Lógica:
if is_first_run:  # has_features() == False
    # Roda Initializer Agent
else:
    # Roda Coding Agent
```

**Critério de Detecção:**
- **Greenfield**: `features.db` não existe OU está vazio → Roda Initializer
- **Brownfield**: `features.db` existe E tem features → Roda Coding Agent

---

## 🎯 Melhorias Propostas

### 1. Botão "Add Iteration" com Atalho 'i'

Permite iniciar uma nova iteração de expansão do projeto, criando backup do spec e rodando o Initializer novamente.

#### Arquivos a Modificar

##### **Frontend: `ui/src/App.tsx`**

**Localização dos atalhos de teclado:** Linhas 70-110

```typescript
// ADICIONAR após a linha 94 (após o atalho 'A'):

// I : Add Iteration (when project selected)
if ((e.key === 'i' || e.key === 'I') && selectedProject) {
  e.preventDefault()
  setShowAddIteration(true)  // Novo state
}
```

**Adicionar state no topo do componente (após linha 31):**

```typescript
const [showAddIteration, setShowAddIteration] = useState(false)
```

**Adicionar novo componente modal (criar arquivo):**

Arquivo: `ui/src/components/AddIterationModal.tsx`

```typescript
import { useState } from 'react'
import { useStartIteration } from '../hooks/useProjects'
import { X, GitBranch, Loader2 } from 'lucide-react'

interface AddIterationModalProps {
  projectName: string
  onClose: () => void
}

export function AddIterationModal({ projectName, onClose }: AddIterationModalProps) {
  const [instructions, setInstructions] = useState('')
  const startIteration = useStartIteration(projectName)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!instructions.trim()) return

    startIteration.mutate(
      { instructions },
      {
        onSuccess: () => {
          onClose()
        },
      }
    )
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white border-3 border-black p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-display font-bold text-2xl flex items-center gap-2">
            <GitBranch size={24} />
            Add Project Iteration
          </h2>
          <button onClick={onClose} className="neo-btn neo-btn-secondary p-2">
            <X size={20} />
          </button>
        </div>

        <div className="mb-4 p-4 bg-yellow-50 border-3 border-yellow-600">
          <p className="font-bold text-yellow-900 mb-2">⚠️ This will:</p>
          <ul className="list-disc list-inside text-sm text-yellow-800 space-y-1">
            <li>Create a backup of the current app_spec.txt (versioned)</li>
            <li>Generate a NEW app_spec.txt with your expansion instructions</li>
            <li>Create NEW features in the database (added to existing ones)</li>
            <li>The Initializer Agent will handle the spec update</li>
          </ul>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block font-display font-bold mb-2">
              Expansion Instructions
            </label>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              className="w-full border-3 border-black p-3 font-mono text-sm resize-y min-h-[200px]"
              placeholder="Example: Add export/import functionality using CSV format. Include features for:
- Exporting current board to CSV
- Importing boards from CSV with validation
- Export history tracking"
              required
            />
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="neo-btn neo-btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={startIteration.isPending || !instructions.trim()}
              className="neo-btn neo-btn-primary flex items-center gap-2"
            >
              {startIteration.isPending ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Starting Iteration...
                </>
              ) : (
                <>
                  <GitBranch size={18} />
                  Start Iteration
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
```

**Adicionar no render do App.tsx (após linha 200+):**

```typescript
{showAddIteration && (
  <AddIterationModal
    projectName={selectedProject}
    onClose={() => setShowAddIteration(false)}
  />
)}
```

##### **Frontend: `ui/src/hooks/useProjects.ts`**

**Adicionar novo hook:**

```typescript
export function useStartIteration(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: { instructions: string }) => {
      const response = await fetch(`/api/projects/${projectName}/iteration`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!response.ok) throw new Error('Failed to start iteration')
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects', projectName] })
      queryClient.invalidateQueries({ queryKey: ['features', projectName] })
    },
  })
}
```

---

#### Backend: Python API

##### **Arquivo: `server/routers/projects.py`**

**Adicionar novo endpoint (adicionar após linha 200+):**

```python
from pydantic import BaseModel

class IterationRequest(BaseModel):
    """Request to start a new project iteration."""
    instructions: str

@router.post("/{project_name}/iteration", response_model=ProjectDetail)
async def start_iteration(project_name: str, request: IterationRequest):
    """
    Start a new iteration of a project.

    This will:
    1. Detect if project is greenfield or brownfield
    2. Backup current app_spec.txt with version number
    3. Create conversation with Initializer to update spec
    4. Initializer will add NEW features to existing database
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
            iteration_version=result['version'],
            backup_path=result['backup_path']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create iteration: {str(e)}")
```

##### **Novo Arquivo: `server/services/iteration_manager.py`**

```python
"""
Iteration Manager
=================

Manages project iterations and app_spec.txt versioning.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path


def detect_project_type(project_dir: Path) -> str:
    """
    Detect if a project is greenfield or brownfield.

    Criteria:
    - Greenfield: features.db doesn't exist OR is empty
    - Brownfield: features.db exists AND has features

    Returns:
        "greenfield" or "brownfield"
    """
    import sqlite3

    db_file = project_dir / "features.db"

    if not db_file.exists():
        return "greenfield"

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM features")
        count = cursor.fetchone()[0]
        conn.close()

        return "brownfield" if count > 0 else "greenfield"
    except Exception:
        return "greenfield"


def get_next_spec_version(project_dir: Path) -> int:
    """
    Get the next version number for app_spec.txt backup.

    Looks for existing backups like:
    - app_spec.txt.v1
    - app_spec.txt.v2

    Returns:
        Next version number (1 if no backups exist)
    """
    prompts_dir = project_dir / "prompts"

    if not prompts_dir.exists():
        return 1

    max_version = 0
    pattern = re.compile(r'app_spec\.txt\.v(\d+)$')

    for file in prompts_dir.iterdir():
        match = pattern.match(file.name)
        if match:
            version = int(match.group(1))
            max_version = max(max_version, version)

    return max_version + 1


def backup_app_spec(project_dir: Path) -> tuple[int, Path]:
    """
    Create a versioned backup of the current app_spec.txt.

    Returns:
        (version_number, backup_path)
    """
    prompts_dir = project_dir / "prompts"
    spec_file = prompts_dir / "app_spec.txt"

    if not spec_file.exists():
        raise FileNotFoundError(f"No app_spec.txt found in {prompts_dir}")

    version = get_next_spec_version(project_dir)
    backup_path = prompts_dir / f"app_spec.txt.v{version}"

    # Copy with metadata
    shutil.copy2(spec_file, backup_path)

    # Add metadata comment to backup
    metadata = f"""
<!--
  BACKUP METADATA
  ===============
  Original: app_spec.txt
  Version: v{version}
  Backed up: {datetime.now().isoformat()}
  Project Type: {detect_project_type(project_dir)}
-->

"""

    content = backup_path.read_text(encoding='utf-8')
    backup_path.write_text(metadata + content, encoding='utf-8')

    return version, backup_path


async def create_iteration(project_dir: Path, instructions: str) -> dict:
    """
    Create a new project iteration.

    Workflow:
    1. Detect project type (greenfield/brownfield)
    2. Backup current app_spec.txt with version
    3. Prepare instructions for Initializer Agent
    4. Return metadata for UI

    Args:
        project_dir: Project directory path
        instructions: User's expansion instructions

    Returns:
        {
            'project_type': 'greenfield' or 'brownfield',
            'version': version number,
            'backup_path': path to backup file,
            'ready': True if ready for Initializer
        }
    """
    project_type = detect_project_type(project_dir)

    # Backup existing spec
    version, backup_path = backup_app_spec(project_dir)

    # Create iteration instructions file
    prompts_dir = project_dir / "prompts"
    iteration_file = prompts_dir / f"iteration_v{version}_instructions.md"

    iteration_content = f"""# Iteration v{version} Instructions

**Project Type:** {project_type}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Previous Spec Backup:** app_spec.txt.v{version}

## Expansion Requirements

{instructions}

---

## Instructions for Initializer Agent

You are expanding an existing project (brownfield).

**CRITICAL STEPS:**

1. **Read the PREVIOUS spec:** Read `prompts/app_spec.txt.v{version}` to understand what already exists

2. **Read the CURRENT database:** Check how many features already exist:
   - Use `feature_get_stats` to see existing feature count
   - This project has {get_existing_feature_count(project_dir)} features implemented

3. **Edit app_spec.txt:** Update the CURRENT `prompts/app_spec.txt` to include:
   - All previous features (preserve them)
   - New features based on the expansion requirements above
   - Update feature count: [OLD_COUNT] + [NEW_COUNT]

4. **Create ONLY NEW features:** When calling `feature_create_bulk`:
   - Create ONLY the new features (not the old ones)
   - They will be ADDED to the existing database
   - Set priority starting from {get_next_priority(project_dir)}

5. **DO NOT recreate project structure:** The project already exists
   - DO NOT overwrite existing source code
   - DO NOT recreate init.sh, README.md
   - ONLY add new feature definitions

6. **Preserve git history:**
   - Commit only the spec changes and new feature definitions
   - Message: "Iteration v{version}: [brief description]"
"""

    iteration_file.write_text(iteration_content, encoding='utf-8')

    return {
        'project_type': project_type,
        'version': version,
        'backup_path': str(backup_path),
        'iteration_instructions': str(iteration_file),
        'ready': True
    }


def get_existing_feature_count(project_dir: Path) -> int:
    """Get count of existing features in database."""
    import sqlite3

    db_file = project_dir / "features.db"
    if not db_file.exists():
        return 0

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM features")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def get_next_priority(project_dir: Path) -> int:
    """Get the next priority number for new features."""
    import sqlite3

    db_file = project_dir / "features.db"
    if not db_file.exists():
        return 1

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(priority) FROM features")
        result = cursor.fetchone()[0]
        conn.close()
        return (result or 0) + 1
    except Exception:
        return 1
```

##### **Modificar: `agent.py`**

**Adicionar lógica para detectar iterações (após linha 145):**

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

**Modificar prompt do Initializer (após linha 183):**

```python
if is_first_run:
    if iteration_file:
        # Load iteration instructions instead of standard initializer prompt
        iteration_instructions = iteration_file.read_text(encoding='utf-8')
        base_prompt = get_initializer_prompt(project_dir)
        prompt = f"{base_prompt}\n\n{iteration_instructions}"

        # Delete iteration file after loading (prevent re-running)
        iteration_file.unlink()
    else:
        # Standard initializer
        prompt = get_initializer_prompt(project_dir)

    is_first_run = False  # Only use initializer once
```

---

### 2. Detecção Automática: Greenfield vs Brownfield

#### Critérios Sugeridos

**Melhor Método de Detecção:**

```python
def detect_project_type(project_dir: Path) -> str:
    """
    Detect project type based on multiple signals.

    Criteria (in order of importance):
    1. features.db exists AND has features → BROWNFIELD
    2. Source code exists (src/, client/, server/) → BROWNFIELD
    3. Git history exists (.git/) → BROWNFIELD
    4. Only templates exist → GREENFIELD
    """

    # Primary: Check features database
    db_file = project_dir / "features.db"
    if db_file.exists():
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM features")
            count = cursor.fetchone()[0]
            conn.close()

            if count > 0:
                return "brownfield"
        except Exception:
            pass

    # Secondary: Check for source code directories
    source_indicators = [
        "src",
        "client",
        "server",
        "frontend",
        "backend",
        "app",
        "lib",
        "components"
    ]

    for indicator in source_indicators:
        source_dir = project_dir / indicator
        if source_dir.exists() and source_dir.is_dir():
            # Check if directory has actual code (not just empty)
            if any(source_dir.iterdir()):
                return "brownfield"

    # Tertiary: Check git history
    git_dir = project_dir / ".git"
    if git_dir.exists():
        try:
            # Check if there are commits
            import subprocess
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            commit_count = int(result.stdout.strip())
            if commit_count > 0:
                return "brownfield"
        except Exception:
            pass

    # Default: Assume greenfield
    return "greenfield"
```

**Adicionar indicador visual na UI:**

Arquivo: `ui/src/components/ProjectSelector.tsx`

```typescript
// Adicionar badge ao lado do nome do projeto
<div className="flex items-center justify-between">
  <span>{project.name}</span>
  {project.type === 'brownfield' && (
    <span className="px-2 py-1 bg-blue-100 border border-blue-600 text-xs font-bold text-blue-900">
      BROWNFIELD
    </span>
  )}
</div>
```

---

### 3. Versionamento Automático do app_spec.txt

#### Implementação Completa

O código já foi incluído no `iteration_manager.py` acima. Resumo:

**Formato de Backup:**
```
prompts/
├── app_spec.txt              <- Versão atual (sempre)
├── app_spec.txt.v1           <- Backup da v1
├── app_spec.txt.v2           <- Backup da v2
├── app_spec.txt.v3           <- Backup da v3 (mais recente)
├── iteration_v3_instructions.md  <- Instruções da iteração
```

**Metadados no Backup:**
```xml
<!--
  BACKUP METADATA
  ===============
  Original: app_spec.txt
  Version: v3
  Backed up: 2026-01-10T15:30:00
  Project Type: brownfield
-->

<project_specification>
  ...
</project_specification>
```

**Fluxo de Trabalho:**
1. Usuário clica "Add Iteration" (ou pressiona 'i')
2. Digita instruções de expansão
3. Backend:
   - Detecta tipo de projeto (greenfield/brownfield)
   - Faz backup: `app_spec.txt` → `app_spec.txt.vN`
   - Cria `iteration_vN_instructions.md` com contexto
4. Initializer Agent roda com instruções especiais:
   - Lê spec anterior
   - Atualiza `app_spec.txt` com novas features
   - Adiciona SOMENTE novas features ao `features.db`
   - NÃO recria estrutura de código

---

## 🔧 Análise de Suficiência

### ✅ O Que Está Coberto

1. **Botão "Add Iteration"**: Implementação completa (frontend + backend)
2. **Atalho de teclado 'i'**: Adicionado no sistema de shortcuts do App.tsx
3. **Detecção greenfield/brownfield**: Múltiplos critérios (banco, código, git)
4. **Versionamento de spec**: Backup automático com metadados
5. **Preservação de features**: Novas features são ADICIONADAS, não sobrescritas

### ⚠️ O Que Pode Precisar de Mais

#### 1. **Merge de Features no Banco**

**Problema Potencial:** Se o usuário deletar `features.db` por engano e re-rodar o Initializer, perde todo o progresso.

**Solução Adicional:**

```python
# Em iteration_manager.py
def backup_database(project_dir: Path, version: int) -> Path:
    """Backup features.db along with app_spec.txt."""
    db_file = project_dir / "features.db"
    backup_db = project_dir / f"features.db.v{version}"

    if db_file.exists():
        shutil.copy2(db_file, backup_db)

    return backup_db

# Chamada em create_iteration():
backup_app_spec(project_dir)
backup_database(project_dir, version)  # ADICIONAR ESTA LINHA
```

#### 2. **Validação de Spec pelo Initializer**

**Problema Potencial:** O Initializer pode confundir e criar features duplicadas se não ler corretamente o banco existente.

**Solução Adicional:**

Modificar `.claude/templates/initializer_prompt.template.md`:

```markdown
## ITERATION MODE (For Brownfield Projects)

If you see iteration instructions in your prompt:

1. **CRITICAL: Read existing features FIRST**
   - Call `feature_get_stats` to see total count
   - This tells you how many features are ALREADY implemented
   - DO NOT recreate these features!

2. **When calling feature_create_bulk:**
   - Create ONLY the features mentioned in the iteration instructions
   - These will be ADDED to the database (not replace)
   - Start priority from: [NEXT_PRIORITY] (provided in instructions)

3. **Validation Checklist:**
   - [ ] Read previous spec backup to understand what exists
   - [ ] Read current database stats (feature count)
   - [ ] Calculate NEW feature count = iteration requirements only
   - [ ] Create features with priority starting from MAX+1
```

#### 3. **UI para Visualizar Histórico de Iterações**

**Melhoria Sugerida:**

Adicionar aba "Iterations" no projeto:

```typescript
// Em App.tsx ou novo componente
<Tabs>
  <Tab>Kanban Board</Tab>
  <Tab>Progress</Tab>
  <Tab>Iterations</Tab>  {/* NOVO */}
</Tabs>

// Conteúdo da aba:
<IterationHistory projectName={selectedProject}>
  <IterationItem version={3} date="2026-01-10">
    Added export/import functionality
    - 15 new features
    - Backup: app_spec.txt.v3
  </IterationItem>
  <IterationItem version={2} date="2026-01-08">
    Added dark mode
    - 8 new features
    - Backup: app_spec.txt.v2
  </IterationItem>
</IterationHistory>
```

#### 4. **Rollback de Iterações**

**Funcionalidade Adicional:**

Endpoint para reverter para uma versão anterior:

```python
@router.post("/{project_name}/iteration/{version}/rollback")
async def rollback_iteration(project_name: str, version: int):
    """
    Rollback to a previous iteration.

    1. Restore app_spec.txt from app_spec.txt.vN
    2. Restore features.db from features.db.vN
    3. Remove features added after version N
    """
    project_dir = get_project_path(project_name)

    # Restore spec
    backup_spec = project_dir / "prompts" / f"app_spec.txt.v{version}"
    if not backup_spec.exists():
        raise HTTPException(404, "Backup not found")

    current_spec = project_dir / "prompts" / "app_spec.txt"
    shutil.copy2(backup_spec, current_spec)

    # Restore database (if backup exists)
    backup_db = project_dir / f"features.db.v{version}"
    if backup_db.exists():
        current_db = project_dir / "features.db"
        shutil.copy2(backup_db, current_db)

    return {"message": f"Rolled back to iteration v{version}"}
```

---

## 🎓 Recomendações Finais

### Para Uso Imediato

**As implementações propostas acima SÃO SUFICIENTES** para:
- ✅ Adicionar funcionalidade de iteração ao AutoCoder
- ✅ Distinguir projetos greenfield de brownfield
- ✅ Versionar specs automaticamente
- ✅ Preservar features existentes ao expandir

### Para Produção Robusta

**Considere adicionar:**
1. **Backup automático de `features.db`** (além do spec)
2. **Validação de duplicatas** no Initializer
3. **UI de histórico de iterações** (visualizar evoluções)
4. **Rollback** de iterações (desfazer expansões)
5. **Diff viewer** (comparar specs entre versões)

### Alternativa: Usar Claude Code Diretamente

Para o projeto **first-test-app** que já está funcional:

**Vantagens de NÃO modificar o AutoCoder:**
- ✅ Menor complexidade
- ✅ Controle total do código
- ✅ Expansões sob demanda (não batched)
- ✅ Git history limpo

**Quando usar cada ferramenta:**
- **AutoCoder**: MVPs greenfield 0-to-1
- **Claude Code CLI**: Evolução brownfield, refatorações, features incrementais

---

## 📂 Estrutura de Arquivos Modificados

```
autocoder/
├── ui/src/
│   ├── App.tsx                              # MODIFICAR (atalho 'i')
│   ├── components/
│   │   ├── AddIterationModal.tsx            # CRIAR
│   │   └── ProjectSelector.tsx              # MODIFICAR (badge brownfield)
│   └── hooks/
│       └── useProjects.ts                   # MODIFICAR (hook iteration)
│
├── server/
│   ├── routers/
│   │   └── projects.py                      # MODIFICAR (endpoint /iteration)
│   └── services/
│       └── iteration_manager.py             # CRIAR
│
├── agent.py                                 # MODIFICAR (detect iteration mode)
│
└── .claude/templates/
    └── initializer_prompt.template.md       # MODIFICAR (iteration instructions)
```

---

## 📊 Comparação: Antes vs Depois

| Aspecto | Antes (AutoCoder Original) | Depois (Com Melhorias) |
|---------|----------------------------|------------------------|
| **Tipo de Projeto** | Apenas greenfield | Greenfield + Brownfield |
| **Adicionar Features** | ❌ Não suportado | ✅ Via iterações |
| **Versioning** | ❌ Sem backup | ✅ app_spec.txt.vN automático |
| **Detecção Automática** | ❌ Não distingue | ✅ Detecta greenfield/brownfield |
| **Preservação de Progresso** | ⚠️ Sobrescreve | ✅ Adiciona sem perder |
| **UI Atalhos** | D, N, A | D, N, A, **I** (novo) |
| **Workflow Expansion** | ❌ Recomeçar do zero | ✅ Expansão incremental |

---

## 🚀 Próximos Passos

1. **Implementar código acima** no fork do AutoCoder
2. **Testar** com projeto existente (first-test-app)
3. **Validar** que features não são duplicadas
4. **Documentar** no README do AutoCoder
5. **Contribuir** para o repositório oficial (se desejado)

---

## 📚 Referências

- **AutoCoder GitHub**: https://github.com/leonvanzyl/autocoder
- **Protocolo Anthropic**: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- **Claude Agent SDK**: https://github.com/anthropics/anthropic-sdk-python
- **Projeto Analisado**: `/home/vinicius/RiderProjects/FirstTestApp/first-test-app`

---

**Autor:** Claude Sonnet 4.5
**Sessão:** 2026-01-10
**Status:** ✅ Análise Completa