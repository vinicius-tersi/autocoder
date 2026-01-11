---
description: Add "Add Iteration" button to UI Pending column header
order: 5
---

# OBJETIVO

Adicionar botão visual **"Add Iteration"** no cabeçalho da coluna "Pending" do Kanban board, ao lado dos botões existentes "Add Feature" (+) e "Expand Project" (✨).

**Pré-requisitos:** Comandos 01, 02, 03 e 04 completos.

---

# CONTEXTO

Atualmente existem 3 formas de adicionar features:
1. **Add Feature** (botão +) - Adiciona 1 feature manualmente
2. **Expand Project** (botão ✨) - Chat interativo para múltiplas features
3. **Add Iteration** (atalho 'i') - Modal para iteração brownfield **← SEM BOTÃO VISUAL**

O modal `AddIterationModal` já existe e funciona via atalho 'i', mas **não há botão visual** na interface. Este comando adiciona o botão.

**Referência:** Commit 334b655 moveu botões para o header da coluna Pending.

---

# TAREFAS

## 1. Modificar `ui/src/components/KanbanColumn.tsx`

### 1.1 Adicionar import do ícone GitBranch

**Localização:** Linha 1-2

**Antes:**
```typescript
import { Plus, Sparkles } from 'lucide-react'
import type { Feature } from '../lib/types'
```

**Depois:**
```typescript
import { Plus, Sparkles, GitBranch } from 'lucide-react'
import type { Feature } from '../lib/types'
```

### 1.2 Adicionar prop onAddIteration à interface

**Localização:** Linha 4-13 (interface KanbanColumnProps)

**Antes:**
```typescript
interface KanbanColumnProps {
  title: string
  count: number
  features: Feature[]
  color: 'pending' | 'progress' | 'done'
  onFeatureClick: (feature: Feature) => void
  onAddFeature?: () => void
  onExpandProject?: () => void
  showExpandButton?: boolean
}
```

**Depois:**
```typescript
interface KanbanColumnProps {
  title: string
  count: number
  features: Feature[]
  color: 'pending' | 'progress' | 'done'
  onFeatureClick: (feature: Feature) => void
  onAddFeature?: () => void
  onExpandProject?: () => void
  onAddIteration?: () => void
  showExpandButton?: boolean
  showIterationButton?: boolean
}
```

### 1.3 Adicionar props na desestruturação

**Localização:** Linha 23-31 (função KanbanColumn)

**Antes:**
```typescript
export function KanbanColumn({
  title,
  count,
  features,
  color,
  onFeatureClick,
  onAddFeature,
  onExpandProject,
  showExpandButton,
}: KanbanColumnProps) {
```

**Depois:**
```typescript
export function KanbanColumn({
  title,
  count,
  features,
  color,
  onFeatureClick,
  onAddFeature,
  onExpandProject,
  onAddIteration,
  showExpandButton,
  showIterationButton,
}: KanbanColumnProps) {
```

### 1.4 Adicionar botão "Add Iteration" no header

**Localização:** Linha 47-67 (dentro da condição do header com botões)

Encontre o bloco:
```typescript
{(onAddFeature || onExpandProject) && (
  <div className="flex gap-2">
    {onAddFeature && (
      <button
        onClick={onAddFeature}
        className="neo-btn neo-btn-sm flex items-center gap-1"
        title="Add Feature (N)"
      >
        <Plus size={16} />
      </button>
    )}
    {onExpandProject && showExpandButton && (
      <button
        onClick={onExpandProject}
        className="neo-btn neo-btn-sm flex items-center gap-1"
        title="Expand Project (E)"
      >
        <Sparkles size={16} />
      </button>
    )}
  </div>
)}
```

**Substitua por:**
```typescript
{(onAddFeature || onExpandProject || onAddIteration) && (
  <div className="flex gap-2">
    {onAddFeature && (
      <button
        onClick={onAddFeature}
        className="neo-btn neo-btn-sm flex items-center gap-1"
        title="Add Feature (N)"
      >
        <Plus size={16} />
      </button>
    )}
    {onExpandProject && showExpandButton && (
      <button
        onClick={onExpandProject}
        className="neo-btn neo-btn-sm flex items-center gap-1"
        title="Expand Project (E)"
      >
        <Sparkles size={16} />
      </button>
    )}
    {onAddIteration && showIterationButton && (
      <button
        onClick={onAddIteration}
        className="neo-btn neo-btn-sm flex items-center gap-1"
        title="Add Iteration (I)"
      >
        <GitBranch size={16} />
      </button>
    )}
  </div>
)}
```

---

## 2. Modificar `ui/src/components/KanbanBoard.tsx`

### 2.1 Adicionar prop onAddIteration à interface

**Localização:** Linha 4-9

**Antes:**
```typescript
interface KanbanBoardProps {
  features: FeatureListResponse | undefined
  onFeatureClick: (feature: Feature) => void
  onAddFeature?: () => void
  onExpandProject?: () => void
}
```

**Depois:**
```typescript
interface KanbanBoardProps {
  features: FeatureListResponse | undefined
  onFeatureClick: (feature: Feature) => void
  onAddFeature?: () => void
  onExpandProject?: () => void
  onAddIteration?: () => void
}
```

### 2.2 Adicionar prop na desestruturação

**Localização:** Linha 11

**Antes:**
```typescript
export function KanbanBoard({ features, onFeatureClick, onAddFeature, onExpandProject }: KanbanBoardProps) {
```

**Depois:**
```typescript
export function KanbanBoard({ features, onFeatureClick, onAddFeature, onExpandProject, onAddIteration }: KanbanBoardProps) {
```

### 2.3 Passar onAddIteration para KanbanColumn Pending

**Localização:** Linha 33-42 (KanbanColumn "Pending")

**Antes:**
```typescript
<KanbanColumn
  title="Pending"
  count={features.pending.length}
  features={features.pending}
  color="pending"
  onFeatureClick={onFeatureClick}
  onAddFeature={onAddFeature}
  onExpandProject={onExpandProject}
  showExpandButton={hasFeatures}
/>
```

**Depois:**
```typescript
<KanbanColumn
  title="Pending"
  count={features.pending.length}
  features={features.pending}
  color="pending"
  onFeatureClick={onFeatureClick}
  onAddFeature={onAddFeature}
  onExpandProject={onExpandProject}
  onAddIteration={onAddIteration}
  showExpandButton={hasFeatures}
  showIterationButton={hasFeatures}
/>
```

---

## 3. Modificar `ui/src/App.tsx`

### 3.1 Passar onAddIteration para KanbanBoard

**Localização:** Linha 251-257 (onde KanbanBoard é renderizado)

**Antes:**
```typescript
<KanbanBoard
  features={features}
  onFeatureClick={setSelectedFeature}
  onAddFeature={() => setShowAddFeature(true)}
  onExpandProject={() => setShowExpandProject(true)}
/>
```

**Depois:**
```typescript
<KanbanBoard
  features={features}
  onFeatureClick={setSelectedFeature}
  onAddFeature={() => setShowAddFeature(true)}
  onExpandProject={() => setShowExpandProject(true)}
  onAddIteration={() => setShowAddIteration(true)}
/>
```

**Nota:** O estado `showAddIteration` e o modal `AddIterationModal` já existem (criados no Comando 02), apenas faltava passar o handler para o KanbanBoard.

---

## 4. Build e Validação

### 4.1 Build do Frontend

```bash
cd ui
npm run build
```

**Verificar:**
- ✅ Build completa sem erros
- ✅ Sem warnings de TypeScript
- ✅ Arquivo `dist/index.html` gerado

### 4.2 Teste Visual

1. **Iniciar UI:**
   ```bash
   cd ..
   ./start_ui.sh  # ou start_ui.bat no Windows
   ```

2. **Selecionar projeto** com features existentes

3. **Verificar botões na coluna Pending:**
   ```
   Pending (N)
   ┌─────────────────────────────────┐
   │ Pending           [+] [✨] [🌿] │  ← 3 botões
   └─────────────────────────────────┘
   ```

   - **[+]** Plus - Add Feature (tooltip: "Add Feature (N)")
   - **[✨]** Sparkles - Expand Project (tooltip: "Expand Project (E)")
   - **[🌿]** GitBranch - Add Iteration (tooltip: "Add Iteration (I)")

4. **Clicar no botão GitBranch:**
   - Modal `AddIterationModal` deve abrir
   - Mesmo comportamento do atalho 'i'

5. **Verificar condições:**
   - Botão "Add Iteration" só aparece quando `hasFeatures === true`
   - Mesmo comportamento do botão "Expand Project"

### 4.3 Teste de Integração

**Cenário 1: Projeto sem features**
- Selecionar projeto vazio
- **Resultado esperado:**
  - ✅ Botão "Add Feature" (+) visível
  - ❌ Botão "Expand Project" (✨) oculto
  - ❌ Botão "Add Iteration" (🌿) oculto

**Cenário 2: Projeto com features**
- Selecionar projeto com 10+ features
- **Resultado esperado:**
  - ✅ Todos os 3 botões visíveis
  - ✅ Clicar em qualquer botão abre o modal correto

**Cenário 3: Agent rodando**
- Agent em execução
- **Resultado esperado:**
  - ✅ Botões visíveis mas podem estar desabilitados
  - ✅ Atalho 'i' não funciona (conforme implementado)

---

## 5. Validação de Código

### 5.1 TypeScript Type Check

```bash
cd ui
npx tsc --noEmit
```

**Resultado esperado:** Sem erros

### 5.2 ESLint

```bash
cd ui
npm run lint
```

**Resultado esperado:** Sem erros (warnings ok)

### 5.3 Verificar Props Passadas

```bash
# Verificar que onAddIteration é passada em toda a cadeia
grep -n "onAddIteration" ui/src/App.tsx
grep -n "onAddIteration" ui/src/components/KanbanBoard.tsx
grep -n "onAddIteration" ui/src/components/KanbanColumn.tsx
```

**Resultado esperado:** Todas as 3 verificações retornam matches

---

## 6. Comparação Visual

### Antes (Comando 02)
```
┌─────────────────────────────────┐
│ Pending               [+] [✨]  │  ← 2 botões apenas
└─────────────────────────────────┘

Formas de adicionar iteration:
• Atalho 'i' apenas ✅
```

### Depois (Comando 05)
```
┌─────────────────────────────────┐
│ Pending           [+] [✨] [🌿] │  ← 3 botões
└─────────────────────────────────┘

Formas de adicionar iteration:
• Atalho 'i' ✅
• Botão visual 🌿 ✅
```

---

## 7. Checklist de Completude

- [ ] Import `GitBranch` adicionado em `KanbanColumn.tsx`
- [ ] Props `onAddIteration` e `showIterationButton` adicionadas à interface
- [ ] Props desestruturadas na função `KanbanColumn`
- [ ] Botão "Add Iteration" adicionado no header do Pending
- [ ] Prop `onAddIteration` adicionada à interface de `KanbanBoard`
- [ ] Prop passada para `KanbanColumn` Pending
- [ ] Handler `onAddIteration` passado de `App.tsx` para `KanbanBoard`
- [ ] Build completa sem erros
- [ ] Botão visível na UI (quando hasFeatures = true)
- [ ] Clicar no botão abre `AddIterationModal`
- [ ] Tooltip "Add Iteration (I)" aparece no hover

---

## 8. Troubleshooting

### Botão não aparece

**Possíveis causas:**
1. Build não foi executado: `cd ui && npm run build`
2. Servidor não foi reiniciado: Reiniciar `start_ui.sh`
3. Cache do browser: Ctrl+Shift+R (hard refresh)
4. Projeto não tem features: `showIterationButton` é false quando `hasFeatures` é false

### Botão aparece mas não funciona

**Verificar:**
```typescript
// Em App.tsx, verificar que handler está correto:
onAddIteration={() => setShowAddIteration(true)}

// E que o modal está renderizado:
{showAddIteration && selectedProject && (
  <AddIterationModal ...
```

### TypeScript errors

**Se houver erros de tipo:**
```bash
cd ui
rm -rf node_modules/.cache
npm run build
```

---

## 9. Resultado Final

Ao completar este comando, a UI terá:

**3 botões na coluna Pending:**
1. **Add Feature** (+) - Adiciona 1 feature
2. **Expand Project** (✨) - Chat para múltiplas features
3. **Add Iteration** (🌿) - Modal para iteração brownfield

**4 formas de adicionar features:**
1. Botão visual "Add Feature"
2. Botão visual "Expand Project"
3. Botão visual "Add Iteration" **← NOVO**
4. Atalhos de teclado (n, e, i)

**Consistência:**
- Todos os botões seguem o mesmo padrão visual (neo-btn neo-btn-sm)
- Todos têm tooltips informativos
- Todos respeitam a condição `hasFeatures` (exceto Add Feature)

---

## 10. Arquivos Modificados

**Sumário das mudanças:**

```
ui/src/components/KanbanColumn.tsx
  • Import GitBranch
  • +2 props: onAddIteration, showIterationButton
  • +1 botão no header

ui/src/components/KanbanBoard.tsx
  • +1 prop: onAddIteration
  • Pass para KanbanColumn Pending

ui/src/App.tsx
  • +1 linha: onAddIteration handler no KanbanBoard
```

**Total:** 3 arquivos modificados, ~20 linhas adicionadas

---

## ✅ VALIDAÇÃO FINAL

Execute estes comandos para confirmar sucesso:

```bash
# 1. Build
cd ui && npm run build

# 2. Verificar imports
grep "GitBranch" ui/src/components/KanbanColumn.tsx

# 3. Verificar props
grep "onAddIteration" ui/src/components/KanbanColumn.tsx
grep "onAddIteration" ui/src/components/KanbanBoard.tsx
grep "onAddIteration" ui/src/App.tsx

# 4. Contar botões na UI (deve ser 3)
grep -c "neo-btn neo-btn-sm" ui/src/components/KanbanColumn.tsx

# 5. Start UI
./start_ui.sh
```

**Resultado esperado:**
- ✅ Build sem erros
- ✅ 3 greps retornam matches
- ✅ Count retorna 3
- ✅ UI mostra 3 botões na coluna Pending

---

**Status:** PRONTO PARA IMPLEMENTAÇÃO 🚀

**Próximo comando:** Nenhum - Sistema brownfield completo!