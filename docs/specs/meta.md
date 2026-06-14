# Meta / Transversal — `erpclaw-meta`

> Spec funcional por ação. Gerada de `scripts/erpclaw-meta/db_query.py`. 4 funcionalidades · 4 ações.

## Verificacao de Instalacao

**Objetivo.** Inspeciona quais skills ERPClaw estao instaladas, o estado do banco e a saude da biblioteca compartilhada.

### `check-installation`

Varre as skills instaladas, o estado do banco e a presenca da biblioteca compartilhada, reportando contagens e versoes.

| | |
|---|---|
| **Entradas** | --db-path (default ~/.openclaw/erpclaw/data.sqlite). Sem flags obrigatorias. |
| **Saídas** | JSON com status, total_skills_available, installed_skills [{name, version, tables_ok}], installed_count, missing_skills, missing_count, database_exists, database_tables, company_count, shared_library_installed, db_path, skills_dir. |
| **Regras** | Itera sobre ALL_SKILLS (26 nomes); para cada uma le a versao do SKILL.md via regex no frontmatter e calcula tables_ok verificando se as tabelas esperadas (SKILL_TABLES) existem no banco; skills sem tabelas proprias sao tables_ok=True. Erros de sqlite sao silenciados (relata o que conseguir). Sempre retorna status ok. |
| **Efeitos colaterais** | nenhum (leitura): apenas le sqlite_master e a tabela company, lista ~/clawd/skills e le arquivos SKILL.md. |
| **Pré-condições** | Nenhuma; funciona standalone sem PyPika. O banco e a pasta de skills podem nao existir (campos refletem isso). |

## Guia de Onboarding

**Objetivo.** Recomenda a proxima tier/skills a instalar com base no estado atual da instalacao.

### `install-guide`

Avalia o progresso por tier e recomenda a proxima skill/tier a instalar com o comando clawhub correspondente.

| | |
|---|---|
| **Entradas** | --db-path (default ~/.openclaw/erpclaw/data.sqlite). Sem flags obrigatorias. |
| **Saídas** | JSON com status, current_tier, next_recommendation, install_command, progress (texto 'X of Y (Z%)'), database_exists, company_count, tiers [{name, skills, installed, missing, status, install_cmd}]. |
| **Regras** | Classifica cada tier (8 tiers em TIERS) como complete/partial/not_started. Identifica o primeiro tier incompleto; se nada instalado recomenda Tier 1, se tier parcial monta comando so com as skills faltantes, se tudo completo retorna mensagem final. Percentual calculado sobre ALL_SKILLS. Sempre retorna status ok. |
| **Efeitos colaterais** | nenhum (leitura): le sqlite_master/company e lista skills instaladas em ~/clawd/skills. |
| **Pré-condições** | Nenhuma; funciona standalone sem PyPika. Banco e pasta de skills opcionais. |

## Geracao de Dados de Demo

**Objetivo.** Cria um conjunto completo e idempotente de dados de demonstracao orquestrando subprocessos das demais skills.

### `seed-demo-data`

Popula uma empresa de demonstracao (Stark Manufacturing, ou empresa existente via --company-id) com dados de ponta a ponta em todos os modulos.

| | |
|---|---|
| **Entradas** | --db-path (default ~/.openclaw/erpclaw/data.sqlite); --company-id (opcional: usa empresa existente em vez de criar a Stark). |
| **Saídas** | JSON com status (ok/partial), message, company_id, summary (contagens por entidade: customers, suppliers, items, warehouses, stock_entries, journal_entries, sales_orders/invoices, purchase_orders/receipts/invoices, payments, boms, work_orders, employees, leads, opportunities, assets, support_issues, projects, tasks etc.) e errors/error_count quando houver falhas parciais. |
| **Regras** | Idempotente: se a empresa-alvo ja tem customers (>0) retorna 'already exists' sem reescrever; com --company-id inexistente retorna erro 'Company not found'. Executa fases sequenciais (setup, COA us_gaap, fiscal years, cost centers, master data, opening stock, JEs, SO/SI, PO/PR/PI, pagamentos, manufatura, HR/payroll, CRM, assets, support, projetos) via subprocesso a cada db_query.py de skill; cada fase captura excecoes em errors e continua. Se setup-company falha, tenta recuperar usando qualquer empresa existente; se nem assim ha company_id, retorna erro fatal. |
| **Efeitos colaterais** | Escreve massivamente no banco INDIRETAMENTE: cada acao chamada via subprocesso grava em suas tabelas e faz postagens reais. Inclui submit de stock entries (stock_ledger_entry + gl_entry), submit de journal entries / sales+purchase invoices (gl_entry), submit de payments (gl_entry/payment_entry_reference), alem de criar company, contas, items, warehouses, customers/suppliers, BOMs, work orders, employees, salary structures, leads/opportunities, assets, SLAs/issues, projects/tasks. audit_log e demais efeitos sao produzidos pelas skills subjacentes. |
| **Pré-condições** | Requer PyPika/erpclaw_lib instalado e as skills referenciadas presentes em ~/clawd/skills (ou nos pacotes v2 erpclaw-ops/erpclaw-growth); _find_skill_script localiza cada script e lanca erro 'not found' se ausente. Para --company-id, a empresa deve existir. |

## Setup Web Dashboard

**Objetivo.** Acao de setup do dashboard web, agora migrada para o addon externo erpclaw-os-engine (stub de migracao nesta versao air-gapped).

### `setup-web-dashboard`

Stub que informa que o setup do dashboard web foi movido para o addon erpclaw-os-engine (renomeado para os-setup-web-dashboard).

| | |
|---|---|
| **Entradas** | Flags ainda declaradas no parser mas ignoradas: --domain (default None), --ssl/--no-ssl (default None), --skip-build (default False); --db-path tambem aceito. |
| **Saídas** | JSON de erro com status=error, error, missing_addon=erpclaw-os-engine, old_action=setup-web-dashboard, new_action=os-setup-web-dashboard, note, since_version=4.0.0. |
| **Regras** | Sempre retorna erro estruturado e encerra com exit 1; nao executa nenhuma logica de clone/build/nginx (removida por seguranca apos flag do VirusTotal Code Insight). O addon nao esta empacotado neste fork air-gapped. |
| **Efeitos colaterais** | nenhum (apenas imprime JSON de erro e faz sys.exit(1)); nao toca banco, filesystem nem rede. |
| **Pré-condições** | Nenhuma; o stub responde independentemente do estado do ambiente. |

