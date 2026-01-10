---
description: Create frontend UI for project iterations
order: 2
---

# OBJETIVO

Criar interface de usuário para iniciar iterações de projeto, incluindo:
1. Modal de criação de iteração
2. Atalho de teclado 'i'
3. Hook React Query para API
4. Badge indicador de projeto brownfield

**Pré-requisito:** Comando 01 (backend) deve estar completo.

---

# CONTEXTO

A UI deve permitir que usuários iniciem iterações de forma intuitiva:
- Botão visual ou atalho 'i'
- Modal com explicação clara do que vai acontecer
- Textarea para instruções de expansão
- Feedback de progresso

**Referência:** Ver `docs/SESSAO_ANALISE_AUTOCODER.md` seção "Botão Add Iteration com Atalho i"

---

# TAREFAS

## 1. Criar `ui/src/components/AddIterationModal.tsx`

Componente modal completo com:
- Header com ícone GitBranch
- Warning box explicando o processo
- Textarea para instruções
- Botões Cancel/Start Iteration
- Loading state

**Arquivo completo:**

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
      <div className="bg-white border-3 border-black p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto shadow-neo">
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
            <li>Create a versioned backup of app_spec.txt and features.db</li>
            <li>Generate iteration instructions for the Initializer Agent</li>
            <li>Add NEW features to the database (preserving existing ones)</li>
            <li>The agent will process this on next run</li>
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
              className="w-full border-3 border-black p-3 font-mono text-sm resize-y min-h-[200px] focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Example: Add user profile functionality with the following features:
- Profile page showing user info and avatar
- Edit profile form with validation
- Avatar upload with image preview
- Profile settings (privacy, notifications)"
              required
            />
            <p className="text-sm text-gray-600 mt-2">
              Describe what you want to add. Be specific about features, screens, and behaviors.
            </p>
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
                  Creating Iteration...
                </>
              ) : (
                <>
                  <GitBranch size={18} />
                  Start Iteration
                </>
              )}
            </button>
          </div>

          {startIteration.isError && (
            <div className="mt-4 p-3 bg-red-50 border-3 border-red-600 text-red-900">
              <p className="font-bold">Error creating iteration:</p>
              <p className="text-sm">{startIteration.error?.message || 'Unknown error'}</p>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
```

---

## 2. Adicionar hook em `ui/src/hooks/useProjects.ts`

### Localização: Após os hooks existentes

**Adicionar:**

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
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to start iteration')
      }
      return response.json()
    },
    onSuccess: () => {
      // Invalidate queries to refresh UI
      queryClient.invalidateQueries({ queryKey: ['projects', projectName] })
      queryClient.invalidateQueries({ queryKey: ['features', projectName] })
    },
  })
}
```

---

## 3. Modificar `ui/src/App.tsx`

### 3.1 Adicionar state (após linha 31)

**Adicionar:**

```typescript
const [showAddIteration, setShowAddIteration] = useState(false)
```

### 3.2 Adicionar atalho de teclado (após linha 94, depois do atalho 'A')

**Adicionar dentro do `useEffect` de keyboard shortcuts:**

```typescript
// I : Add Iteration (when project selected and not running)
if ((e.key === 'i' || e.key === 'I') && selectedProject && agentStatus !== 'running') {
  e.preventDefault()
  setShowAddIteration(true)
}
```

### 3.3 Adicionar import do modal (topo do arquivo)

**Adicionar:**

```typescript
import { AddIterationModal } from './components/AddIterationModal'
```

### 3.4 Adicionar modal no render (após os outros modais, próximo linha 200+)

**Adicionar:**

```typescript
{showAddIteration && selectedProject && (
  <AddIterationModal
    projectName={selectedProject}
    onClose={() => setShowAddIteration(false)}
  />
)}
```

### 3.5 Adicionar botão visual (opcional, na toolbar do projeto)

**Localização:** Onde estão os botões de controle do projeto

**Adicionar:**

```typescript
<button
  onClick={() => setShowAddIteration(true)}
  disabled={agentStatus === 'running'}
  className="neo-btn neo-btn-accent flex items-center gap-2"
  title="Add Iteration (i)"
>
  <GitBranch size={18} />
  Add Iteration
</button>
```

---

## 4. Adicionar badge brownfield (opcional)

### Modificar `ui/src/components/ProjectSelector.tsx` (se existir)

OU adicionar inline onde projetos são listados:

```typescript
// Onde o nome do projeto é renderizado
<div className="flex items-center justify-between">
  <span className="font-bold">{project.name}</span>
  {project.type === 'brownfield' && (
    <span className="px-2 py-1 bg-blue-100 border-2 border-blue-600 text-xs font-bold text-blue-900">
      BROWNFIELD
    </span>
  )}
</div>
```

**Nota:** Isso requer que o backend retorne `type: "greenfield" | "brownfield"` na API de projetos.

---

## 5. Atualizar tipos TypeScript em `ui/src/lib/types.ts`

**Adicionar/atualizar:**

```typescript
export interface Project {
  name: string
  path: string
  has_spec: boolean
  type?: 'greenfield' | 'brownfield'  // Novo campo
  iteration_version?: number           // Novo campo
}

export interface IterationRequest {
  instructions: string
}
```

---

# VALIDAÇÃO

Após implementação, teste:

1. **Build do frontend:**
   ```bash
   cd ui
   npm run build
   ```

2. **Iniciar UI:**
   ```bash
   ./start_ui.sh  # ou start_ui.bat no Windows
   ```

3. **Testar atalho 'i':**
   - Selecionar projeto
   - Pressionar 'i'
   - Modal deve abrir

4. **Testar criação de iteração:**
   - Preencher instruções
   - Clicar "Start Iteration"
   - Verificar que modal fecha
   - Verificar que features são criadas no banco

5. **Verificar console do browser:**
   - Não deve ter erros
   - Request POST para `/api/projects/{name}/iteration` deve ter sucesso

---

# MELHORIAS OPCIONAIS

Após funcionalidade básica:

1. **Mostrar versão atual no modal:**
   - "This will create version 3 based on your current spec (v2)"

2. **Histórico de iterações:**
   - Nova aba mostrando iterações passadas
   - Links para backups de spec

3. **Preview do impacto:**
   - Estimativa de quantas features serão criadas
   - Com base no texto das instruções

---

# RESULTADO ESPERADO

Ao final desta etapa:
- ✅ UI permite iniciar iterações via modal
- ✅ Atalho 'i' funciona corretamente
- ✅ Feedback visual durante processo
- ✅ Integração com backend funciona

**Próxima etapa:** Atualizar prompt do Initializer (comando 03)