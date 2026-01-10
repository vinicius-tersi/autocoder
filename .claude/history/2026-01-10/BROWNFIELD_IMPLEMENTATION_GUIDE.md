# Brownfield Implementation Guide

Este guia explica como implementar suporte a projetos brownfield no AutoCoder.

## 📋 Visão Geral

O AutoCoder originalmente suportava apenas projetos **greenfield** (criados do zero). Estas mudanças adicionam suporte a **brownfield** (projetos existentes), permitindo:

- ✅ Adicionar features incrementalmente
- ✅ Expandir projetos via iterações
- ✅ Preservar progresso existente
- ✅ Versionar specs e databases automaticamente

## 🎯 Análise de Viabilidade

**Status:** ✅ **MUDANÇAS SÃO VIÁVEIS**

Ver `docs/SESSAO_ANALISE_AUTOCODER.md` para análise completa.

**Resumo:**
- Arquitetura atual já tem base necessária
- Lógica de detecção greenfield/brownfield já existe
- Mudanças são incrementais e não quebram funcionalidades
- Todas as implementações são bem definidas

## 📂 Arquivos de Comando

### Ordem de Implementação

Execute os comandos na ordem numérica:

| # | Comando | Descrição | Pré-requisitos |
|---|---------|-----------|----------------|
| **01** | `01-create-backend-iteration-support.md` | Backend: API + iteration manager + agent detection | Nenhum |
| **02** | `02-create-frontend-iteration-ui.md` | Frontend: Modal + atalho 'i' + hooks | Comando 01 |
| **03** | `03-update-initializer-prompt.md` | Prompts: Atualizar Initializer para iteration mode | Comandos 01, 02 |
| **04** | `04-add-brownfield-command.md` | CLI: Comando `/brownfield-iteration` (opcional) | Comandos 01-03 |

### Comandos Opcionais

Após os 3 comandos principais, você pode implementar:

- **Comando 04:** `/brownfield-iteration` - CLI alternativo à UI
- **Histórico de iterações:** UI mostrando versões passadas
- **Rollback:** Reverter para versões anteriores
- **Diff viewer:** Comparar specs entre versões

## 🚀 Como Implementar

### Método 1: Implementação Automática (Recomendado)

Use o Claude Code para implementar cada comando:

```bash
# 1. Backend
claude code "Implemente o arquivo .claude/commands/01-create-backend-iteration-support.md"

# 2. Frontend
claude code "Implemente o arquivo .claude/commands/02-create-frontend-iteration-ui.md"

# 3. Prompts
claude code "Implemente o arquivo .claude/commands/03-update-initializer-prompt.md"

# 4. (Opcional) CLI
claude code "Implemente o arquivo .claude/commands/04-add-brownfield-command.md"
```

### Método 2: Implementação Manual

Siga as instruções em cada arquivo:

1. **Comando 01:**
   - Criar `server/services/iteration_manager.py`
   - Adicionar endpoint em `server/routers/projects.py`
   - Modificar `agent.py`

2. **Comando 02:**
   - Criar `ui/src/components/AddIterationModal.tsx`
   - Modificar `ui/src/App.tsx`
   - Adicionar hook em `ui/src/hooks/useProjects.ts`

3. **Comando 03:**
   - Modificar `.claude/templates/initializer_prompt.template.md`

4. **Comando 04 (opcional):**
   - Criar `.claude/commands/brownfield-iteration.md`

## ✅ Validação

Após cada comando, execute os testes de validação descritos no arquivo.

### Teste End-to-End

Após implementar comandos 01-03:

1. **Criar projeto greenfield:**
   ```bash
   python start.py
   # Criar "test-brownfield"
   ```

2. **Deixar agent criar features iniciais:**
   ```bash
   python autonomous_agent_demo.py --project-dir test-brownfield
   # Aguardar algumas features passarem
   ```

3. **Criar iteração via UI:**
   - Abrir UI: `./start_ui.sh`
   - Selecionar "test-brownfield"
   - Pressionar 'i'
   - Adicionar instruções: "Add user profile with avatar upload"
   - Clicar "Start Iteration"

4. **Verificar backups:**
   ```bash
   ls generations/test-brownfield/prompts/
   # Deve ter: app_spec.txt, app_spec.txt.v1, iteration_v1_instructions.md

   ls generations/test-brownfield/
   # Deve ter: features.db, features.db.v1
   ```

5. **Rodar agent novamente:**
   ```bash
   python autonomous_agent_demo.py --project-dir test-brownfield
   # Deve detectar iteration mode
   # Deve criar apenas features novas (não duplicar)
   ```

6. **Verificar database:**
   ```python
   import sqlite3
   conn = sqlite3.connect("generations/test-brownfield/features.db")
   cursor = conn.cursor()
   cursor.execute("SELECT COUNT(*) FROM features")
   print(f"Total features: {cursor.fetchone()[0]}")
   # Deve ter: old_count + new_count (sem duplicatas)
   ```

## 🎓 Arquitetura das Mudanças

### Backend Flow

```
User clicks "Add Iteration"
    ↓
POST /api/projects/{name}/iteration
    ↓
iteration_manager.create_iteration()
    ├─ Detect project type (brownfield)
    ├─ Backup app_spec.txt → app_spec.txt.vN
    ├─ Backup features.db → features.db.vN
    └─ Create iteration_vN_instructions.md
    ↓
Agent starts
    ↓
agent.py detects iteration file
    ├─ Sets is_first_run = True (force Initializer)
    └─ Loads iteration instructions
    ↓
Initializer Agent runs
    ├─ Reads app_spec.txt.vN (previous spec)
    ├─ Calls feature_get_stats() (existing count)
    ├─ Edits app_spec.txt (adds new features)
    └─ Calls feature_create_bulk(new_features_only)
    ↓
Coding Agent continues
    └─ Implements new features
```

### Frontend Flow

```
User presses 'i' keyboard shortcut
    ↓
Opens AddIterationModal
    ↓
User enters expansion instructions
    ↓
useStartIteration() hook calls API
    ↓
POST /api/projects/{name}/iteration
    ↓
Modal closes, UI refreshes
    ↓
User clicks Play to start agent
```

## 📊 Comparação: Antes vs Depois

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Tipo de Projeto** | Apenas greenfield | Greenfield + Brownfield |
| **Adicionar Features** | ❌ Recomeçar do zero | ✅ Via iterações |
| **Versioning** | ❌ Sem backup | ✅ Automático (vN) |
| **Detecção Automática** | ❌ Não distingue | ✅ Detecta tipo |
| **Preservação** | ⚠️ Sobrescreve | ✅ Adiciona |
| **UI Atalhos** | D, N, A | D, N, A, **I** |

## 🔧 Troubleshooting

### Erro: "Failed to create iteration"

**Causa:** Spec file não encontrado

**Solução:**
```bash
# Verificar se app_spec.txt existe
ls generations/my-project/prompts/app_spec.txt
```

### Erro: "Duplicate features created"

**Causa:** Initializer não leu o banco existente

**Solução:**
1. Verificar se prompt do Initializer foi atualizado (comando 03)
2. Verificar se `feature_get_stats()` está sendo chamado
3. Checar logs do agent para ver se iteration mode foi detectado

### UI: Modal não abre ao pressionar 'i'

**Causa:** Agent está rodando

**Solução:** Apenas pode criar iterações quando agent está parado

### Agent não detecta iteration mode

**Causa:** Arquivo de instruções não foi criado

**Solução:**
```bash
# Verificar se arquivo existe
ls generations/my-project/prompts/iteration_v*_instructions.md

# Verificar logs do agent
python autonomous_agent_demo.py --project-dir my-project
# Deve mostrar: "⚠️ Found iteration instructions: iteration_v1_instructions.md"
```

## 📚 Referências

- **Análise Original:** `docs/SESSAO_ANALISE_AUTOCODER.md`
- **AutoCoder GitHub:** https://github.com/leonvanzyl/autocoder
- **Claude Agent SDK:** https://github.com/anthropics/anthropic-sdk-python

## 🤝 Contribuindo

Após implementar e testar, considere:

1. Documentar no README principal
2. Criar exemplos/tutoriais
3. Contribuir para o repositório upstream
4. Compartilhar feedback sobre melhorias

---

**Status:** 📝 Guia completo - Pronto para implementação

**Última atualização:** 2026-01-10