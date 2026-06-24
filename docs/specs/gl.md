# Contabilidade (GL) — `glue-gl`

> Spec funcional por ação. Gerada de `scripts/glue-gl/db_query.py`. 13 funcionalidades · 31 ações.

## Plano de Contas

**Objetivo.** Criar, importar, consultar e atualizar contas contábeis e a hierarquia do plano de contas por empresa.

### `setup-chart-of-accounts`

Cria o plano de contas de uma empresa a partir de um template JSON de assets/charts.

| | |
|---|---|
| **Entradas** | --template (default 'us_gaap'); --company-id (obrigatório se houver mais de uma empresa; auto-detecta se houver só uma). |
| **Saídas** | accounts_created, template, company_id. |
| **Regras** | Falha se empresa não encontrada, se nenhuma empresa existe, se há múltiplas e --company-id ausente, ou se o template não existe em assets/charts/{template}.json. Resolve parent_id e depth via número da conta; pula contas cujo account_number já existe (idempotente). |
| **Efeitos colaterais** | INSERT em account (uma linha por conta nova: id, name, account_number, parent_id, root_type, account_type, is_group, balance_direction, company_id, depth); audit_log (import/account); commit. |
| **Pré-condições** | A empresa (company) deve existir e o arquivo de template do plano deve estar presente. |

### `add-account`

Cria uma única conta contábil (grupo ou postável) para uma empresa.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --company-id (obrigatório); --root-type (obrigatório: asset\|liability\|equity\|income\|expense); --account-type; --account-number; --parent-id; --currency (default 'USD'); --is-group (default false). |
| **Saídas** | status='created', account_id, name, account_number. |
| **Regras** | account_type em LEAF_ONLY_TYPES (receivable, payable, bank, cash, tax, cost_of_goods_sold, stock, depreciation, accumulated_depreciation, round_off) não pode ser grupo. account_type informado deve estar registrado e ativo em account_type_registry. balance_direction='credit_normal' para liability/equity/income, senão 'debit_normal'. depth = depth do pai +1 (erro se pai não existe). IntegrityError vira erro de duplicidade. |
| **Efeitos colaterais** | INSERT em account; audit_log (create/account); commit. |
| **Pré-condições** | Empresa existente; pai existente se --parent-id; account_type registrado/ativo se informado. |

### `update-account`

Atualiza campos editáveis de uma conta (nome, número, pai, congelamento).

| | |
|---|---|
| **Entradas** | --account-id (obrigatório); campos opcionais: --name, --account-number, --parent-id, --is-frozen. |
| **Saídas** | status='updated', account_id, updated_fields. |
| **Regras** | Erro se conta não existe ou se nenhum campo for fornecido. Faz lookup de existência de gl_entry não-cancelado (has_entries) mas o código não bloqueia mudanças com base nisso. --is-frozen é normalizado para 1/0. Seta updated_at. |
| **Efeitos colaterais** | UPDATE em account (campos enviados + updated_at) via dynamic_update; audit_log (update/account com old/new); commit. |
| **Pré-condições** | A conta deve existir. |

### `list-accounts`

Lista contas de uma empresa com filtros e paginação.

| | |
|---|---|
| **Entradas** | --company-id ou --company (nome, resolvido); --root-type; --account-type; --is-group; --parent-id; --search (name/account_number); --include-frozen (default false); --limit (default 20); --offset (default 0). |
| **Saídas** | accounts[], total_count, limit, offset, has_more. |
| **Regras** | Sem --include-frozen, filtra is_frozen=0 e disabled=0. Ordena por account_number depois name. total_count calculado antes do limit. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível por id ou nome. |

### `get-account`

Retorna uma conta com seu saldo calculado até uma data.

| | |
|---|---|
| **Entradas** | --account-id (obrigatório); --as-of-date (default: hoje UTC). |
| **Saídas** | account (todos os campos + balance, debit_total, credit_total). |
| **Regras** | Erro se conta não existe. Saldo = debit_total - credit_total se balance_direction='debit_normal', senão credit_total - debit_total, somando gl_entry não-cancelados com posting_date <= as_of. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | A conta deve existir. |

### `import-chart-of-accounts`

Importa contas de um arquivo CSV para uma empresa, complementando o setup por template.

| | |
|---|---|
| **Entradas** | --csv-path (obrigatório, .csv válido e arquivo regular); --company-id (obrigatório). Colunas CSV: name, root_type, account_number, account_type, parent_name, currency, is_group. |
| **Saídas** | imported, skipped, total_rows. |
| **Regras** | Valida extensão .csv, existência e schema via validate_csv('account'); erro se CSV inválido ou vazio. Pula contas cujo name já existe na empresa (skipped). Resolve parent por parent_name; balance_direction derivado do root_type; depth fixado em 0; currency default 'USD'. |
| **Efeitos colaterais** | INSERT em account (uma por linha importada); commit. NÃO grava audit_log. |
| **Pré-condições** | Empresa existente e arquivo CSV válido acessível. |

## Congelamento de Contas

**Objetivo.** Bloquear e desbloquear contas para postagem via flag is_frozen.

### `freeze-account`

Marca uma conta como congelada (is_frozen=1).

| | |
|---|---|
| **Entradas** | --account-id (obrigatório). |
| **Saídas** | status='updated', account_id, is_frozen=true. |
| **Regras** | Erro se a conta não existe. |
| **Efeitos colaterais** | UPDATE account.is_frozen=1 e updated_at; audit_log (freeze/account); commit. |
| **Pré-condições** | A conta deve existir. |

### `unfreeze-account`

Remove o congelamento de uma conta (is_frozen=0).

| | |
|---|---|
| **Entradas** | --account-id (obrigatório). |
| **Saídas** | status='updated', account_id, is_frozen=false. |
| **Regras** | Erro se a conta não existe. |
| **Efeitos colaterais** | UPDATE account.is_frozen=0 e updated_at; audit_log (unfreeze/account); commit. |
| **Pré-condições** | A conta deve existir. |

## Lançamentos no Razão

**Objetivo.** Postar, estornar e listar lançamentos no razão (gl_entry) por voucher.

### `post-gl-entries`

Posta um conjunto de linhas débito/crédito balanceadas no razão para um voucher.

| | |
|---|---|
| **Entradas** | --voucher-type (obrigatório, canonicalizado), --voucher-id (obrigatório), --posting-date (obrigatório), --company-id (obrigatório), --entries (obrigatório, array JSON). |
| **Saídas** | status='created', gl_entry_ids, entries_created, warnings. |
| **Regras** | voucher_type é normalizado para snake_case via canonical_voucher_type. --entries deve ser array JSON não-vazio. Validação por validate_gl_entries (lança ValueError, ex.: desbalanceado/conta inválida); inserção por insert_gl_entries. |
| **Efeitos colaterais** | INSERT em gl_entry (via lib, com débito/crédito base, checksum de cadeia); audit_log (post/gl_entry); commit. |
| **Pré-condições** | Empresa e contas referenciadas existentes; entries balanceadas e válidas. |

### `reverse-gl-entries`

Cria lançamentos de estorno para todas as linhas de um voucher.

| | |
|---|---|
| **Entradas** | --voucher-type (obrigatório, canonicalizado), --voucher-id (obrigatório), --posting-date (default: hoje UTC). |
| **Saídas** | reversed_count, reversal_entry_ids. |
| **Regras** | Normaliza voucher_type. Delega a reverse_gl_entries da lib (lança ValueError se voucher não encontrado/já estornado). |
| **Efeitos colaterais** | INSERT de lançamentos de estorno em gl_entry (débito/crédito invertidos); audit_log (reverse/gl_entry); commit. |
| **Pré-condições** | Existirem gl_entry para o voucher informado. |

### `list-gl-entries`

Lista lançamentos do razão com join na conta, filtros e paginação.

| | |
|---|---|
| **Entradas** | --company-id/--company; --account-id; --voucher-type (canonicalizado); --voucher-id; --party-type; --party-id; --from-date; --to-date; --is-cancelled; --limit (default 100); --offset (default 0). |
| **Saídas** | entries[] (campos de gl_entry + account_name), total_count, limit, offset, has_more. |
| **Regras** | Junta gl_entry com account; filtra company via account.company_id. voucher_type filtrado é canonicalizado. Ordena por posting_date desc, created_at desc. total_count calculado antes do limit. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma obrigatória além de DB acessível. |

## Saldos de Conta

**Objetivo.** Calcular o saldo de uma conta em uma data, opcionalmente por parte.

### `get-account-balance`

Calcula o saldo de uma conta até uma data, com filtro opcional por parte.

| | |
|---|---|
| **Entradas** | --account-id (obrigatório); --as-of-date (obrigatório); --party-type; --party-id. |
| **Saídas** | balance, debit_total, credit_total, currency. |
| **Regras** | Erro se a conta não existe ou se faltar --as-of-date. Soma gl_entry não-cancelados com posting_date <= as_of; saldo conforme balance_direction (débito-crédito ou crédito-débito). |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | A conta deve existir. |

## Anos Fiscais

**Objetivo.** Criar e listar anos fiscais de uma empresa, garantindo não-sobreposição de datas.

### `add-fiscal-year`

Cria um ano fiscal para a empresa validando sobreposição de datas.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --start-date (obrigatório); --end-date (obrigatório); --company-id (obrigatório). |
| **Saídas** | status='created', fiscal_year_id, name. |
| **Regras** | Erro se as datas se sobrepõem a um fiscal_year existente da empresa. IntegrityError vira erro de duplicidade. |
| **Efeitos colaterais** | INSERT em fiscal_year (id, name, start_date, end_date, company_id); audit_log (create/fiscal_year); commit. |
| **Pré-condições** | A empresa deve existir. |

### `list-fiscal-years`

Lista os anos fiscais de uma empresa com paginação.

| | |
|---|---|
| **Entradas** | --company-id/--company; --limit (default 20); --offset (default 0). |
| **Saídas** | fiscal_years[], total_count, limit, offset, has_more. |
| **Regras** | Filtra por company_id; ordena por start_date desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível por id ou nome. |

## Fechamento de Período

**Objetivo.** Validar, fechar e reabrir um ano fiscal, transferindo o resultado para lucros acumulados.

### `validate-period-close`

Calcula receita, despesa, resultado líquido e checa o balanceamento do balancete antes do fechamento.

| | |
|---|---|
| **Entradas** | --fiscal-year-id (obrigatório). |
| **Saídas** | fiscal_year, income_total, expense_total, net_income, trial_balance_balanced. |
| **Regras** | Erro se FY não existe ou já está fechado. income = credit-debit de contas income; expense = debit-credit de contas expense (no intervalo do FY, não-cancelados). trial_balance_balanced = \|total_debit-total_credit\| < 0.01 sobre toda a empresa. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Ano fiscal existente e ainda aberto. |

### `close-fiscal-year`

Fecha o ano fiscal criando o voucher de fechamento e zerando contas de resultado contra lucros acumulados.

| | |
|---|---|
| **Entradas** | --fiscal-year-id (obrigatório); --closing-account-id (obrigatório, conta equity); --posting-date (obrigatório). |
| **Saídas** | status='submitted', pcv_id, net_pl_transferred, gl_entries_created, fiscal_year_closed=true. |
| **Regras** | Erro se FY não existe/já fechado; conta de fechamento deve existir, ser root_type='equity' e pertencer à MESMA empresa do FY (ADR-0016, hard-fail). net_pl = income - expense. Helper _close_pl_accounts zera cada conta income/expense leaf (is_group=0) com saldo, postando pares contra lucros acumulados. |
| **Efeitos colaterais** | INSERT em period_closing_voucher (status='submitted'); INSERT de pares em gl_entry (voucher_type='period_closing', voucher_id=pcv_id, moeda 'USD'/rate '1'); UPDATE fiscal_year.is_closed=1; audit_log (close/fiscal_year); commit. |
| **Pré-condições** | Ano fiscal aberto e conta de lucros acumulados (equity) da mesma empresa existente. |

### `reopen-fiscal-year`

Reabre um ano fiscal fechado, cancelando o voucher de fechamento e seus lançamentos.

| | |
|---|---|
| **Entradas** | --fiscal-year-id (obrigatório). |
| **Saídas** | fiscal_year_id, is_closed=false, pcv_reversed. |
| **Regras** | Erro se FY não existe ou não está fechado. Localiza o period_closing_voucher submitted; se houver, cancela seus gl_entry e marca PCV como 'cancelled'. |
| **Efeitos colaterais** | UPDATE gl_entry.is_cancelled=1 (voucher_type='period_closing' do PCV); UPDATE period_closing_voucher.status='cancelled'; UPDATE fiscal_year.is_closed=0; audit_log (reopen/fiscal_year); commit. |
| **Pré-condições** | Ano fiscal existente e fechado. |

## Centros de Custo

**Objetivo.** Criar e listar centros de custo da empresa.

### `add-cost-center`

Cria um centro de custo (grupo ou folha) para uma empresa.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --company-id (obrigatório); --parent-id; --is-group (default false). |
| **Saídas** | status='created', cost_center_id, name. |
| **Regras** | Erro se faltar name ou company-id. IntegrityError vira erro de duplicidade. |
| **Efeitos colaterais** | INSERT em cost_center (id, name, parent_id, company_id, is_group); audit_log (create/cost_center); commit. |
| **Pré-condições** | A empresa deve existir. |

### `list-cost-centers`

Lista os centros de custo de uma empresa com paginação.

| | |
|---|---|
| **Entradas** | --company-id/--company; --parent-id; --limit (default 20); --offset (default 0). |
| **Saídas** | cost_centers[], total_count, limit, offset, has_more. |
| **Regras** | Filtra por company_id e opcionalmente parent_id; ordena por name. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível por id ou nome. |

## Dimensões Contábeis

**Objetivo.** Gerenciar o registro de dimensões contábeis (dimension_registry) que alimentam gl_entry.dimensions_json.

### `add-dimension`

Registra uma nova dimensão contábil com chave, rótulo e tipo de dado.

| | |
|---|---|
| **Entradas** | --key (obrigatório); --label (obrigatório); --type (text\|uuid_fk\|enum, default 'text'); --refers-to (obrigatório se type=uuid_fk); --allowed-values (obrigatório se type=enum, CSV); --required-on-account-types (CSV). |
| **Saídas** | status='created', dimension_id, key, data_type. |
| **Regras** | key não pode colidir com chaves reservadas (account_id, cost_center_id, project_id). uuid_fk exige --refers-to; enum exige --allowed-values. CSVs viram listas JSON. IntegrityError vira 'dimension already exists'. |
| **Efeitos colaterais** | INSERT em dimension_registry; audit_log (create/dimension_registry); commit. |
| **Pré-condições** | Tabela dimension_registry disponível; key única e não reservada. |

### `list-dimensions`

Lista as dimensões contábeis registradas, ativas por padrão.

| | |
|---|---|
| **Entradas** | --include-inactive (default false). |
| **Saídas** | dimensions[], count. |
| **Regras** | Sem --include-inactive, filtra is_active=1. Ordena por key. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela dimension_registry disponível. |

### `update-dimension`

Atualiza metadados de uma dimensão por chave (sem renomear a chave).

| | |
|---|---|
| **Entradas** | --key (obrigatório); campos opcionais: --label, --type (validado), --refers-to, --allowed-values, --required-on-account-types, --is-active. |
| **Saídas** | status='updated', key. |
| **Regras** | Erro se dimensão não existe, se --type inválido, ou se nenhum campo for fornecido. Não permite renomear a key. Seta updated_at. |
| **Efeitos colaterais** | UPDATE em dimension_registry (campos enviados + updated_at); audit_log (update/dimension_registry); commit. |
| **Pré-condições** | A dimensão deve existir. |

### `deactivate-dimension`

Desativa uma dimensão, bloqueando se ainda referenciada por GL recente.

| | |
|---|---|
| **Entradas** | --key (obrigatório); --within-days (default 90). |
| **Saídas** | status='deactivated', key. |
| **Regras** | Erro se dimensão não existe. Conta gl_entry não-cancelados com a chave em dimensions_json e posting_date >= hoje-within_days; se houver, recusa a desativação (dimensão em uso). |
| **Efeitos colaterais** | UPDATE dimension_registry.is_active=0 e updated_at; audit_log (update/dimension_registry); commit. |
| **Pré-condições** | A dimensão deve existir e não ter uso recente dentro da janela. |

## Orçamentos

**Objetivo.** Criar e listar orçamentos por conta/centro de custo dentro de um ano fiscal, com realizado e variação.

### `add-budget`

Cria um orçamento para um ano fiscal, vinculado a conta e/ou centro de custo.

| | |
|---|---|
| **Entradas** | --fiscal-year-id (obrigatório); --budget-amount (obrigatório); --account-id e/ou --cost-center-id (ao menos um obrigatório); --action-if-exceeded (default 'warn'). |
| **Saídas** | status='created', budget_id. |
| **Regras** | Erro se faltar FY ou amount, ou se não houver nem account nem cost-center. company_id é herdado do fiscal_year. IntegrityError vira erro de duplicidade. |
| **Efeitos colaterais** | INSERT em budget (id, fiscal_year_id, account_id, cost_center_id, budget_amount, action_if_exceeded, company_id); audit_log (create/budget); commit. |
| **Pré-condições** | O ano fiscal deve existir. |

### `list-budgets`

Lista orçamentos de um ano fiscal com valor realizado e variação calculados do razão.

| | |
|---|---|
| **Entradas** | --fiscal-year-id (obrigatório); --company-id/--company; --limit (default 20); --offset (default 0). |
| **Saídas** | budgets[] (campos + actual_amount, variance), total_count, limit, offset, has_more. |
| **Regras** | Erro se FY não existe. Para cada orçamento, soma debit de gl_entry não-cancelados no intervalo do FY filtrando por account_id e/ou cost_center_id; variance = budget_amount - actual. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Ano fiscal existente; empresa resolvível. |

## Séries de Numeração

**Objetivo.** Inicializar e avançar séries de numeração de documentos por tipo de entidade e empresa.

### `seed-naming-series`

Cria séries de numeração padrão (uma por tipo de entidade) para uma empresa no ano corrente.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório). |
| **Saídas** | series_created, total_types. |
| **Regras** | Itera ENTITY_PREFIXES gerando prefixo '{prefix}{ano}-'; cria a série apenas se ainda não existir (idempotente). current_value inicia em 0. |
| **Efeitos colaterais** | INSERT em naming_series (id, entity_type, prefix, current_value, company_id) por série nova; commit. NÃO grava audit_log. |
| **Pré-condições** | A empresa deve existir. |

### `next-series`

Retorna o próximo nome/número da série para um tipo de entidade.

| | |
|---|---|
| **Entradas** | --entity-type (obrigatório); --company-id (obrigatório). |
| **Saídas** | series (nome gerado), entity_type. |
| **Regras** | Delega a get_next_name da lib (lança ValueError se entity_type/série inválida), que incrementa o contador. |
| **Efeitos colaterais** | UPDATE em naming_series (current_value incrementado, dentro de get_next_name); commit. |
| **Pré-condições** | Série existir para o entity_type/empresa (ou ser criável pela lib). |

## Importação

**Objetivo.** Importar saldos de abertura via CSV postando-os como lançamento de abertura no razão.

### `import-opening-balances`

Importa saldos de abertura de um CSV e os posta como um lançamento de abertura único.

| | |
|---|---|
| **Entradas** | --csv-path (obrigatório, .csv válido); --company-id (obrigatório); --posting-date (obrigatório). Colunas: account_number, debit, credit, party_type, party_name. |
| **Saídas** | gl_entries_created, voucher_id, rows_processed. |
| **Regras** | Valida .csv e schema via validate_csv('opening_balance'); erro se inválido/vazio. Resolve conta por account_number (erro se não achar); resolve party_id por party_name em customer/supplier. Posta como voucher_type='journal_entry' com is_opening=True (insert_gl_entries lança ValueError se desbalanceado). |
| **Efeitos colaterais** | INSERT em gl_entry (via lib, marcados como abertura, mesmo voucher_id); commit. NÃO grava audit_log. |
| **Pré-condições** | Empresa e contas (por account_number) existentes; CSV válido acessível. |

## Integridade e Câmbio

**Objetivo.** Verificar a integridade do razão e revalorizar saldos em moeda estrangeira no fim de período.

### `check-gl-integrity`

Verifica o balanceamento global e a integridade da cadeia de hash SHA-256 do razão de uma empresa.

| | |
|---|---|
| **Entradas** | --company-id/--company. |
| **Saídas** | balanced, total_debit, total_credit, difference, chain_intact, broken_links, total_entries. |
| **Regras** | balanced = \|total_debit-total_credit\| < 0.01 (não-cancelados). Recalcula o hash encadeado (campos posting_date\|account_id\|debit\|credit\|voucher_type\|voucher_id\|prev_hash, prev inicial 'GENESIS') e compara com gl_checksum; entries sem checksum são puladas; conta broken_links. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível por id ou nome. |

### `revalue-foreign-balances`

Revaloriza contas monetárias em moeda estrangeira na taxa de fim de período, postando ganho/perda não realizado.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --as-of-date (obrigatório). |
| **Saídas** | revaluations[] (por conta, com txn_balance, old/new_base_balance, gain_loss, exchange_rate, gl_entries ou skipped/reason), total_gain_loss, accounts_processed. |
| **Regras** | Erro se empresa não existe ou sem exchange_gain_loss_account_id. Processa contas leaf não-desabilitadas com currency != base e account_type em receivable/payable/bank/cash. Para cada uma com saldo: ganho/perda = saldo*nova_taxa - saldo_base atual; pula se taxa ausente ou variação zero; ganho → DR conta / CR FX, perda → DR FX / CR conta; aplica default_cost_center_id à perna FX. |
| **Efeitos colaterais** | INSERT em gl_entry (via insert_gl_entries, voucher_type='exchange_rate_revaluation', um voucher por conta); commit. NÃO grava audit_log. |
| **Pré-condições** | Empresa com default_currency e exchange_gain_loss_account_id configurados; taxas de câmbio cadastradas. |

## Status

**Objetivo.** Fornecer estatísticas agregadas do estado do módulo GL.

### `status`

Retorna contagens agregadas de empresas, contas, anos fiscais e lançamentos do GL.

| | |
|---|---|
| **Entradas** | --company-id (opcional; auto-detecta se houver só uma empresa, senão estatísticas globais). |
| **Saídas** | companies, accounts, fiscal_years, gl_entries, latest_posting_date. |
| **Regras** | Com company_id, conta accounts/fiscal_years/gl_entries não-cancelados e a maior posting_date dessa empresa; sem ele, agrega globalmente. companies é sempre a contagem total de empresas. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma além de DB acessível. |

