# OS / Runtime (Fundação) — `erpclaw-os`

> Spec funcional por ação. Gerada de `scripts/erpclaw-os/db_query.py`. 6 funcionalidades · 8 ações.

## Validação contra a Constituição

**Objetivo.** Valida um módulo contra os 21 artigos da Constituição Glue via análise estática (artigos 1-8, 10-12, 19-21) e execução de testes em sandbox (artigo 9).

### `validate-module`

Valida o diretório de um módulo contra a Constituição Glue, retornando aprovação/reprovação por artigo.

| | |
|---|---|
| **Entradas** | --module-path (obrigatório; caminho do diretório do módulo); --validation-type (default 'full'; choices static\|runtime\|full); --db-path (default None; banco de teste para o tipo runtime). |
| **Saídas** | JSON via ok() com result (pass\|fail), module_name, module_path, articles (mapa numero->pass\|fail\|skip), violations[], skipped[], duration_ms, validation_type; em 'full' inclui sub-objeto runtime e seta articles[9]. Em 'runtime' puro retorna result, tests_run, tests_passed, tests_failed, output. |
| **Regras** | Erro (err) se module_path não for diretório existente. static/full roda validate_module_static (14 checagens de artigo). runtime/full roda validate_module_runtime que invoca pytest no tests/. Em 'full', se runtime falhar seta result='fail' e articles[9]='fail', senão articles[9]='pass'. runtime sem tests/ retorna fail; pytest com timeout de 120s vira fail. |
| **Efeitos colaterais** | Nenhum (leitura) no banco principal: só lê arquivos do módulo (SKILL.md, init_db.py) e roda pytest em subprocesso. Não escreve tabelas, gl_entry/SLE/PLE, status nem audit_log; o runtime pode escrever em banco de teste isolado via ERPCLAW_DB_PATH. |
| **Pré-condições** | module_path deve apontar para diretório existente do módulo; para validação runtime/full o módulo precisa de um diretório tests/ com testes pytest. |

### `list-articles`

Lista os artigos da Constituição (todos, ou somente os de enforcement estático ou runtime).

| | |
|---|---|
| **Entradas** | --article-type (default 'all'; choices all\|static\|runtime). Sem flags obrigatórias. |
| **Saídas** | JSON via ok() com articles (lista de dicts: number, name, description, enforcement, severity, bypass_policy) e count. |
| **Regras** | article_type='static' retorna artigos 1-8,10-12,19-21; 'runtime' retorna 9,13-18; 'all' retorna todos os 21. Filtro feito por enforcement==static/runtime sobre a lista ARTICLES. |
| **Efeitos colaterais** | Nenhum (leitura). Apenas lê a constante ARTICLES em memória. |
| **Pré-condições** | Nenhuma além do módulo constitution.py estar importável. |

## Registro de Tabelas

**Objetivo.** Constrói o registro de propriedade (ownership) de tabelas mapeando cada tabela ao módulo dono, usado para impor proteção contra escritas cross-module.

### `build-table-registry`

Constrói e exibe o registro de propriedade de tabelas (tabela -> módulo dono) varrendo a árvore de fontes.

| | |
|---|---|
| **Entradas** | --src-root (obrigatório; raiz do diretório source/ a varrer). |
| **Saídas** | JSON via ok() com total_tables, total_modules, registry (mapa tabela->módulo) e by_module (mapa módulo->lista de tabelas, ordenado). |
| **Regras** | Erro (err) se src_root não for diretório existente. Varre erpclaw-setup/init_schema.py atribuindo tabelas ao dono 'erpclaw', depois todos os init_db.py sob src_root atribuindo ao módulo derivado do diretório; pula __pycache__/.git e o init_schema do core. Tabelas extraídas por regex CREATE TABLE IF NOT EXISTS. |
| **Efeitos colaterais** | Nenhum (leitura). Só lê arquivos init_schema.py/init_db.py do filesystem; não escreve no banco nem em audit_log. |
| **Pré-condições** | src-root deve ser diretório existente; tabelas só são detectadas em arquivos init_db.py / init_schema.py com DDL CREATE TABLE IF NOT EXISTS. |

## Plano de Migração

**Objetivo.** Gera um plano de migração comparando o init_db.py declarado do módulo com o schema vivo do banco, validando e gravando um registro 'planned'.

### `schema-plan`

Gera um plano de migração (DDL de CREATE TABLE) para sincronizar o banco com o init_db.py do módulo.

| | |
|---|---|
| **Entradas** | --module-path (obrigatório; deve conter init_db.py); --db-path (default ~/.openclaw/erpclaw/data.sqlite); --src-root (opcional; habilita checagem de conflito cross-module). |
| **Saídas** | dict com result (planned\|no_changes\|blocked\|error), e em sucesso: migration_id, module_name, new_tables, new_columns, ddl_count, ddl_statements, validation_passed, validation_result, duration_ms. (Obs: o router de db_query.py descarta o dict retornado — nada é impresso no stdout.) |
| **Regras** | Erro se faltar init_db.py. Só novas tabelas/colunas contam como mudança acionável; sem mudanças retorna no_changes. Se src_root dado, bloqueia (result='blocked') ADD column / DROP de tabelas de outro dono no registro de ownership. Gera DDL só para new_tables (tipo mais seguro), roda validate_module_static e snapshot do schema atual. |
| **Efeitos colaterais** | ESCREVE no banco: cria a tabela erpclaw_schema_migration (se ausente) e INSERE 1 registro com status 'planned' (migration_type='create', ddl_statements, previous_schema snapshot, planned_at). Não toca tabelas de negócio, gl_entry/SLE/PLE nem audit_log. |
| **Pré-condições** | module-path com init_db.py; banco SQLite acessível; para detecção de conflito, src-root válido com registro de ownership. |

## Aplicar/Reverter Migrações

**Objetivo.** Executa em transação o DDL de uma migração planejada (apply) ou reverte uma migração aplicada derrubando as tabelas criadas e fazendo backup dos dados (rollback).

### `schema-apply`

Executa o DDL de uma migração com status 'planned' dentro de uma única transação.

| | |
|---|---|
| **Entradas** | --migration-id (lido via getattr, obrigatório para o handler); --db-path (default ~/.openclaw/erpclaw/data.sqlite). OBS: o parser de db_query.py NÃO define --migration-id, então na prática o handler sempre recebe None e retorna o erro de flag obrigatória. |
| **Saídas** | dict com result (applied\|error), e em sucesso: migration_id, module_name, tables_created, ddl_executed, duration_ms; erro inclui error e migration_id. (Router descarta o retorno — sem impressão.) |
| **Regras** | Sem migration_id retorna {error}. Migração inexistente ou com status != 'planned' retorna error. Executa cada DDL; rastreia tabelas via regex CREATE TABLE. Em falha sqlite3.Error: marca registro como 'failed', faz commit e retorna error; em sucesso marca 'applied' com applied_at e applied_by (default 'system'). |
| **Efeitos colaterais** | ESCREVE no banco: executa os DDL CREATE TABLE/INDEX da migração (cria tabelas reais) e ATUALIZA o status do registro em erpclaw_schema_migration para 'applied' (ou 'failed' em erro). Não posta em gl_entry/SLE/PLE nem audit_log. |
| **Pré-condições** | Existir registro em erpclaw_schema_migration com status 'planned' (criado por schema-plan) e o migration_id correspondente. |

### `schema-rollback`

Reverte uma migração 'applied' do tipo create, fazendo backup dos dados e derrubando as tabelas criadas.

| | |
|---|---|
| **Entradas** | --migration-id (lido via getattr, obrigatório para o handler); --db-path (default ~/.openclaw/erpclaw/data.sqlite). OBS: o parser de db_query.py NÃO define --migration-id, então na prática o handler sempre recebe None e retorna o erro de flag obrigatória. |
| **Saídas** | dict com result (rolled_back\|error), e em sucesso: migration_id, module_name, tables_dropped, backups_created (lista de {original, backup, rows}), duration_ms. (Router descarta o retorno — sem impressão.) |
| **Regras** | Sem migration_id retorna {error}. Migração inexistente ou com status != 'applied' retorna error. Para migration_type='create': se a tabela tem linhas, copia para {tabela}_backup_{id[:8]} antes; depois DROP TABLE IF EXISTS. Falha sqlite3.Error retorna error sem commit. |
| **Efeitos colaterais** | ESCREVE no banco: cria tabelas de backup (CREATE TABLE AS SELECT) para tabelas com dados, faz DROP das tabelas criadas pela migração, e ATUALIZA o registro em erpclaw_schema_migration para 'rolled_back' com rolled_back_at. Não posta em gl_entry/SLE/PLE nem audit_log. |
| **Pré-condições** | Existir registro em erpclaw_schema_migration com status 'applied' (aplicado por schema-apply) e o migration_id correspondente. |

## Detecção de Drift

**Objetivo.** Detecta divergências (drift) entre o schema vivo do banco e o schema declarado no init_db.py do módulo.

### `schema-drift`

Detecta modificações manuais no banco que divergem do schema declarado em init_db.py do módulo.

| | |
|---|---|
| **Entradas** | --module-path (obrigatório; deve conter init_db.py); --db-path (default ~/.openclaw/erpclaw/data.sqlite). |
| **Saídas** | dict com result (drift_detected\|no_drift), findings (lista de {type, table, column?, details}), finding_count, module_path, duration_ms. (Router descarta o retorno — sem impressão.) |
| **Regras** | Sem module_path retorna {error}. Sem init_db.py retorna lista vazia (no_drift). Compara via diff_schema e classifica achados: extra_table (só para tabelas com o prefixo do módulo), missing_column, extra_column, type_mismatch. |
| **Efeitos colaterais** | Nenhum (leitura). Apenas consulta sqlite_master/PRAGMA table_info e lê init_db.py; não escreve tabelas, gl_entry/SLE/PLE, status nem audit_log. |
| **Pré-condições** | module-path com init_db.py e banco SQLite acessível para comparação. |

## Ações Movidas para Addon (erpclaw-os-engine)

**Objetivo.** Stubs para ~29 ações de geração/deploy/evolução DGM que foram movidas para o addon externo erpclaw-os-engine, retornando erro estruturado de addon ausente neste fork air-gapped.

### `handle_moved_to_addon (generate-module, configure-module, list-industries, classify-operation, deploy-module, deploy-audit-log, install-suite, run-audit, compliance-weather-status, log-improvement, list-improvements, review-improvement, semantic-check, semantic-rules-list, dgm-run-variant, dgm-list-variants, dgm-select-best, detect-gaps, detect-schema-divergence, detect-stubs, suggest-modules, heartbeat-analyze, heartbeat-report, heartbeat-suggest, add-feature-to-module, check-feature-completeness, list-feature-matrix, research-business-rule, get-implementation-guide)`

Para qualquer uma das ~29 ações listadas em MOVED_ACTIONS_TO_ADDON, retorna erro estruturado indicando que a ação migrou para o addon erpclaw-os-engine.

| | |
|---|---|
| **Entradas** | --action com um dos nomes movidos (obrigatório; aceito pelo parser pois consta em all_known). Nenhuma outra flag é processada antes do desvio. |
| **Saídas** | JSON de erro (print direto + exit 1) com status='error', error, missing_addon='erpclaw-os-engine', old_action, new_action (nome os-prefixado), note e since_version='4.0.0'. |
| **Regras** | Roteado antes de qualquer outra ação: se action está em MOVED_ACTIONS_TO_ADDON, chama handle_moved_to_addon e encerra. Mapeia o nome antigo para o novo (prefixo 'os-'). Sempre falha; nunca executa a lógica real (que vive no addon externo não empacotado). |
| **Efeitos colaterais** | Nenhum (leitura). Apenas imprime JSON de erro e faz sys.exit(1); não escreve no banco nem em audit_log. |
| **Pré-condições** | Nenhuma; o comportamento é independente de estado, sempre retorna o erro de addon ausente. |

