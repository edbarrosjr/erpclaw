# Contabilidade (Razão Geral / GL) — `erpclaw-gl`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-gl/db_query.py`. 13 funcionalidades · 31 ações.

## Plano de Contas

**Objetivo.** Criar e manter o plano de contas (hierárquico, com tipos raiz e tipos de conta) de uma empresa, por template pronto ou conta a conta.

**Ações:**
- `setup-chart-of-accounts` — Carrega um plano de contas a partir de um template JSON (ex.: us_gaap) em assets/charts/, criando as contas que ainda não existem.
- `add-account` — Cria uma conta individual com tipo raiz, tipo de conta, pai, moeda e flag de grupo.
- `update-account` — Atualiza campos editáveis da conta (name, account_number, parent_id, is_frozen).
- `list-accounts` — Lista contas da empresa com filtros (root_type, account_type, is_group, parent_id, search) e paginação.
- `get-account` — Retorna uma conta com seu saldo calculado (débito/crédito totais e saldo conforme balance_direction) na data de corte.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id/--company, --template; ou --name, --root-type (asset\|liability\|equity\|income\|expense), --account-type, --account-number, --parent-id, --currency, --is-group; --account-id; filtros --root-type/--account-type/--parent-id/--search/--include-frozen/--limit/--offset; --as-of-date (get-account). |
| **Saídas** | setup: accounts_created, template, company_id. add: account_id, name, account_number. update: updated_fields. list: accounts[], total_count, has_more. get: account com balance, debit_total, credit_total. |
| **Regras de negócio** | root_type define balance_direction (liability/equity/income = credit_normal; demais debit_normal). account_type deve estar registrado e ativo em account_type_registry. Tipos LEAF_ONLY (receivable, payable, bank, cash, tax, cost_of_goods_sold, stock, depreciation, accumulated_depreciation, round_off) não podem ser grupo. depth derivado do pai. setup ignora contas já existentes (idempotente por account_number). update bloqueia troca de root_type/account_type quando há gl_entry não cancelado (checa has_entries). |
| **Efeitos colaterais** | Escrita em account (insert/update). Auditoria em audit_log via audit() para create/import/update. Nenhuma postagem em gl_entry. Commit ao final. |
| **Pré-condições** | Empresa existente (tabela company). Para template, arquivo assets/charts/<template>.json. Para account_type não nulo, tipo previamente registrado (account_type_registry / seed-registry-defaults). Pai existente quando --parent-id informado. |

## Congelamento de Contas

**Objetivo.** Congelar/descongelar uma conta para impedir novas postagens nela, controle de bloqueio contábil em nível de conta.

**Ações:**
- `freeze-account` — Marca a conta como congelada (is_frozen=1).
- `unfreeze-account` — Remove o congelamento da conta (is_frozen=0).

| Campo | Detalhe |
|---|---|
| **Entradas** | --account-id (obrigatório). |
| **Saídas** | status=updated, account_id, is_frozen (true/false). |
| **Regras de negócio** | Conta deve existir. Postar em conta congelada é bloqueado na validação de GL (Step 4): exige que o context_role da postagem seja igual a company.role_allowed_for_frozen_entries, senão a postagem falha. is_frozen também pode ser alterado via update-account. |
| **Efeitos colaterais** | Update em account.is_frozen e updated_at. Auditoria (freeze/unfreeze) em audit_log. Commit. Não cria nem cancela gl_entry; apenas restringe postagens futuras. |
| **Pré-condições** | Conta existente. Para que a exceção de postagem em conta congelada funcione, a empresa precisa ter role_allowed_for_frozen_entries configurado. |

## Lançamentos no Razão

**Objetivo.** Registrar (postar), estornar e consultar lançamentos contábeis em gl_entry, com partida dobrada e cadeia de integridade.

**Ações:**
- `post-gl-entries` — Posta um conjunto de lançamentos balanceados para um voucher (valida via checklist de 12+ passos e insere).
- `reverse-gl-entries` — Estorna todos os lançamentos ativos de um voucher criando entradas espelho (débito/crédito trocados) e marcando os originais como cancelados.
- `list-gl-entries` — Lista lançamentos com filtros por conta, voucher, parte, intervalo de datas e is_cancelled, com nome da conta.

| Campo | Detalhe |
|---|---|
| **Entradas** | post: --voucher-type, --voucher-id, --posting-date, --company-id, --entries (JSON array com account_id/debit/credit e opcionais party_type/party_id/cost_center_id/dimensions). reverse: --voucher-type, --voucher-id, --posting-date (default hoje). list: --account-id, --voucher-type, --voucher-id, --party-type/--party-id, --from-date/--to-date, --is-cancelled, --limit/--offset. |
| **Saídas** | post: gl_entry_ids, entries_created, warnings (ex.: orçamento). reverse: reversed_count, reversal_entry_ids. list: entries[] (com account_name), total_count, has_more. |
| **Regras de negócio** | voucher_type canonicalizado (snake_case) na fronteira. Validação obrigatória: partida dobrada (débito=crédito), conta não grupo/não desabilitada, afinidade conta-empresa, conta não congelada (ou role), parte obrigatória em receivable/payable, cost_center obrigatório em income/expense, lançamentos de abertura sem P&L, validação de cost center, ano fiscal aberto, data de congelamento, filtragem de linhas zero, checagem de orçamento, dimensões obrigatórias. Idempotência por (voucher_type, voucher_id, entry_set). Cancelamento é por estorno (não delete); reversal preserva entry_set, cost_center, dimensões. |
| **Efeitos colaterais** | INSERT em gl_entry (com gl_checksum SHA-256 encadeado por empresa, debit_base/credit_base calculados quando exchange_rate!=1, dimensions_json canônico). reverse: insere espelhos e faz UPDATE is_cancelled=1 nos originais. Auditoria (post/reverse). Commit. Não toca stock_ledger_entry nem payment_ledger_entry diretamente. |
| **Pré-condições** | Empresa, contas e (quando aplicável) cost centers/partes existentes. Ano fiscal aberto cobrindo a posting_date. voucher_type ativo em voucher_type_registry (target_table=gl_entry); party_type ativo em party_type_registry. Para reverse, lançamentos ativos do voucher. |

## Saldos de Conta

**Objetivo.** Consultar o saldo de uma conta numa data de corte, opcionalmente filtrado por parte, respeitando a direção normal do saldo.

**Ações:**
- `get-account-balance` — Calcula débito total, crédito total e saldo de uma conta até a data informada, com filtro opcional por parte.

| Campo | Detalhe |
|---|---|
| **Entradas** | --account-id (obrigatório), --as-of-date (obrigatório), --party-type, --party-id (opcionais). |
| **Saídas** | balance, debit_total, credit_total, currency. |
| **Regras de negócio** | Soma apenas lançamentos com is_cancelled=0 e posting_date <= as_of_date. Saldo = débito-crédito quando balance_direction=debit_normal; crédito-débito quando credit_normal. Conta deve existir. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Conta existente; lançamentos em gl_entry para haver saldo. |

## Anos Fiscais

**Objetivo.** Definir e listar os anos fiscais (períodos contábeis) de uma empresa, base para validação de período de postagem e fechamento.

**Ações:**
- `add-fiscal-year` — Cria um ano fiscal com nome e intervalo de datas, validando que não haja sobreposição.
- `list-fiscal-years` — Lista os anos fiscais da empresa (mais recente primeiro) com paginação.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --name, --start-date, --end-date, --company-id. list: --company-id/--company, --limit, --offset. |
| **Saídas** | add: fiscal_year_id, name. list: fiscal_years[], total_count, has_more. |
| **Regras de negócio** | Datas não podem se sobrepor a um ano fiscal existente da mesma empresa (falha apontando o ano em conflito). is_closed começa em 0 (aberto). O ano fiscal aberto cobrindo a posting_date é exigido na validação de qualquer postagem (Step 9). |
| **Efeitos colaterais** | INSERT em fiscal_year. Auditoria (create). Commit. Sem postagens em gl_entry. |
| **Pré-condições** | Empresa existente. |

## Fechamento de Período

**Objetivo.** Validar, fechar e reabrir o ano fiscal, transferindo o resultado líquido (P&L) para a conta de lucros acumulados via lançamentos de fechamento.

**Ações:**
- `validate-period-close` — Calcula receita, despesa, resultado líquido do período e verifica se o balancete está balanceado (sem alterar nada).
- `close-fiscal-year` — Cria o período de fechamento (period_closing_voucher), zera contas de receita/despesa contra a conta de equity e marca o ano como fechado.
- `reopen-fiscal-year` — Reabre o ano fiscal, cancela os lançamentos do PCV e marca o PCV como cancelled.

| Campo | Detalhe |
|---|---|
| **Entradas** | validate/reopen: --fiscal-year-id. close: --fiscal-year-id, --closing-account-id (conta equity / lucros acumulados), --posting-date. |
| **Saídas** | validate: income_total, expense_total, net_income, trial_balance_balanced. close: pcv_id, net_pl_transferred, gl_entries_created, fiscal_year_closed. reopen: is_closed=false, pcv_reversed. |
| **Regras de negócio** | Ano não pode estar já fechado (close) nem aberto (reopen). Conta de fechamento deve ser root_type=equity e pertencer à MESMA empresa do ano fiscal (ADR-0016, hard-fail antes de qualquer postagem). net_pl = receita - despesa. _close_pl_accounts zera cada conta de income/expense (não grupo, com saldo) postando o par contra a conta de equity. Reabertura cancela lançamentos do voucher_type period_closing do PCV submitted. |
| **Efeitos colaterais** | close: INSERT em period_closing_voucher (status submitted) e múltiplos INSERT em gl_entry (voucher_type=period_closing, em USD), UPDATE fiscal_year.is_closed=1. reopen: UPDATE gl_entry.is_cancelled=1 dos lançamentos do PCV, UPDATE period_closing_voucher.status=cancelled, UPDATE fiscal_year.is_closed=0. Auditoria (close/reopen). validate: nenhum (somente leitura). Commit nas ações de escrita. |
| **Pré-condições** | Ano fiscal existente. Para close: conta equity da mesma empresa e posting_date. Contas de receita/despesa com lançamentos no período. |

## Centros de Custo

**Objetivo.** Cadastrar e listar centros de custo hierárquicos da empresa, usados para rateio de resultado e checagem de orçamento.

**Ações:**
- `add-cost-center` — Cria um centro de custo com nome, pai opcional e flag de grupo.
- `list-cost-centers` — Lista centros de custo da empresa (filtro por parent_id) com paginação.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --name, --company-id, --parent-id, --is-group. list: --company-id/--company, --parent-id, --limit, --offset. |
| **Saídas** | add: cost_center_id, name. list: cost_centers[], total_count, has_more. |
| **Regras de negócio** | Nome e empresa obrigatórios. Centros de custo grupo não podem receber postagem (Step 8 da validação de GL bloqueia). Contas de income/expense exigem cost_center_id na postagem (Step 6). |
| **Efeitos colaterais** | INSERT em cost_center. Auditoria (create). Commit. Sem postagens em gl_entry. |
| **Pré-condições** | Empresa existente; pai existente quando informado. |

## Dimensões Contábeis

**Objetivo.** Registrar e gerenciar dimensões contábeis customizadas (M6) que enriquecem cada gl_entry via dimensions_json, com validação de obrigatoriedade e integridade FK.

**Ações:**
- `add-dimension` — Registra uma nova dimensão (key, label, tipo text|uuid_fk|enum) no dimension_registry.
- `list-dimensions` — Lista dimensões registradas (ativas por padrão; --include-inactive mostra todas).
- `update-dimension` — Atualiza metadados de uma dimensão por key (label, tipo, refers_to, allowed_values, obrigatoriedade, is_active); não renomeia a key.
- `deactivate-dimension` — Desativa uma dimensão se ela não estiver referenciada por GL viva recente (janela --within-days, default 90 dias).

| Campo | Detalhe |
|---|---|
| **Entradas** | --key, --label, --type (text\|uuid_fk\|enum), --refers-to (tabela, p/ uuid_fk), --allowed-values (CSV, p/ enum), --required-on-account-types (CSV), --within-days, --include-inactive, --is-active. |
| **Saídas** | add: dimension_id, key, data_type. list: dimensions[], count. update: status=updated, key. deactivate: status=deactivated, key. |
| **Regras de negócio** | key não pode colidir com colunas reservadas (account_id, cost_center_id, project_id). uuid_fk exige --refers-to; enum exige --allowed-values. key é única (insert duplicado falha). Na postagem (Step 13), dimensão obrigatória ausente para o account_type da conta falha, e valor uuid_fk deve referenciar linha existente na tabela validada. deactivate bloqueia se houver gl_entry não cancelado citando a key na janela. |
| **Efeitos colaterais** | INSERT/UPDATE em dimension_registry (incl. is_active=0 no deactivate). Auditoria (create/update). Commit. As dimensões em si não postam GL, mas passam a ser validadas/exigidas em toda postagem. |
| **Pré-condições** | Tabela dimension_registry existente. Para uuid_fk, tabela referenciada (identificador válido) existente. |

## Orçamentos

**Objetivo.** Definir orçamentos por conta e/ou centro de custo num ano fiscal e acompanhar o realizado x orçado, com ação ao exceder.

**Ações:**
- `add-budget` — Cria um orçamento para uma conta e/ou centro de custo no ano fiscal, com action_if_exceeded (warn|stop).
- `list-budgets` — Lista orçamentos do ano fiscal e calcula realizado (soma de débitos do período) e variância por orçamento.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --fiscal-year-id, --budget-amount, --account-id e/ou --cost-center-id, --action-if-exceeded (default warn). list: --fiscal-year-id, --company-id/--company, --limit, --offset. |
| **Saídas** | add: budget_id. list: budgets[] com actual_amount e variance, total_count, has_more. |
| **Regras de negócio** | Exige ao menos account_id ou cost_center_id. company_id derivado do ano fiscal. action_if_exceeded default warn. Na postagem (Step 12): se débito acumulado + atual ultrapassa budget_amount, gera warning (warn) ou bloqueia a postagem (stop). Realizado calculado por soma de débitos não cancelados no intervalo do ano fiscal. |
| **Efeitos colaterais** | add: INSERT em budget + auditoria (create) + commit. list: nenhum (somente leitura; calcula realizado on-the-fly). A aplicação efetiva (warn/stop) ocorre na validação de post-gl-entries. |
| **Pré-condições** | Ano fiscal existente; conta e/ou centro de custo existentes. |

## Séries de Numeração

**Objetivo.** Semear e avançar séries de numeração sequencial por tipo de entidade e empresa (prefixo com ano).

**Ações:**
- `seed-naming-series` — Cria séries (prefixo<ano>-) para cada tipo de entidade de ENTITY_PREFIXES que ainda não exista para a empresa.
- `next-series` — Gera/avança o próximo nome da série para um tipo de entidade da empresa.

| Campo | Detalhe |
|---|---|
| **Entradas** | seed: --company-id. next: --entity-type, --company-id. |
| **Saídas** | seed: series_created, total_types. next: series (nome gerado), entity_type. |
| **Regras de negócio** | seed é idempotente: só cria a série se não existir (entity_type+prefix+company). next usa get_next_name (incrementa current_value); falha com ValueError se o tipo não tiver série configurada. Prefixo inclui o ano UTC corrente. |
| **Efeitos colaterais** | seed: INSERT em naming_series (current_value=0). next: UPDATE do contador da série. Commit. Sem postagens em gl_entry. |
| **Pré-condições** | Empresa existente. Para next, série já semeada para o entity_type (seed-naming-series). |

## Importação

**Objetivo.** Importar plano de contas e saldos de abertura a partir de arquivos CSV, criando contas e postando o lançamento de abertura.

**Ações:**
- `import-chart-of-accounts` — Importa contas de um CSV (name, root_type, account_number, account_type, parent_name, currency, is_group), pulando duplicadas por nome.
- `import-opening-balances` — Importa saldos de abertura de um CSV (account_number, debit, credit, party_type, party_name) e posta um único lançamento de abertura.

| Campo | Detalhe |
|---|---|
| **Entradas** | --csv-path, --company-id; import-opening-balances também exige --posting-date. |
| **Saídas** | chart: imported, skipped, total_rows. opening: gl_entries_created, voucher_id, rows_processed. |
| **Regras de negócio** | Path-safety: resolve symlink, exige extensão .csv e arquivo regular. CSV validado por validate_csv antes. chart: pula conta cujo nome já existe na empresa; resolve parent por parent_name; balance_direction derivado do root_type. opening: resolve conta por account_number (falha se não achar), resolve party (customer/supplier) por nome; posta como voucher_type=journal_entry com is_opening=True (não permite contas de P&L — Step 7). |
| **Efeitos colaterais** | chart: INSERT em account (depth=0). opening: INSERT em gl_entry via insert_gl_entries (lançamento de abertura, com checksum e validação completa). Commit. import-chart NÃO grava auditoria explícita; import-opening passa pelo motor de GL. |
| **Pré-condições** | Empresa existente; arquivo .csv válido. Para opening: contas (por account_number) e ano fiscal aberto cobrindo a posting_date; partes existentes se referenciadas. |

## Integridade e Câmbio

**Objetivo.** Verificar integridade do razão (balanço e cadeia de hash) e revaluar saldos em moeda estrangeira ao câmbio de fim de período.

**Ações:**
- `check-gl-integrity` — Confere se débitos=créditos da empresa e reconstrói a cadeia SHA-256 dos gl_entry para detectar adulteração (broken_links).
- `revalue-foreign-balances` — Revalua contas monetárias em moeda estrangeira (AR/AP/bank/cash) à taxa da data, postando o ganho/perda não realizado contra a conta de FX.

| Campo | Detalhe |
|---|---|
| **Entradas** | check: --company-id/--company. revalue: --company-id, --as-of-date. |
| **Saídas** | check: balanced, total_debit, total_credit, difference, chain_intact, broken_links, total_entries. revalue: revaluations[] (por conta, com gain_loss e exchange_rate), total_gain_loss, accounts_processed. |
| **Regras de negócio** | check: balanceado quando \|débito-crédito\|<0.01; recomputa cada gl_checksum a partir de prev_hash (GENESIS) na ordem created_at/rowid; entradas sem checksum são puladas. revalue: usa company.default_currency e exchange_gain_loss_account_id (obrigatório); processa contas não grupo, não desabilitadas, com currency != base; ganho/perda = saldo base revaluado - saldo base atual; ignora saldo/variação zero; pula conta sem taxa de câmbio na data. |
| **Efeitos colaterais** | check: nenhum (somente leitura). revalue: INSERT em gl_entry (voucher_type=exchange_rate_revaluation) com o par conta vs FX gain/loss, em moeda base; usa default_cost_center_id da empresa na perna de FX. Commit no revalue. Não há auditoria explícita no revalue. |
| **Pré-condições** | Empresa existente. revalue: company.exchange_gain_loss_account_id configurado, contas em moeda estrangeira com saldo e taxa de câmbio disponível (get_exchange_rate) na as_of_date; ano fiscal aberto para postar. |

## Status

**Objetivo.** Apresentar um resumo do estado contábil: contagem de empresas, contas, anos fiscais, lançamentos ativos e última data de postagem.

**Ações:**
- `status` — Retorna métricas agregadas do GL; se houver uma única empresa (ou --company-id), filtra por ela, senão mostra estatísticas globais.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id (opcional; auto-detecta empresa única). |
| **Saídas** | companies, accounts, fiscal_years, gl_entries (não cancelados), latest_posting_date. |
| **Regras de negócio** | Conta apenas gl_entry com is_cancelled=0. Sem company_id e havendo mais de uma empresa, retorna números globais; com uma única empresa, filtra automaticamente. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Banco inicializado com a tabela company (dependência mínima do skill). |

