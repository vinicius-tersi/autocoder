---
description: Update Initializer prompt to support iteration mode
order: 3
---

# OBJETIVO

Atualizar o template do prompt do Initializer Agent para:
1. Reconhecer quando está em modo iteração (brownfield)
2. Dar instruções claras sobre preservar features existentes
3. Evitar duplicação de features
4. Validar que apenas novas features são criadas

**Pré-requisitos:** Comandos 01 e 02 completos.

---

# CONTEXTO

O Initializer Agent precisa se comportar diferente em modo iteração:
- **Greenfield (normal):** Cria tudo do zero
- **Brownfield (iteração):** Adiciona apenas o novo, preserva o existente

**Referência:** Ver `docs/SESSAO_ANALISE_AUTOCODER.md` seção "Validação de Spec pelo Initializer"

---

# TAREFAS

## 1. Modificar `.claude/templates/initializer_prompt.template.md`

### Localização: Adicionar nova seção após a seção de "RESPONSIBILITIES" ou "WORKFLOW"

**Adicionar:**

```markdown
---

## 🔄 ITERATION MODE (Brownfield Projects)

**CRITICAL:** If you see iteration instructions in your prompt (marked with `# Iteration vN Instructions`), you are expanding an EXISTING project.

### Detection

You're in iteration mode if:
- The prompt contains `# Iteration vN Instructions`
- The instructions reference a previous spec backup (e.g., `app_spec.txt.v2`)
- You see context about existing feature count

### Special Rules for Iteration Mode

#### 1. **ALWAYS Read Existing State First**

Before doing ANYTHING, call these tools:

```python
# Check existing features
feature_get_stats()
# This shows how many features already exist
```

**Example output:**
```
Total features: 47
Passing: 32
Pending: 15
```

This means the project ALREADY HAS 47 features. DO NOT recreate them!

#### 2. **Read the Previous Spec**

The iteration instructions will tell you where the backup is:
- Example: "Read `prompts/app_spec.txt.v2`"

Read this file to understand what already exists:
- What features were previously defined
- What the tech stack is
- What the project structure looks like

#### 3. **Update app_spec.txt (Don't Replace)**

Edit the CURRENT `prompts/app_spec.txt`:

**DO:**
- ✅ Keep all existing features in the `<features>` section
- ✅ Add new features based on iteration requirements
- ✅ Update the feature count: `OLD_COUNT + NEW_COUNT`
- ✅ Preserve existing overview, tech stack, success criteria

**DON'T:**
- ❌ Delete existing features
- ❌ Replace the entire spec
- ❌ Change the tech stack without being asked
- ❌ Renumber existing features

**Example:**

If app_spec.txt.v2 had 47 features, and iteration asks for "user profiles", you should:
1. Copy all 47 existing features
2. Add ~10 new features for user profiles
3. Update total count to 57

#### 4. **Create ONLY New Features**

When calling `feature_create_bulk`:

```python
# WRONG - This would recreate ALL features
feature_create_bulk([
    {"name": "Login page", ...},  # Already exists!
    {"name": "Dashboard", ...},    # Already exists!
    {"name": "User profile", ...}, # NEW
])

# CORRECT - Only new features
feature_create_bulk([
    {"name": "User profile view", "priority": 48, ...},    # NEW
    {"name": "Edit profile form", "priority": 49, ...},    # NEW
    {"name": "Avatar upload", "priority": 50, ...},        # NEW
])
```

**Priority numbering:**
- The iteration instructions will tell you the next priority number
- Example: "Set priority starting from 48"
- This ensures new features queue AFTER existing ones

#### 5. **DO NOT Recreate Project Structure**

In iteration mode:

**DO NOT:**
- ❌ Run init.sh again
- ❌ Overwrite package.json
- ❌ Recreate README.md
- ❌ Delete existing source code
- ❌ Reinitialize git repository

**ONLY:**
- ✅ Update app_spec.txt
- ✅ Create new feature definitions in the database
- ✅ Commit the spec update

#### 6. **Validation Checklist**

Before calling `feature_create_bulk`, verify:

- [ ] I called `feature_get_stats()` and know the existing count
- [ ] I read the previous spec backup
- [ ] I edited app_spec.txt to include both old and new features
- [ ] I'm creating ONLY new features (not duplicates)
- [ ] Priority numbers start from NEXT_PRIORITY (provided in instructions)
- [ ] Feature count in spec matches: old count + new count

#### 7. **Git Commit Message**

When committing changes in iteration mode:

```bash
git commit -m "Iteration vN: Add [brief description]

- Updated app_spec.txt (preserved existing features)
- Created N new features for [capability]
- Total features: [OLD] → [NEW]"
```

---

### Example Iteration Workflow

**Given:**
- Existing project with 47 features
- Iteration request: "Add export/import functionality"

**Steps:**

1. **Read state:**
   ```python
   stats = feature_get_stats()
   # Output: 47 total features
   ```

2. **Read previous spec:**
   ```python
   # Read prompts/app_spec.txt.v2
   # Understand existing features 1-47
   ```

3. **Update current spec:**
   ```xml
   <features count="62">  <!-- 47 old + 15 new -->
     <!-- Feature 1-47: Existing features (copied) -->
     <feature id="1">Login page</feature>
     ...
     <feature id="47">Settings page</feature>

     <!-- Feature 48-62: New export/import features -->
     <feature id="48">Export board to CSV</feature>
     <feature id="49">Import board from CSV</feature>
     ...
   </features>
   ```

4. **Create ONLY new features:**
   ```python
   feature_create_bulk([
       {
           "category": "functional",
           "name": "Export board to CSV",
           "priority": 48,
           ...
       },
       {
           "category": "functional",
           "name": "Import board from CSV",
           "priority": 49,
           ...
       },
       # ... 13 more new features
   ])
   ```

5. **Commit:**
   ```bash
   git add prompts/app_spec.txt
   git commit -m "Iteration v3: Add export/import functionality

   - Updated app_spec.txt (preserved 47 existing features)
   - Created 15 new features for export/import
   - Total features: 47 → 62"
   ```

---

### Common Mistakes in Iteration Mode

**Mistake 1: Recreating all features**
```python
# WRONG
feature_create_bulk([all_47_old_features + 15_new_features])
# This creates 62 features, duplicating the existing 47!
```

**Mistake 2: Not checking existing count**
```python
# WRONG - blindly creating without checking
feature_create_bulk([new_features])
# What if features already exist? Duplicates!
```

**Mistake 3: Starting priority from 1**
```python
# WRONG
{"name": "Export CSV", "priority": 1}  # Conflicts with existing!

# CORRECT
{"name": "Export CSV", "priority": 48}  # After existing 47
```

**Mistake 4: Replacing app_spec.txt**
```python
# WRONG - deletes existing features
spec_content = generate_new_spec_from_scratch()

# CORRECT - edit to add new features
current_spec = read_file("prompts/app_spec.txt")
updated_spec = current_spec + new_features_section
```

---

### When NOT in Iteration Mode

If you DON'T see iteration instructions:
- This is a standard greenfield project
- Follow normal initialization workflow
- Create all features from scratch
- Initialize project structure

---
```

---

## 2. Adicionar seção de troubleshooting

**Adicionar no final do template:**

```markdown
## 🐛 Troubleshooting Iteration Mode

### "I'm not sure if I'm in iteration mode"

Look for these signals in your prompt:
1. Header: `# Iteration vN Instructions`
2. References to backup files: `app_spec.txt.v2`
3. Context about existing feature count

If you see ANY of these, you're in iteration mode.

### "I accidentally created duplicate features"

If you realize you duplicated features:
1. STOP immediately
2. The features are already in the database
3. You cannot delete them (no delete tool exists)
4. Report to the user: "I accidentally duplicated features. The database now has duplicates. Manual cleanup needed."

**Prevention:** Always call `feature_get_stats()` FIRST.

### "The priority numbers are wrong"

Priority should be:
- Iteration instructions provide `NEXT_PRIORITY`
- Start from that number
- Increment by 1 for each new feature

Example:
```
Instructions say: "Set priority starting from 48"
Your features: priority 48, 49, 50, 51, ...
```

### "app_spec.txt is too large"

If the spec becomes very large (>10KB):
- Consider using feature categories instead of listing every detail
- Summarize existing features if needed
- Focus detail on NEW features only

---
```

---

## 3. Adicionar validação no início do prompt

**Modificar a seção inicial (após "YOU ARE..."):**

```markdown
## First Steps

Before starting, determine your mode:

1. **Check for iteration instructions:**
   - Is there a `# Iteration vN Instructions` section in this prompt?
   - YES → You're in **Iteration Mode** (see section below)
   - NO → You're in **Standard Mode** (create from scratch)

2. **If in Iteration Mode:**
   - Read the "ITERATION MODE" section carefully
   - Follow the special rules
   - Call `feature_get_stats()` before anything else

3. **If in Standard Mode:**
   - Follow normal initialization workflow
   - Create all features from scratch
```

---

# VALIDAÇÃO

Após modificação, teste:

1. **Greenfield (modo normal):**
   ```bash
   # Criar novo projeto
   python start.py
   # Deve funcionar como antes
   ```

2. **Brownfield (modo iteração):**
   ```bash
   # Criar iteração via UI (comando 02)
   # Rodar agent
   python autonomous_agent_demo.py --project-dir test-project
   ```

3. **Verificar comportamento do agent:**
   - ✅ Chama `feature_get_stats()` primeiro
   - ✅ Lê o backup do spec
   - ✅ Edita app_spec.txt (não substitui)
   - ✅ Cria apenas features novas
   - ✅ Prioridades começam do número correto

4. **Verificar database:**
   ```python
   import sqlite3
   conn = sqlite3.connect("features.db")
   cursor = conn.cursor()
   cursor.execute("SELECT id, priority, name FROM features ORDER BY priority")
   print(cursor.fetchall())
   # Não deve ter duplicatas
   # Prioridades devem ser sequenciais
   ```

---

# RESULTADO ESPERADO

Ao final desta etapa:
- ✅ Initializer reconhece modo iteração
- ✅ Instruções claras sobre preservação
- ✅ Validações previnem duplicação
- ✅ Features são adicionadas incrementalmente

**Sistema completo:** Brownfield support está funcional!

---

# PRÓXIMAS MELHORIAS (Opcionais)

Após funcionalidade básica:

1. **Comando 04:** UI de histórico de iterações
2. **Comando 05:** Rollback de iterações
3. **Comando 06:** Diff viewer entre versões de spec
4. **Comando 07:** Métricas de evolução do projeto