# Meta / Transversal — `erpclaw-meta`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-meta/db_query.py`. 4 funcionalidades · 4 ações.

## Verificação de Instalação

**Objetivo.** Diagnostica o estado da instalação do ERPClaw: quais skills estão instaladas, qual a versão de cada uma, se o banco existe e se as tabelas esperadas de cada skill estão presentes. Serve de ponto de entrada padrão (sem dependências além da stdlib).

**Ações:**
- `check-installation` — Varre ~/clawd/skills procurando diretórios erpclaw-*/webclaw com SKILL.md, lê a versão do frontmatter YAML, confere as tabelas esperadas de cada skill (mapa SKILL_TABLES) contra as tabelas existentes no banco e verifica a presença da biblioteca compartilhada.

| Campo | Detalhe |
|---|---|
| **Entradas** | --action check-installation; --db-path (opcional, padrão ~/.openclaw/erpclaw/data.sqlite). |
| **Saídas** | JSON com status, total_skills_available, installed_skills (lista com name/version/tables_ok), installed_count, missing_skills, missing_count, database_exists, database_tables (contagem), company_count, shared_library_installed, db_path e skills_dir. |
| **Regras de negócio** | Itera sobre ALL_SKILLS (29 skills) classificando cada uma como instalada (diretório com SKILL.md presente) ou ausente. tables_ok é True quando todas as tabelas representativas da skill existem no banco, ou True por padrão para skills sem tabelas próprias (ex.: reports, regionais, webclaw). Versão extraída por regex do bloco frontmatter, sem biblioteca YAML. Se o banco estiver corrompido/bloqueado, reporta o que conseguir sem falhar. |
| **Efeitos colaterais** | nenhum (somente leitura). Apenas SELECT em sqlite_master e contagem da tabela company; nenhuma postagem em GL/gl_entry, SLE ou mudança de status. |
| **Pré-condições** | Nenhuma obrigatória — funciona mesmo sem banco, sem skills e sem a lib compartilhada (PyPika é opcional). Para contar empresas e validar tabelas, o banco precisa existir em --db-path. |

## Guia de Onboarding

**Objetivo.** Recomenda a próxima etapa de instalação com base no estado atual, organizando as 29 skills em tiers (Foundation, Core Accounting, Supply Chain, Operations, Extended, Regional, Integrations, Web Dashboard) e indicando o comando clawhub install a executar.

**Ações:**
- `install-guide` — Calcula o status de cada tier (complete/partial/not_started) a partir das skills instaladas, identifica o primeiro tier incompleto, monta a recomendação e o comando de instalação correspondente, além do percentual de progresso.

| Campo | Detalhe |
|---|---|
| **Entradas** | --action install-guide; --db-path (opcional, padrão ~/.openclaw/erpclaw/data.sqlite). |
| **Saídas** | JSON com status, current_tier, next_recommendation (texto), install_command (comando clawhub sugerido), progress ('X of Y skills installed (Z%)'), database_exists, company_count e tiers (lista com name/skills/installed/missing/status/install_cmd). |
| **Regras de negócio** | Tier é 'complete' se nada falta, 'not_started' se nada instalado, 'partial' caso intermediário. Se nada instalado, recomenda Tier 1 (Foundation). Se há tiers incompletos, recomenda o primeiro: quando 'partial', sugere instalar apenas as skills faltantes (clawhub install <faltantes>); quando 'not_started', sugere o install_cmd completo do tier. Se tudo instalado, retorna 'All tiers complete' sem comando. |
| **Efeitos colaterais** | nenhum (somente leitura). Lê apenas existência do banco e contagem de empresas via get_db_info; nenhuma escrita. |
| **Pré-condições** | Nenhuma obrigatória. Os diretórios das skills são lidos de ~/clawd/skills e o banco de --db-path apenas para enriquecer a saída (database_exists/company_count). |

## Geração de Dados de Demo

**Objetivo.** Popula um conjunto completo de dados de demonstração ponta a ponta para uma empresa, orquestrando subprocessos das demais skills, de modo a permitir testar relatórios e fluxos com lançamentos reais. Idempotente por empresa.

**Ações:**
- `seed-demo-data` — Cria/usa uma empresa e semeia em fases: defaults, plano de contas US GAAP, anos fiscais 2025/2026, naming series, centros de custo, 3 armazéns, 25 itens (15 RAW + 10 FG), 10 clientes, 8 fornecedores, estoque inicial, 5 lançamentos contábeis, 5 SO+SI, 3 PO+PR+PI, 5 pagamentos, 3 BOMs + 2 ordens de produção, RH/folha, CRM, ativos, suporte e projetos.

| Campo | Detalhe |
|---|---|
| **Entradas** | --action seed-demo-data; --db-path (opcional); --company-id (opcional — usa empresa existente em vez de criar 'Stark Manufacturing Inc.'). Demais flags são fixas no código (USD, United States, datas 2025/2026). |
| **Saídas** | JSON com status ('ok' se sem erros, 'partial' se houve falhas), message, company_id e summary (contagens por entidade: customers, suppliers, items, warehouses, stock_entries, journal_entries, sales/purchase orders+invoices, payments, boms, work_orders, employees, leads, assets, etc.). Em falhas parciais inclui errors[] e error_count. |
| **Regras de negócio** | Idempotente: se a empresa-alvo já existe e tem clientes (customer_count>0), retorna sem semear novamente. Com --company-id inexistente, retorna erro. Sem --company-id, procura 'Stark Manufacturing Inc%'; em caso de falha na criação, faz fallback para a empresa mais antiga existente. Documentos transacionais seguem o ciclo create→submit (estoque, JE, SO/SI, PO/PR/PI, pagamentos são submetidos). Cada passo é resiliente: duplicatas (UNIQUE) são puladas com lookup do registro existente, e erros isolados não abortam o lote — são acumulados em errors[]. |
| **Efeitos colaterais** | EFEITOS REAIS extensos via subprocessos das skills: submete stock entries (gera stock_ledger_entry / SLE de estoque inicial), submete journal entries, sales invoices e purchase invoices (geram gl_entry no Razão), submete pagamentos (gera payment_ledger_entry e quitação de faturas via allocations), cria/altera status de documentos (SO/PO/PR submetidos), além de mestres (empresa, contas, itens, clientes/fornecedores) e dados de RH/folha/CRM/ativos/suporte/projetos. Auditoria é registrada pelas próprias skills chamadas. |
| **Pré-condições** | As skills referenciadas precisam estar instaladas (setup, gl, inventory, selling, buying, journals, payments, manufacturing, hr, payroll, crm, assets, support, projects) — caso contrário o passo correspondente falha e entra em errors[]. Requer a lib compartilhada/PyPika para as consultas de idempotência e lookup de contas. Depende do plano de contas US GAAP (números de conta como 1111, 1121, 4110, 5110) para mapear os IDs usados nos lançamentos. |

## Setup Web Dashboard

**Objetivo.** Ponto de configuração do dashboard web. Nesta versão a ação foi removida desta skill de fundação e movida para o addon externo erpclaw-os-engine; o código aqui apenas devolve um erro estruturado de migração.

**Ações:**
- `setup-web-dashboard` — Stub de migração (_setup_web_dashboard_moved_stub): retorna JSON de erro informando que a ação foi renomeada para 'os-setup-web-dashboard' no addon erpclaw-os-engine e sai com código 1. Não executa nenhum trabalho.

| Campo | Detalhe |
|---|---|
| **Entradas** | --action setup-web-dashboard; flags ainda declaradas no parser mas não utilizadas pelo stub: --domain, --ssl/--no-ssl, --skip-build, --db-path. |
| **Saídas** | JSON de erro com status='error', error (mensagem de migração), missing_addon='erpclaw-os-engine', old_action='setup-web-dashboard', new_action='os-setup-web-dashboard', note (esclarece que o addon é tooling externo não empacotado neste fork air-gapped) e since_version='4.0.0'. Encerra com exit 1. |
| **Regras de negócio** | Sempre retorna o mesmo erro de migração, independentemente das flags. A implementação original (clone do erpclaw-web, npm install/build, venv da API, deploy/setup.sh, configuração de nginx + Let's Encrypt com sudo) foi removida por ter sido sinalizada como alto risco (VirusTotal Code Insight) e isolada no addon opcional, conforme o plano CLAWHUB_FIX_C_PLAN_2026-05-04 D6. |
| **Efeitos colaterais** | nenhum (somente retorna erro). Não clona repositório, não roda npm/build, não cria venv, não executa setup.sh e não toca em nginx/SSL nesta versão — todos esses efeitos foram deslocados para o addon externo. |
| **Pré-condições** | Nenhuma. Para de fato configurar o dashboard seria necessário instalar o addon externo erpclaw-os-engine e invocar 'os-setup-web-dashboard', que não está empacotado neste fork. |

