# Comando 03 - Validação e Testes

## Status: ✅ COMPLETO

O template do Initializer Agent foi atualizado com suporte completo para modo iteração (brownfield).

---

## Mudanças Realizadas

### 1. Atualização do Template (`.claude/templates/initializer_prompt.template.md`)

**Seções adicionadas:**

- **FIRST: Determine Your Mode** - Detecção inicial do modo (greenfield vs brownfield)
- **🔄 ITERATION MODE (Brownfield Projects)** - Guia completo com:
  - Detecção de modo iteração
  - Regras especiais (8 seções)
  - Exemplo de workflow completo
  - Erros comuns a evitar
- **🐛 Troubleshooting Iteration Mode** - Solução de problemas

**Total:** +299 linhas adicionadas (524 → 823 linhas)

---

## Fluxo de Funcionamento

### Quando o Agent é Executado

1. **Check de Iteração** (`agent.py:150-162`)
   ```python
   iteration_files = sorted(prompts_dir.glob("iteration_v*_instructions.md"))
   if iteration_files:
       iteration_file = iteration_files[-1]
       is_first_run = True  # Force initializer mode
   ```

2. **Carregamento do Prompt** (`agent.py:200-208`)
   ```python
   if iteration_file:
       iteration_instructions = iteration_file.read_text()
       base_prompt = get_initializer_prompt(project_dir)
       prompt = f"{base_prompt}\n\n---\n\n{iteration_instructions}"
   ```

3. **Template Base** (`.claude/templates/initializer_prompt.template.md`)
   - Contém seção "ITERATION MODE" com todas as instruções
   - Agent vê as instruções de iteração E o conteúdo do arquivo de iteração

4. **Arquivo de Iteração** (`prompts/iteration_vN_instructions.md`)
   - Criado por `iteration_manager.create_iteration()`
   - Contém contexto específico:
     - Feature count existente
     - Próximo priority number
     - Path do backup do spec
     - Requisitos da expansão

---

## Validação Manual

### Teste 1: Greenfield (Modo Normal)

**Passos:**
1. Criar novo projeto via UI ou CLI
2. Verificar que NÃO há arquivos `iteration_v*_instructions.md`
3. Rodar agent: `python autonomous_agent_demo.py --project-dir test-project`

**Resultado Esperado:**
- ✅ Agent usa modo standard
- ✅ Cria todas features do zero
- ✅ Inicializa estrutura do projeto

### Teste 2: Brownfield (Modo Iteração)

**Pré-requisitos:**
- Projeto existente com features (comando 01 completo)
- UI de criação de iteração (comando 02 completo)

**Passos:**
1. Abrir UI em projeto existente
2. Clicar "Add Iteration"
3. Preencher requisitos de expansão
4. Salvar (cria arquivo `iteration_v1_instructions.md`)
5. Rodar agent: `python autonomous_agent_demo.py --project-dir test-project`

**Resultado Esperado:**
- ✅ Agent detecta arquivo de iteração
- ✅ Carrega prompt base + instruções de iteração
- ✅ Chama `feature_get_stats()` primeiro
- ✅ Lê backup do spec (`app_spec.txt.v1`)
- ✅ Edita `app_spec.txt` (não substitui)
- ✅ Cria apenas features novas com priority correto
- ✅ NÃO recria estrutura do projeto

### Teste 3: Validação de Database

**Verificar que não há duplicatas:**

```python
import sqlite3

conn = sqlite3.connect("test-project/features.db")
cursor = conn.cursor()

# Verificar sequência de priorities
cursor.execute("SELECT priority, name FROM features ORDER BY priority")
features = cursor.fetchall()

# Checar se há gaps ou duplicatas
priorities = [f[0] for f in features]
assert priorities == list(range(1, len(priorities) + 1)), "Priorities must be sequential"

print(f"✅ {len(features)} features with sequential priorities")
conn.close()
```

---

## Checklist de Validação

### Template

- [x] Seção "FIRST: Determine Your Mode" adicionada
- [x] Seção "ITERATION MODE" completa com 8 regras
- [x] Exemplo de workflow incluído
- [x] Erros comuns documentados
- [x] Seção de troubleshooting adicionada
- [x] Template tem 823 linhas (original: 524)

### Integração

- [x] `agent.py` detecta arquivos de iteração
- [x] `agent.py` carrega instruções corretamente
- [x] `prompts.py` tem fallback chain funcionando
- [x] `iteration_manager.py` cria arquivos com contexto correto

### Comportamento do Agent (para testar)

- [ ] Agent detecta modo iteração automaticamente
- [ ] Agent chama `feature_get_stats()` primeiro
- [ ] Agent lê backup do spec
- [ ] Agent edita (não substitui) `app_spec.txt`
- [ ] Agent cria apenas features novas
- [ ] Agent usa priority correto
- [ ] Agent NÃO recria estrutura do projeto
- [ ] Database não tem duplicatas

---

## Exemplos de Output Esperado

### Modo Greenfield (Normal)

```
Fresh start - will use initializer agent
==================================================
  NOTE: First session takes 10-20+ minutes!
  The agent is generating 200 detailed test cases.
==================================================

Session 1
================
[Tool: feature_create_bulk] Creating 250 features...
```

### Modo Brownfield (Iteração)

```
⚠️  Found iteration instructions: iteration_v2_instructions.md
Will run in ITERATION mode (preserving existing features)

Fresh start - will use initializer agent
==================================================
Session 1
================
[Tool: feature_get_stats]
Total features: 47
Passing: 32
Pending: 15

[Agent reads prompts/app_spec.txt.v2]
[Agent edits prompts/app_spec.txt]
[Tool: feature_create_bulk] Creating 15 NEW features (priority 48-62)...

✅ Loaded iteration instructions (deleted iteration_v2_instructions.md)
```

---

## Debugging

### Ver conteúdo do prompt final

Para debug, adicionar em `agent.py:204`:

```python
print("="*70)
print("FINAL PROMPT:")
print("="*70)
print(prompt)
print("="*70)
```

### Verificar se template está correto

```bash
# Contar seções de iteração
grep -c "ITERATION MODE\|Example Iteration Workflow\|Common Mistakes\|Troubleshooting" \
  .claude/templates/initializer_prompt.template.md

# Deve retornar 4
```

### Verificar arquivo de iteração

```bash
cat test-project/prompts/iteration_v1_instructions.md

# Deve conter:
# - feature_count
# - next_priority
# - Expansion requirements
```

---

## Próximos Passos

Após validação manual bem-sucedida:

1. ✅ Comando 03 completo
2. ⏭️ Comando 04: Adicionar comando `/brownfield` ao CLI
3. ⏭️ Opcional: Histórico de iterações na UI
4. ⏭️ Opcional: Rollback de iterações
5. ⏭️ Opcional: Diff viewer entre versões

---

## Notas de Implementação

### Por que o Template Base é Modificado?

Opção 1: Modificar template base (ESCOLHIDA ✅)
- Vantagens:
  - Instruções sempre presentes
  - Não requer lógica adicional
  - Funciona mesmo se arquivo de iteração for corrompido

Opção 2: Instruções apenas no arquivo de iteração
- Desvantagens:
  - Duplicação de conteúdo
  - Risco de instruções divergirem
  - Mais difícil de manter

### Por que o Arquivo de Iteração é Deletado?

```python
iteration_file.unlink()  # agent.py:207
```

Razões:
1. Previne execução acidental duas vezes
2. Iteração é "consumida" após uso
3. Backups preservam histórico
4. Force usuário a criar nova iteração intencionalmente

---

## Estrutura Final

```
autocoder/
├── .claude/
│   └── templates/
│       └── initializer_prompt.template.md  ✅ ATUALIZADO (823 linhas)
├── agent.py                                ✅ JÁ TINHA SUPORTE
├── prompts.py                              ✅ JÁ TINHA FALLBACK
├── server/
│   └── services/
│       └── iteration_manager.py            ✅ JÁ CRIA ARQUIVOS
└── docs/
    └── COMANDO_03_VALIDATION.md            ✅ NOVO (este arquivo)
```

---

## Resumo

### Antes do Comando 03

- Template não tinha instruções de iteração
- Agent carregava arquivo mas sem contexto
- Risco de duplicação de features

### Depois do Comando 03

- ✅ Template com seção completa de ITERATION MODE
- ✅ 8 regras específicas com exemplos
- ✅ Workflow de exemplo end-to-end
- ✅ Erros comuns documentados
- ✅ Troubleshooting guide
- ✅ Previne duplicação via validação

**Status:** PRONTO PARA TESTES 🎉