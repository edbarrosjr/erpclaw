# OS / Runtime (Fundação ERPClaw) — `erpclaw-os`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-os/db_query.py`. 6 funcionalidades · 18 ações.

## Validação contra a Constituição

**Objetivo.** Valida um módulo contra a Constituição do ERPClaw (21 artigos), combinando análise estática (artigos 1-8, 10-12, 19-21) e execução de testes em sandbox (artigo 9), para garantir conformidade antes de instalar/operar o módulo.

**Ações:**
- `validate-module` — Roteia a validação de um módulo; conforme --validation-type executa estática, runtime ou ambas (full) e mede duration_ms.
- `validate_module_static` — Roda os 14 checadores estáticos de artigo (prefixo de tabela, Money=TEXT, PK UUID, FKs, no cross-module/GL writes, formato de resposta, testes existem, security scan, SKILL.md, naming, escopo de modificação, proveniência, isolamento de feature) e agrega pass/fail.
- `validate_module_runtime` — Executa pytest no diretório tests/ do módulo (subprocess, timeout 120s) e parseia a contagem de passed/failed para validar o artigo 9 (Tests Pass).

| Campo | Detalhe |
|---|---|
| **Entradas** | --module-path (obrigatório, diretório do módulo); --validation-type (static\|runtime\|full, default full); --db-path (opcional, banco de teste exportado como ERPCLAW_DB_PATH para o pytest). |
| **Saídas** | JSON via ok() com result (pass\|fail), module_name, module_path, articles (mapa número->pass/fail/skip), violations[], skipped[], validation_type e duration_ms. No modo full inclui bloco runtime{} e fixa articles[9] como pass/fail. O runtime traz tests_run/passed/failed e output (últimos 2000 chars). |
| **Regras de negócio** | Estática cobre artigos 1-8,10-12,19-21; runtime cobre o 9. Resultado geral é fail se qualquer artigo crítico falhar. Checadores retornam skip quando faltam init_db.py/scripts/SKILL.md ou quando é módulo core. severity e bypass_policy (never/tier2/tier3) são metadados informativos — não há lógica de bypass no runtime. Caminho inexistente gera err. |
| **Efeitos colaterais** | Estática é somente leitura (lê init_db.py, SKILL.md, .py via AST e regex). Runtime tem efeito colateral real: dispara subprocess pytest que executa os testes do módulo; se --db-path for informado, os testes podem escrever nesse banco de teste (ERPCLAW_DB_PATH). Não posta em gl_entry nem stock_ledger_entry diretamente. |
| **Pré-condições** | Diretório do módulo existente com init_db.py e/ou SKILL.md; para runtime, diretório tests/ com testes pytest e pytest instalado. src_root é auto-detectado (pasta source/) para registro de propriedade de tabelas usado nos artigos 4 e 5. |

## Artigos

**Objetivo.** Expõe os 21 artigos da Constituição (regras de conformidade dos módulos) para consulta, com filtro por tipo de enforcement (estático vs runtime).

**Ações:**
- `list-articles` — Lista os artigos da Constituição; com --article-type filtra entre todos, somente estáticos (1-8,10-12,19-21) ou somente runtime (9,13-18).
- `get_static_articles` — Retorna apenas os artigos com enforcement='static'.
- `get_runtime_articles` — Retorna apenas os artigos com enforcement='runtime'.

| Campo | Detalhe |
|---|---|
| **Entradas** | --article-type (all\|static\|runtime, default all). |
| **Saídas** | JSON via ok() com articles[] (cada um: number, name, description, enforcement, severity, bypass_policy) e count. |
| **Regras de negócio** | Os artigos são uma constante estática (ARTICLES) definida em constitution.py. static = artigos verificados por análise; runtime = artigos 13-18 enforçados por triggers/APIs de banco mais o 9 (testes em sandbox). bypass_policy assume never/tier2/tier3 conforme o artigo. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Nenhuma — não depende de banco, empresa ou módulo. |

## Registro de Tabelas

**Objetivo.** Constrói o registro de propriedade de tabelas (qual módulo é dono de cada tabela) varrendo os init_db.py de todos os módulos e o init_schema.py do core, base para as regras anti cross-module/GL writes.

**Ações:**
- `build-table-registry` — Constrói e exibe o registro de propriedade, agrupando as tabelas por módulo para leitura.
- `build_table_ownership_registry` — Varre init_schema.py do core (dono='erpclaw') e todos os init_db.py sob src_root, extraindo nomes de tabela via regex e mapeando tabela->módulo (nome derivado do diretório).

| Campo | Detalhe |
|---|---|
| **Entradas** | --src-root (obrigatório, raiz source/ contendo os módulos). |
| **Saídas** | JSON via ok() com total_tables, total_modules, registry (mapa tabela->módulo) e by_module (mapa módulo->lista de tabelas). |
| **Regras de negócio** | Tabelas do core ficam atribuídas a 'erpclaw' (via erpclaw/scripts/erpclaw-setup/init_schema.py). Para os demais módulos, o dono é o nome derivado do diretório do init_db.py. Diretórios __pycache__/.git são ignorados e o init_schema do core não é recontado. Caminho inexistente gera err. |
| **Efeitos colaterais** | Nenhum (somente leitura de arquivos do filesystem). |
| **Pré-condições** | src_root existente apontando para a árvore source/ com os módulos e, idealmente, o init_schema.py do core para mapear as tabelas centrais. |

## Plano de Migração

**Objetivo.** Gera um plano de migração de schema (padrão Infrastructure-as-Code) comparando o init_db.py declarado de um módulo com o banco vivo, validando o módulo e registrando a migração como 'planned'.

**Ações:**
- `schema-plan` — Handler CLI que invoca plan_migration e anexa duration_ms ao resultado.
- `plan_migration` — Faz o diff (diff_schema), checa conflitos cross-module, gera DDL só para novas tabelas (generate_create_ddl), roda validação estática e insere o registro de migração.
- `diff_schema` — Compara o schema vivo (sqlite_master/PRAGMA) com o declarado, retornando new_tables, dropped_tables, new_columns, dropped_columns, type_changes e matching_tables.
- `ensure_migration_table` — Cria a tabela erpclaw_schema_migration se não existir (efeito DDL idempotente).

| Campo | Detalhe |
|---|---|
| **Entradas** | --module-path (obrigatório, contém init_db.py); --db-path (opcional, default ~/.openclaw/erpclaw/data.sqlite); --src-root (opcional, para checagem de propriedade/conflitos). |
| **Saídas** | dict com result (planned\|no_changes\|blocked\|error), migration_id, module_name, new_tables, new_columns, ddl_count, ddl_statements, validation_passed/validation_result e duration_ms. |
| **Regras de negócio** | Só new_tables e new_columns são acionáveis; dropped_tables são ignoradas (tabelas da fundação não declaradas). A IA pode CRIAR tabelas mas nunca ALTER/DROP de tabelas de outro módulo — havendo src_root, conflitos de propriedade retornam result='blocked'. Ciclo de vida inicia em status 'planned'. Sem mudanças acionáveis retorna 'no_changes'. Sem init_db.py retorna error. |
| **Efeitos colaterais** | Efeito colateral real no banco: cria a tabela erpclaw_schema_migration (se ausente) e INSERE uma linha com status 'planned', guardando ddl_statements e o snapshot do schema anterior (previous_schema). Não cria as tabelas-alvo ainda, não posta em GL nem em SLE. |
| **Pré-condições** | Banco SQLite acessível; módulo com init_db.py válido; para detectar conflitos cross-module, src_root com o registro de propriedade de tabelas. |

## Aplicar/Reverter Migrações

**Objetivo.** Aplica uma migração planejada executando o DDL dentro de uma transação, ou reverte uma migração aplicada removendo as tabelas criadas após salvar backup dos dados; ambos atualizam o status no registro de migração.

**Ações:**
- `schema-apply` — Handler CLI que invoca apply_migration por migration_id e anexa duration_ms.
- `apply_migration` — Carrega a migração 'planned', executa os DDL em uma transação, rastreia as tabelas criadas e atualiza o status para 'applied' (ou 'failed' em erro de SQL).
- `schema-rollback` — Handler CLI que invoca rollback_migration por migration_id e anexa duration_ms.
- `rollback_migration` — Para migrações tipo 'create', faz backup das linhas em tabelas _backup, dá DROP nas tabelas criadas e atualiza o status para 'rolled_back'.

| Campo | Detalhe |
|---|---|
| **Entradas** | --migration-id (obrigatório, UUID da migração); --db-path (opcional, default ~/.openclaw/erpclaw/data.sqlite); applied_by (opcional na função, default 'system'). |
| **Saídas** | apply: dict com result (applied\|error), migration_id, module_name, tables_created[], ddl_executed, duration_ms. rollback: dict com result (rolled_back\|error), tables_dropped[], backups_created[] (original, backup, rows), duration_ms. |
| **Regras de negócio** | apply exige status 'planned' (senão erro); falha de DDL faz rollback da transação e marca status 'failed'. rollback exige status 'applied'; só trata migration_type='create'. Backup só é gerado para tabelas com linhas (row_count>0), nomeado tabela_backup_<8charsId>. Ciclo de vida: planned -> applied -> rolled_back, ou planned -> failed. |
| **Efeitos colaterais** | Efeitos colaterais reais de DDL: apply executa CREATE TABLE/INDEX e altera o status da linha em erpclaw_schema_migration. rollback cria tabelas _backup (CREATE TABLE AS SELECT), executa DROP TABLE das tabelas criadas e muda o status. Tudo dentro de transação. Não posta diretamente em gl_entry/stock_ledger_entry; o impacto é estrutural no schema. |
| **Pré-condições** | Banco acessível com a tabela erpclaw_schema_migration e uma migração no status correto (planned para apply, applied para rollback). O DDL armazenado deve ser válido. |

## Detecção de Drift

**Objetivo.** Detecta drift de schema — modificações manuais no banco que divergem do schema declarado no init_db.py do módulo — listando tabelas/colunas/tipos fora de sincronia, sem alterar nada.

**Ações:**
- `schema-drift` — Handler CLI que chama detect_drift e monta o resultado com contagem e duração.
- `detect_drift` — Faz o diff entre banco e init_db.py e classifica as divergências em extra_table, missing_column, extra_column e type_mismatch.

| Campo | Detalhe |
|---|---|
| **Entradas** | --module-path (obrigatório, contém init_db.py); --db-path (opcional, default ~/.openclaw/erpclaw/data.sqlite). |
| **Saídas** | dict com result (drift_detected\|no_drift), findings[] (type, table, column quando aplicável, details), finding_count, module_path e duration_ms. |
| **Regras de negócio** | Tabelas presentes no banco mas ausentes no init_db.py só viram finding (extra_table) se usarem o prefixo do módulo (derivado do nome do diretório), evitando falsos positivos de outros módulos. Colunas declaradas e ausentes = missing_column; colunas extras no banco = extra_column; diferença de tipo = type_mismatch. Sem init_db.py retorna lista vazia (no_drift). |
| **Efeitos colaterais** | Nenhum (somente leitura: consulta sqlite_master/PRAGMA e lê init_db.py; não escreve no banco). |
| **Pré-condições** | Banco SQLite acessível e módulo com init_db.py para servir de schema declarado de referência. |

