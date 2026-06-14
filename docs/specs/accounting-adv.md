# Contabilidade Avançada — `erpclaw-accounting-adv`

> Spec funcional por ação. Gerada de `scripts/erpclaw-accounting-adv/db_query.py`. 16 funcionalidades · 49 ações.

## Contratos de Receita (ASC606)

**Objetivo.** Gerenciar o ciclo de vida (CRUD e modificações) de contratos de receita sob ASC 606.

### `add-revenue-contract`

Cria um novo contrato de receita em status draft.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --customer-name (obrigatório); --total-value (default "0"); --contract-number; --start-date; --end-date. |
| **Saídas** | id, naming_series, customer_name, contract_status ("draft"), total_value. |
| **Regras** | Valida existência da company; customer-name obrigatório; total-value deve ser decimal válido. Gera naming_series via get_next_name(prefixo RCON-). Inicializa allocated_value="0", modification_count=0, contract_status="draft". |
| **Efeitos colaterais** | INSERT em advacct_revenue_contract; audit_log via audit(); commit. |
| **Pré-condições** | Company existente; tabelas advacct_* criadas (init_db). |

### `update-revenue-contract`

Atualiza campos editáveis de um contrato de receita existente.

| | |
|---|---|
| **Entradas** | --id (obrigatório); campos opcionais: --customer-name, --contract-number, --start-date, --end-date, --total-value, --contract-status. |
| **Saídas** | id, updated_fields (lista de colunas alteradas). |
| **Regras** | Valida existência do contrato; se contract-status fornecido deve estar em (draft, active, modified, completed, terminated); erro "No fields to update" se nada mudou. Não há checagem de status para permitir edição. |
| **Efeitos colaterais** | UPDATE dinâmico em advacct_revenue_contract (set updated_at); audit_log; commit. |
| **Pré-condições** | Contrato existente. |

### `get-revenue-contract`

Retorna um contrato de receita com suas obrigações e considerações variáveis.

| | |
|---|---|
| **Entradas** | --id (obrigatório). |
| **Saídas** | Todos os campos do contrato + obligations[], obligation_count, variable_considerations[]. |
| **Regras** | Valida existência do contrato; carrega obligations ordenadas por created_at e variable_considerations. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Contrato existente. |

### `list-revenue-contracts`

Lista contratos de receita com filtros e paginação.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --company-id, --contract-status, --search (customer_name/contract_number); --limit (default 20), --offset (default 0). |
| **Saídas** | rows[], total_count, limit, offset, has_more. |
| **Regras** | Monta WHERE dinâmico; ordena por created_at DESC; has_more = (offset+limit) < total. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela advacct_revenue_contract existente. |

### `modify-contract`

Marca um contrato como modificado e incrementa o contador de modificações.

| | |
|---|---|
| **Entradas** | --id (obrigatório). |
| **Saídas** | id, contract_status ("modified"), modification_count. |
| **Regras** | Contrato deve estar em status draft ou active, caso contrário erro; incrementa modification_count em 1 e seta contract_status="modified". |
| **Efeitos colaterais** | UPDATE em advacct_revenue_contract (contract_status, modification_count, updated_at); audit_log; commit. |
| **Pré-condições** | Contrato existente em status draft ou active. |

## Obrigações de Desempenho

**Objetivo.** Gerenciar obrigações de desempenho (performance obligations) e seu cumprimento sob ASC 606.

### `add-performance-obligation`

Adiciona uma obrigação de desempenho a um contrato e atualiza o valor alocado do contrato.

| | |
|---|---|
| **Entradas** | --contract-id (obrigatório); --company-id (obrigatório); --name (obrigatório); --standalone-price (default "0"); --recognition-method (default "over_time"); --recognition-basis (default "time"). |
| **Saídas** | id, contract_id, name, standalone_price, allocated_price, recognition_method, obligation_status ("unsatisfied"). |
| **Regras** | Valida contrato e company; recognition-method em (point_in_time, over_time); recognition-basis em (output, input, time); allocated_price = standalone_price; pct_complete="0", obligation_status="unsatisfied". |
| **Efeitos colaterais** | INSERT em advacct_performance_obligation; UPDATE de advacct_revenue_contract.allocated_value (SUM dos allocated_price, arredondado 2 casas); audit_log; commit. |
| **Pré-condições** | Contrato e company existentes. |

### `list-performance-obligations`

Lista obrigações de desempenho com filtros e paginação.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --contract-id, --company-id, --obligation-status; --limit (20), --offset (0). |
| **Saídas** | rows[], total_count, limit, offset, has_more. |
| **Regras** | WHERE dinâmico; ordena por created_at ASC. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela advacct_performance_obligation existente. |

### `satisfy-performance-obligation`

Registra o percentual de cumprimento de uma obrigação e ajusta seu status.

| | |
|---|---|
| **Entradas** | --id (obrigatório); --pct-complete (default "100"). |
| **Saídas** | id, pct_complete, obligation_status. |
| **Regras** | Obrigação não pode já estar satisfied; pct deve ser decimal entre 0 e 100; pct=100 => satisfied (satisfied_date=now); 0<pct<100 => partially_satisfied; pct=0 => unsatisfied. |
| **Efeitos colaterais** | UPDATE em advacct_performance_obligation (pct_complete, obligation_status, satisfied_date, updated_at); audit_log; commit. |
| **Pré-condições** | Obrigação existente e não satisfied. |

### `update-performance-obligation`

Atualiza campos de preço/método de uma obrigação de desempenho.

| | |
|---|---|
| **Entradas** | --id (obrigatório); campos opcionais: --standalone-price, --allocated-price, --name, --recognition-method, --recognition-basis. |
| **Saídas** | id, updated_fields. |
| **Regras** | Valida existência; erro "No fields to update" se nada fornecido. Não revalida enums de recognition-method/basis nesta ação. |
| **Efeitos colaterais** | UPDATE dinâmico em advacct_performance_obligation (set updated_at); audit_log; commit. |
| **Pré-condições** | Obrigação existente. |

## Consideração Variável

**Objetivo.** Registrar e listar considerações variáveis (variable consideration) dos contratos sob ASC 606.

### `add-variable-consideration`

Adiciona uma consideração variável a um contrato de receita.

| | |
|---|---|
| **Entradas** | --contract-id (obrigatório); --company-id (obrigatório); --description (obrigatório); --estimated-amount (default "0"); --constraint-amount (default "0"); --method (default "expected_value"); --probability (default "0"). |
| **Saídas** | id, contract_id, description, estimated_amount, method. |
| **Regras** | Valida contrato e company; description obrigatório; method em (expected_value, most_likely). |
| **Efeitos colaterais** | INSERT em advacct_variable_consideration; audit_log; commit. |
| **Pré-condições** | Contrato e company existentes. |

### `list-variable-considerations`

Lista considerações variáveis com filtros e paginação.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --contract-id, --company-id; --limit (20), --offset (0). |
| **Saídas** | rows[], total_count, limit, offset, has_more. |
| **Regras** | WHERE dinâmico; ordena por created_at ASC. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela advacct_variable_consideration existente. |

## Cronograma/Apropriação de Receita

**Objetivo.** Calcular cronogramas de apropriação de receita e marcar entradas como reconhecidas.

### `calculate-revenue-schedule`

Gera um cronograma mensal de receita para uma obrigação a partir das datas do contrato.

| | |
|---|---|
| **Entradas** | --obligation-id (obrigatório). |
| **Saídas** | obligation_id, entries_created, monthly_amount, total_amount. |
| **Regras** | Obrigação e contrato devem existir; contrato precisa de start_date e end_date; allocated_price>0; meses = diferença de meses inclusiva, deve ser >0; valor mensal arredondado e último mês recebe o remainder. |
| **Efeitos colaterais** | DELETE das entradas existentes + INSERT de N linhas em advacct_revenue_schedule (recognized=0); audit_log; commit. |
| **Pré-condições** | Obrigação com allocated_price>0 e contrato com datas válidas. |

### `update-schedule-amounts`

Atualiza o valor de todas as entradas não reconhecidas de uma obrigação (modificações de contrato).

| | |
|---|---|
| **Entradas** | --obligation-id (obrigatório); --amount (obrigatório). |
| **Saídas** | obligation_id, new_amount, entries_updated. |
| **Regras** | Obrigação deve existir; amount deve ser decimal válido; atualiza somente linhas com recognized=0; entries_updated = changes(). |
| **Efeitos colaterais** | UPDATE em advacct_revenue_schedule (amount onde recognized=0); audit_log; commit. |
| **Pré-condições** | Obrigação existente com cronograma gerado. |

### `generate-revenue-entries`

Marca todas as entradas não reconhecidas de uma obrigação como reconhecidas.

| | |
|---|---|
| **Entradas** | --obligation-id (obrigatório). |
| **Saídas** | obligation_id, recognized_count, total_recognized. |
| **Regras** | Obrigação deve existir; erro se não houver entradas com recognized=0; soma os amounts reconhecidos. Não gera lançamentos em gl_entry (apenas atualiza flag recognized). |
| **Efeitos colaterais** | UPDATE em advacct_revenue_schedule (recognized=1) para cada entrada; audit_log; commit. |
| **Pré-condições** | Cronograma com entradas não reconhecidas. |

### `recognize-schedule-entry`

Marca uma única entrada de cronograma de receita como reconhecida pelo seu ID.

| | |
|---|---|
| **Entradas** | --id (obrigatório). |
| **Saídas** | id, recognized (1), amount. |
| **Regras** | Entrada deve existir; erro se já recognized=1. Usado para reconhecimento período a período (ex.: bridge Stripe ASC 606). |
| **Efeitos colaterais** | UPDATE em advacct_revenue_schedule (recognized=1) da entrada; audit_log; commit. |
| **Pré-condições** | Entrada de cronograma existente e não reconhecida. |

## Relatórios de Receita

**Objetivo.** Relatórios somente-leitura de waterfall e resumo de reconhecimento de receita.

### `revenue-waterfall-report`

Resume por contrato o valor, alocação e contagem de obrigações satisfeitas.

| | |
|---|---|
| **Entradas** | Filtro opcional: --company-id. |
| **Saídas** | report ("revenue_waterfall"), rows[] (contract_id, customer_name, total_value, allocated_value, obligation_count, satisfied_count, etc.), total_contracts. |
| **Regras** | LEFT JOIN contratos x obrigações agrupado por contrato; ordena por created_at DESC. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabelas de contrato e obrigação existentes. |

### `revenue-recognition-summary`

Resume por período os valores reconhecidos e não reconhecidos do cronograma.

| | |
|---|---|
| **Entradas** | Filtro opcional: --company-id. |
| **Saídas** | report ("revenue_recognition_summary"), rows[] (period_date, total_amount, recognized_amount, unrecognized_amount, entry_count), total_periods. |
| **Regras** | Agrupa advacct_revenue_schedule por period_date; soma condicional por flag recognized; ordena por period_date. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela advacct_revenue_schedule existente. |

## Arrendamentos (ASC842)

**Objetivo.** Gerenciar o ciclo de vida (CRUD e classificação) de arrendamentos sob ASC 842.

### `add-lease`

Cria um novo arrendamento em status draft.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --lessee-name (obrigatório); --lessor-name (obrigatório); --monthly-payment (default "0"); --discount-rate (default "0"); --term-months (default 0); --lease-type (default "operating"); --asset-description; --start-date; --end-date; --annual-escalation (default "0"); --purchase-option-price. |
| **Saídas** | id, naming_series, lessee_name, lessor_name, lease_status ("draft"), term_months. |
| **Regras** | Valida company; lessee-name e lessor-name obrigatórios; gera naming_series (prefixo LEAS-); rou_asset_value e lease_liability ficam NULL (calculados depois). |
| **Efeitos colaterais** | INSERT em advacct_lease; audit_log; commit. |
| **Pré-condições** | Company existente. |

### `update-lease`

Atualiza campos editáveis de um arrendamento existente.

| | |
|---|---|
| **Entradas** | --id (obrigatório); opcionais: --lessee-name, --lessor-name, --asset-description, --start-date, --end-date, --monthly-payment, --discount-rate, --annual-escalation, --purchase-option-price, --lease-type, --term-months. |
| **Saídas** | id, updated_fields. |
| **Regras** | Valida existência; se lease-type fornecido deve estar em (operating, finance); term-months convertido para int; erro "No fields to update" se nada mudou. |
| **Efeitos colaterais** | UPDATE dinâmico em advacct_lease (set updated_at); audit_log; commit. |
| **Pré-condições** | Arrendamento existente. |

### `get-lease`

Retorna um arrendamento com seus pagamentos e entradas de amortização.

| | |
|---|---|
| **Entradas** | --id (obrigatório). |
| **Saídas** | Campos do arrendamento + payments[], payment_count, amortization_entries[]. |
| **Regras** | Valida existência; carrega payments (ordem payment_date) e amortization_entries (ordem period_date). |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Arrendamento existente. |

### `list-leases`

Lista arrendamentos com filtros e paginação.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --company-id, --lease-type, --lease-status, --search (lessee/lessor/asset); --limit (20), --offset (0). |
| **Saídas** | rows[], total_count, limit, offset, has_more. |
| **Regras** | WHERE dinâmico; ordena por created_at DESC. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela advacct_lease existente. |

### `classify-lease`

Classifica o arrendamento como operating ou finance (auto por prazo ou override manual).

| | |
|---|---|
| **Entradas** | --id (obrigatório); --lease-type opcional (override). |
| **Saídas** | id, lease_type. |
| **Regras** | Se lease-type não informado, auto-classifica: term_months>=36 => finance, senão operating; lease-type informado deve estar em (operating, finance). |
| **Efeitos colaterais** | UPDATE em advacct_lease (lease_type, updated_at); audit_log; commit. |
| **Pré-condições** | Arrendamento existente. |

## ROU/Passivo de Arrendamento

**Objetivo.** Calcular o ativo de direito de uso (ROU) e o passivo de arrendamento via valor presente.

### `calculate-rou-asset`

Calcula o valor do ativo de direito de uso (ROU) como valor presente dos pagamentos.

| | |
|---|---|
| **Entradas** | --id (obrigatório). |
| **Saídas** | id, rou_asset_value. |
| **Regras** | term_months>0 e monthly_payment>0; taxa mensal = discount_rate/12; ROU = PV de anuidade ordinária (arredondado 2 casas; rate=0 => payment*periods). |
| **Efeitos colaterais** | UPDATE em advacct_lease (rou_asset_value, updated_at); audit_log; commit. |
| **Pré-condições** | Arrendamento existente com term_months e monthly_payment positivos. |

### `calculate-lease-liability`

Calcula o passivo de arrendamento como valor presente dos pagamentos remanescentes.

| | |
|---|---|
| **Entradas** | --id (obrigatório). |
| **Saídas** | id, lease_liability. |
| **Regras** | term_months>0 e monthly_payment>0; taxa mensal = discount_rate/12; passivo = PV de anuidade (igual ao ROU na origem). |
| **Efeitos colaterais** | UPDATE em advacct_lease (lease_liability, updated_at); audit_log; commit. |
| **Pré-condições** | Arrendamento existente com term_months e monthly_payment positivos. |

## Amortização/Pagamentos de Arrendamento

**Objetivo.** Gerar o cronograma de amortização e registrar pagamentos de arrendamento.

### `generate-amortization-schedule`

Gera o cronograma mensal de amortização (juros/principal/saldos) do arrendamento.

| | |
|---|---|
| **Entradas** | --lease-id (obrigatório). |
| **Saídas** | lease_id, entries_created, initial_balance, monthly_payment. |
| **Regras** | term_months>0, monthly_payment>0 e start_date obrigatórios; saldo inicial = PV; por mês: juros=saldo*taxa_mensal, principal=pagamento-juros; último mês zera saldo e ajusta principal/juros por arredondamento. |
| **Efeitos colaterais** | DELETE entradas existentes + INSERT de N linhas em advacct_amortization_entry; audit_log; commit. |
| **Pré-condições** | Arrendamento existente com term_months, monthly_payment e start_date válidos. |

### `record-lease-payment`

Registra um pagamento de arrendamento, decompondo em juros e principal.

| | |
|---|---|
| **Entradas** | --lease-id (obrigatório); --payment-date (obrigatório); --payment-amount (obrigatório). |
| **Saídas** | id, lease_id, payment_amount, principal, interest, balance_after, payment_status ("paid"). |
| **Regras** | Saldo corrente vem da última entrada de amortização (closing_balance) ou do lease_liability ou 0; juros=saldo*discount_rate/12; principal=pagamento-juros; balance_after=saldo-principal; payment_status fixo "paid". |
| **Efeitos colaterais** | INSERT em advacct_lease_payment; audit_log; commit. Não posta em gl_entry/payment_ledger_entry. |
| **Pré-condições** | Arrendamento existente. |

## Relatórios de Leasing

**Objetivo.** Relatórios somente-leitura de maturidade, disclosure e resumo de arrendamentos.

### `lease-maturity-report`

Lista arrendamentos ordenados por data de término para análise de maturidade.

| | |
|---|---|
| **Entradas** | Filtro opcional: --company-id. |
| **Saídas** | report ("lease_maturity"), rows[] (id, lessee/lessor, lease_type, datas, term_months, monthly_payment, rou_asset_value, lease_liability, lease_status), total_leases. |
| **Regras** | WHERE por company; ordena por end_date ASC. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela advacct_lease existente. |

### `lease-disclosure-report`

Agrega por tipo de arrendamento os totais de pagamentos, ROU e passivos.

| | |
|---|---|
| **Entradas** | Filtro opcional: --company-id. |
| **Saídas** | report ("lease_disclosure"), rows[] (lease_type, lease_count, total_monthly_payments, total_rou_assets, total_lease_liabilities). |
| **Regras** | Agrupa por lease_type; usa COALESCE para ROU/passivo nulos. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela advacct_lease existente. |

### `lease-summary`

Retorna contagens totais de arrendamentos por status e por tipo.

| | |
|---|---|
| **Entradas** | Filtro opcional: --company-id. |
| **Saídas** | report ("lease_summary"), total_leases, by_status{}, by_type{}. |
| **Regras** | Três queries: total, GROUP BY lease_status e GROUP BY lease_type. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela advacct_lease existente. |

## Transações Intercompany

**Objetivo.** Gerenciar o ciclo de vida (CRUD, aprovação e postagem) de transações entre empresas do grupo.

### `add-ic-transaction`

Cria uma transação intercompany em status draft.

| | |
|---|---|
| **Entradas** | --from-company-id (obrigatório); --to-company-id (obrigatório); --company-id (obrigatório); --transaction-type (obrigatório); --amount (default "0", deve ser >0); --currency (default "USD"); --transfer-price-method; --description. |
| **Saídas** | id, naming_series, from_company_id, to_company_id, transaction_type, amount, ic_status ("draft"). |
| **Regras** | Valida 3 companies; from!=to; transaction-type em (sale, purchase, service, loan, dividend, allocation); amount>0; transfer-price-method (se dado) em (cost_plus, resale_minus, comparable, other); gera naming (ICT-); posted_date NULL. |
| **Efeitos colaterais** | INSERT em advacct_ic_transaction; audit_log; commit. |
| **Pré-condições** | from, to e company existentes e distintos (from!=to). |

### `update-ic-transaction`

Atualiza campos editáveis de uma transação intercompany não postada.

| | |
|---|---|
| **Entradas** | --id (obrigatório); opcionais: --description, --amount, --currency, --transaction-type, --transfer-price-method. |
| **Saídas** | id, updated_fields. |
| **Regras** | Status deve ser draft ou pending_approval, senão erro; valida enums de transaction-type e transfer-price-method se fornecidos; erro "No fields to update" se nada mudou. |
| **Efeitos colaterais** | UPDATE dinâmico em advacct_ic_transaction (set updated_at); audit_log; commit. |
| **Pré-condições** | Transação existente em status draft ou pending_approval. |

### `get-ic-transaction`

Retorna uma transação intercompany pelo seu ID.

| | |
|---|---|
| **Entradas** | --id (obrigatório). |
| **Saídas** | Todos os campos da transação (row_to_dict). |
| **Regras** | Valida existência da transação. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Transação existente. |

### `list-ic-transactions`

Lista transações intercompany com filtros e paginação.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --company-id, --from-company-id, --to-company-id, --transaction-type, --ic-status, --search (description); --limit (20), --offset (0). |
| **Saídas** | rows[], total_count, limit, offset, has_more. |
| **Regras** | WHERE dinâmico; ordena por created_at DESC. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela advacct_ic_transaction existente. |

### `approve-ic-transaction`

Aprova uma transação intercompany, movendo-a para status approved.

| | |
|---|---|
| **Entradas** | --id (obrigatório). |
| **Saídas** | id, ic_status ("approved"). |
| **Regras** | Status atual deve ser draft ou pending_approval, senão erro. |
| **Efeitos colaterais** | UPDATE em advacct_ic_transaction (ic_status="approved", updated_at); audit_log; commit. |
| **Pré-condições** | Transação existente em draft ou pending_approval. |

### `post-ic-transaction`

Posta uma transação intercompany aprovada, registrando a data de postagem.

| | |
|---|---|
| **Entradas** | --id (obrigatório). |
| **Saídas** | id, ic_status ("posted"), posted_date. |
| **Regras** | Status atual deve ser approved, senão erro; seta ic_status="posted" e posted_date=now. Não gera lançamentos em gl_entry. |
| **Efeitos colaterais** | UPDATE em advacct_ic_transaction (ic_status, posted_date, updated_at); audit_log; commit. |
| **Pré-condições** | Transação existente em status approved. |

## Preços de Transferência

**Objetivo.** Definir e listar regras de preço de transferência (transfer pricing) entre empresas.

### `add-transfer-price-rule`

Cria uma regra de preço de transferência para um par de empresas/tipo de transação.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --method (default "cost_plus"); --markup-pct (default "0"); --from-company-id; --to-company-id; --transaction-type; --effective-date; --expiry-date. |
| **Saídas** | id, method, markup_pct, transaction_type. |
| **Regras** | Valida company; method em (cost_plus, resale_minus, comparable, other); transaction-type (se dado) em conjunto válido. from/to companies não são revalidadas aqui. |
| **Efeitos colaterais** | INSERT em advacct_transfer_price_rule; audit_log; commit. |
| **Pré-condições** | Company existente. |

### `list-transfer-price-rules`

Lista regras de preço de transferência com filtros e paginação.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --company-id, --from-company-id, --to-company-id, --transaction-type; --limit (20), --offset (0). |
| **Saídas** | rows[], total_count, limit, offset, has_more. |
| **Regras** | WHERE dinâmico; ordena por created_at DESC. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela advacct_transfer_price_rule existente. |

## Relatórios Intercompany

**Objetivo.** Relatórios somente-leitura de reconciliação e eliminação de transações intercompany.

### `ic-reconciliation-report`

Agrega transações intercompany por par de empresas, tipo e status.

| | |
|---|---|
| **Entradas** | Filtro opcional: --company-id. |
| **Saídas** | report ("ic_reconciliation"), rows[] (from_company_id, to_company_id, transaction_type, transaction_count, total_amount, ic_status). |
| **Regras** | Agrupa por from/to/type/status; ordena por from_company_id, to_company_id. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela advacct_ic_transaction existente. |

### `ic-elimination-report`

Lista transações intercompany postadas e calcula o total a eliminar.

| | |
|---|---|
| **Entradas** | Filtro opcional: --company-id. |
| **Saídas** | report ("ic_elimination"), rows[] (id, from/to, type, amount, currency, posted_date), total_to_eliminate, transaction_count. |
| **Regras** | Filtra ic_status='posted'; soma os amounts (Decimal); ordena por posted_date DESC. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Existirem transações com ic_status='posted'. |

## Grupos de Consolidação

**Objetivo.** Criar e listar grupos de consolidação e adicionar entidades-membro do grupo.

### `add-consolidation-group`

Cria um grupo de consolidação ativo.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --name (obrigatório); --parent-company-id; --consolidation-currency (default "USD"). |
| **Saídas** | id, naming_series, name, group_status ("active"). |
| **Regras** | Valida company; name obrigatório; gera naming_series (prefixo CGRP-); group_status inicial "active". |
| **Efeitos colaterais** | INSERT em advacct_consolidation_group; audit_log; commit. |
| **Pré-condições** | Company existente. |

### `list-consolidation-groups`

Lista grupos de consolidação com filtros e paginação.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --company-id, --group-status, --search (name); --limit (20), --offset (0). |
| **Saídas** | rows[], total_count, limit, offset, has_more. |
| **Regras** | WHERE dinâmico; ordena por created_at DESC. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela advacct_consolidation_group existente. |

### `add-group-entity`

Adiciona uma entidade-membro (subsidiária) a um grupo de consolidação.

| | |
|---|---|
| **Entradas** | --group-id (obrigatório); --company-id (obrigatório); --entity-company-id (obrigatório); --entity-name (obrigatório); --consolidation-method (default "full"); --ownership-pct (default "100"); --functional-currency (default "USD"). |
| **Saídas** | id, group_id, entity_company_id, entity_name, ownership_pct, consolidation_method. |
| **Regras** | Valida grupo e company; entity-company-id e entity-name obrigatórios; consolidation-method em (full, proportional, equity); is_active=1. |
| **Efeitos colaterais** | INSERT em advacct_group_entity; audit_log; commit. |
| **Pré-condições** | Grupo e company existentes. |

## Execução de Consolidação

**Objetivo.** Executar a consolidação e gerar lançamentos de eliminação e tradução de moeda.

### `run-consolidation`

Executa a consolidação de um grupo para um período, listando as entidades ativas.

| | |
|---|---|
| **Entradas** | --group-id (obrigatório); --period-date (obrigatório). |
| **Saídas** | group_id, group_name, period_date, entity_count, entities[], consolidation_run ("completed"). |
| **Regras** | Valida grupo; period-date obrigatório; erro se grupo não tem entidades ativas. Não cria lançamentos — apenas agrega/audita a execução. |
| **Efeitos colaterais** | Nenhuma escrita em tabelas de dados; apenas audit_log (run-consolidation) e commit. |
| **Pré-condições** | Grupo existente com pelo menos uma entidade ativa. |

### `generate-elimination-entries`

Gera lançamentos de eliminação para transações IC postadas entre entidades do grupo.

| | |
|---|---|
| **Entradas** | --group-id (obrigatório); --period-date (obrigatório); --company-id (obrigatório). |
| **Saídas** | group_id, period_date, entries_created. |
| **Regras** | Valida grupo e company; precisa de >=2 entidades ativas; busca advacct_ic_transaction com ic_status='posted' cujos from e to estão entre as entidades; cria 1 entrada por IC (débito "IC Revenue", crédito "IC Expense", entry_type "ic_elimination"). |
| **Efeitos colaterais** | INSERT de N linhas em advacct_elimination_entry; audit_log; commit. Não posta em gl_entry. |
| **Pré-condições** | Grupo com >=2 entidades ativas e transações IC postadas entre elas. |

### `add-currency-translation`

Cria um lançamento de ajuste de tradução de moeda (CTA) no grupo.

| | |
|---|---|
| **Entradas** | --group-id (obrigatório); --company-id (obrigatório); --period-date (obrigatório); --amount (obrigatório); --debit-account (default "CTA - Debit"); --credit-account (default "CTA - Credit"); --description (default "Currency translation adjustment"). |
| **Saídas** | id, group_id, period_date, amount, entry_type ("currency_translation"). |
| **Regras** | Valida grupo e company; period-date e amount obrigatórios; entry_type fixo "currency_translation". |
| **Efeitos colaterais** | INSERT em advacct_elimination_entry; audit_log; commit. |
| **Pré-condições** | Grupo e company existentes. |

## Relatórios de Consolidação

**Objetivo.** Relatórios somente-leitura de balancete consolidado e resumo do grupo.

### `consolidation-trial-balance-report`

Retorna o balancete consolidado com entidades e lançamentos de eliminação do período.

| | |
|---|---|
| **Entradas** | --group-id (obrigatório); --period-date (opcional, filtra eliminações). |
| **Saídas** | report, group_id, group_name, period_date, entities[], elimination_entries[], total_eliminations, entity_count. |
| **Regras** | Valida grupo; entidades ativas ordenadas por entity_name; eliminações filtradas por group_id e, se dado, period_date; total_eliminations = soma dos amounts. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Grupo existente. |

### `consolidation-summary`

Resume um grupo: contagem de entidades, eliminações e totais por tipo de lançamento.

| | |
|---|---|
| **Entradas** | --group-id (obrigatório). |
| **Saídas** | report, group_id, group_name, group_status, consolidation_currency, entity_count, elimination_count, eliminations_by_type{}. |
| **Regras** | Valida grupo; conta entidades ativas e eliminações; agrupa eliminações por entry_type com count e total arredondado. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Grupo existente. |

## Conformidade/Status

**Objetivo.** Painéis transversais somente-leitura de conformidade com os padrões e de status do skill.

### `standards-compliance-dashboard`

Painel transversal com indicadores de conformidade ASC 606, ASC 842, intercompany e consolidação.

| | |
|---|---|
| **Entradas** | Filtro opcional: --company-id. |
| **Saídas** | report, asc_606{revenue_contracts, unsatisfied_obligations}, asc_842{active_leases, leases_without_rou_calculation}, intercompany{unposted_transactions}, consolidation{active_groups}. |
| **Regras** | Executa contagens condicionais: obrigações não satisfeitas, leases ativos, leases sem ROU (não draft), IC não posted/eliminated, grupos ativos. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabelas advacct_* existentes. |

### `status`

Retorna versão do skill e a contagem de registros de todas as tabelas do domínio.

| | |
|---|---|
| **Entradas** | Nenhuma. |
| **Saídas** | skill, version, total_tables, record_counts{} (por tabela). |
| **Regras** | Itera as 12 tabelas ALL_TABLES contando registros; tabela ausente/erro retorna 0. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Conexão ao DB (tolerante a tabelas ausentes). |

