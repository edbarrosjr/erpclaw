# Relatórios — `erpclaw-reports`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-reports/db_query.py`. 13 funcionalidades · 22 ações.

## DRE (Demonstração de Resultado)

**Objetivo.** Apura receitas e despesas do período a partir do gl_entry, gerando o resultado líquido (lucro/prejuízo). Suporta visão plana, comparativa entre períodos e quebra por uma dimensão contábil.

**Ações:**
- `profit-and-loss` — DRE do período por conta de receita/despesa; com --group-by quebra o resultado por uma dimensão contábil.
- `comparative-pl` — DRE comparativa de vários períodos lado a lado (recebe array JSON de períodos).

| Campo | Detalhe |
|---|---|
| **Entradas** | profit-and-loss: --company-id/--company, --from-date, --to-date (ambas obrigatórias); opcionais --project-id, --group-by (uma dimensão), pares --dimension-key/--dimension-value. comparative-pl: --company-id/--company e --periods (array JSON de {from_date,to_date,label}). |
| **Saídas** | profit-and-loss plano: period, listas income/expenses (account, account_id, amount), income_total, expense_total, net_income. Agrupado: groups (valor da dimensão + revenue/expenses/net), income_total, expense_total, net_income. comparative-pl: accounts (com amount por período) e totals (income/expenses/net por período). |
| **Regras de negócio** | Receita = credit - debit; Despesa = debit - credit (contas root_type income/expense, is_group=0, is_cancelled=0). Linhas com amount=0 são omitidas (HAVING). --group-by aceita exatamente uma dimensão e exige que ela esteja registrada e ativa em dimension_registry; entradas sem a chave caem no bucket '(untagged)'. net_income = income_total - expense_total. Apenas leitura; sem ciclo de vida. |
| **Efeitos colaterais** | nenhum (somente leitura). |
| **Pré-condições** | Empresa existente; plano de contas com contas income/expense; lançamentos em gl_entry no período. Para --group-by, a dimensão precisa estar registrada e ativa em dimension_registry. |

## Balanço Patrimonial

**Objetivo.** Monta o balanço (ativo, passivo e patrimônio líquido) em uma data de corte, incluindo o resultado do exercício acumulado no PL.

**Ações:**
- `balance-sheet` — Balanço patrimonial em --as-of-date com ativo/passivo/PL e lucro do exercício (YTD) somado ao PL.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id/--company, --as-of-date (obrigatória); opcionais --project-id e pares --dimension-key/--dimension-value. |
| **Saídas** | as_of_date, assets + total_assets, liabilities + total_liabilities, equity + total_equity, net_income_ytd. |
| **Regras de negócio** | Saldos acumulados até as_of_date (is_cancelled=0). Ativo = debit - credit; Passivo/PL = credit - debit. Contas com saldo zero são omitidas. net_income_ytd é apurado do início do exercício fiscal vigente (fiscal_year cuja faixa contém as_of_date) até a data e somado ao total_equity. Apenas leitura; sem ciclo de vida. |
| **Efeitos colaterais** | nenhum (somente leitura). |
| **Pré-condições** | Empresa; plano de contas com root_type asset/liability/equity/income/expense; lançamentos em gl_entry; fiscal_year cadastrado cobrindo a data para apurar o resultado do exercício. |

## Balancete (Trial Balance)

**Objetivo.** Lista por conta os saldos de abertura, a movimentação do período e o saldo de fechamento, com totais de débito e crédito para conferência de fechamento.

**Ações:**
- `trial-balance` — Balancete por conta com abertura, movimento e fechamento até --to-date.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id/--company, --to-date (obrigatória); opcionais --from-date (separa abertura de movimento), --project-id e pares --dimension-key/--dimension-value. |
| **Saídas** | as_of_date, total_debit, total_credit e accounts (account_id/name/number, root_type, opening_debit/credit, debit/credit do período, closing_debit/credit). |
| **Regras de negócio** | Sem --from-date, todo o saldo até to-date entra como movimento (abertura zero). Com --from-date, abertura = lançamentos antes da data; movimento = entre from e to. Considera apenas is_cancelled=0 e contas não-grupo; contas sem atividade (fechamento débito e crédito zero) são puladas. Apenas leitura. |
| **Efeitos colaterais** | nenhum (somente leitura). |
| **Pré-condições** | Empresa; plano de contas; lançamentos em gl_entry. |

## Fluxo de Caixa

**Objetivo.** Demonstra a variação de caixa do período classificando movimentos em operacional, investimento e financiamento (método indireto simplificado).

**Ações:**
- `cash-flow` — Fluxo de caixa do período com saldos de abertura/fechamento de contas bank/cash e movimentos categorizados.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id/--company, --from-date, --to-date (ambas obrigatórias); opcionais pares --dimension-key/--dimension-value. |
| **Saídas** | operating, investing, financing, net_change, opening_balance, closing_balance e details (categoria, conta, amount por conta movimentada). |
| **Regras de negócio** | Saldos de caixa = soma debit-credit de contas account_type bank/cash. net_change = fechamento - abertura. Classificação por root_type/account_type: income/expense e ativos/passivos correntes → operacional; fixed_asset/accumulated_depreciation → investimento; equity e 'Long Term Loan' → financiamento. Sinais ajustados (despesa/aumento de ativo = saída; aumento de passivo/receita = entrada). Apenas leitura. |
| **Efeitos colaterais** | nenhum (somente leitura). |
| **Pré-condições** | Empresa; contas com account_type bank/cash; lançamentos em gl_entry no período. |

## Razão (General Ledger)

**Objetivo.** Lista os lançamentos do livro razão no período com saldo corrente acumulado, opcionalmente filtrados por conta, parceiro ou tipo de documento.

**Ações:**
- `general-ledger` — Razão geral do período com saldo de abertura, lançamentos paginados e saldo corrente.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id/--company, --from-date, --to-date (obrigatórias); opcionais --account-id, --party-type, --party-id, --voucher-type, pares --dimension-key/--dimension-value, --limit (100), --offset (0). |
| **Saídas** | entries (posting_date, account_name, debit, credit, balance corrente, voucher_type, voucher_id, party_type/id, remarks), opening_balance, total_debit, total_credit, closing_balance. |
| **Regras de negócio** | opening_balance = soma debit-credit antes de from-date (respeitando filtros de conta/dimensão). Saldo corrente acumula por linha (debit-credit). --voucher-type é normalizado por canonical_voucher_type (ex.: 'Sales Invoice' casa com 'sales_invoice'). Considera apenas is_cancelled=0; ordenado por posting_date e created_at. Apenas leitura. |
| **Efeitos colaterais** | nenhum (somente leitura). |
| **Pré-condições** | Empresa; plano de contas; lançamentos em gl_entry. |

## Razão por Parceiro (Party Ledger)

**Objetivo.** Extrato de conta-corrente de um cliente ou fornecedor específico, com abertura, lançamentos e saldo corrente.

**Ações:**
- `party-ledger` — Razão de um parceiro (cliente/fornecedor) com saldo de abertura e fechamento.

| Campo | Detalhe |
|---|---|
| **Entradas** | --party-type (customer ou supplier, obrigatório), --party-id (obrigatório); opcionais --from-date, --to-date. |
| **Saídas** | party_name, opening_balance, entries (posting_date, voucher_type, voucher_id, debit, credit, balance), closing_balance. |
| **Regras de negócio** | Filtra gl_entry por party_type/party_id e is_cancelled=0. Sem --from-date a abertura é zero (cláusula 1=0); com from-date, abertura = soma debit-credit antes da data. Saldo corrente acumula debit-credit por linha. party_name resolvido em customer/supplier (cai no party_id se não achar). Apenas leitura. |
| **Efeitos colaterais** | nenhum (somente leitura). |
| **Pré-condições** | Parceiro (customer/supplier) cadastrado; lançamentos em gl_entry com party_type/party_id preenchidos. |

## Aging AR/AP (Contas a Receber/Pagar por idade)

**Objetivo.** Classifica o saldo em aberto de clientes (AR) e fornecedores (AP) em faixas de vencimento (aging) a partir do payment_ledger_entry.

**Ações:**
- `ar-aging` — Aging de contas a receber por cliente em faixas configuráveis.
- `ap-aging` — Aging de contas a pagar por fornecedor em faixas configuráveis.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id/--company, --as-of-date (obrigatória); opcional --aging-buckets (padrão '30,60,90,120'). |
| **Saídas** | as_of_date, total_outstanding e lista de customers/suppliers, cada um com nome/id, valor 'current', colunas days_<n> por faixa, days_<ultima>_plus e total. |
| **Regras de negócio** | Saldo em aberto vem do payment_ledger_entry (delinked=0, posting_date <= as_of_date) somado por party_type/party_id, mantendo apenas saldos significativos (\|soma\| > 0,005 via HAVING). Idade em dias = as_of_date - posting_date de cada entrada, distribuída nas faixas informadas; acima da última faixa vai para o bucket '_plus'. Apenas leitura. |
| **Efeitos colaterais** | nenhum (somente leitura). |
| **Pré-condições** | Empresa; clientes/fornecedores cadastrados; registros em payment_ledger_entry com party_type/party_id e amount. |

## Faturas Vencidas (Overdue)

**Objetivo.** Lista as notas fiscais de venda vencidas e em aberto na data de hoje, agrupando-as em faixas de atraso.

**Ações:**
- `check-overdue` — Faturas de venda vencidas com saldo aberto, em faixas de atraso (0-30, 31-60, 61-90, 90+).

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id/--company. |
| **Saídas** | overdue_count, total_overdue, buckets (0_30/31_60/61_90/90_plus com count e total) e invoices (id, name/série, customer_name, grand_total, outstanding, due_date, days_overdue, ordenadas por atraso desc). |
| **Regras de negócio** | Considera sales_invoice da empresa com status submitted/partially_paid/overdue, outstanding_amount > 0 e due_date < hoje (datetime.now()). days_overdue = hoje - due_date, distribuído nas faixas fixas. Apenas leitura; não altera status das faturas. |
| **Efeitos colaterais** | nenhum (somente leitura). |
| **Pré-condições** | Empresa; tabela sales_invoice com faturas submetidas/parcialmente pagas/vencidas, due_date e outstanding_amount preenchidos. |

## Orçado vs Realizado (Budget vs Actual)

**Objetivo.** Compara o valor orçado de cada conta/centro de custo com o realizado em gl_entry no exercício, calculando variação absoluta e percentual.

**Ações:**
- `budget-vs-actual` — Comparativo orçado x realizado por conta/centro de custo do exercício fiscal.
- `budget-variance` — Alias de budget-vs-actual.

| Campo | Detalhe |
|---|---|
| **Entradas** | --fiscal-year-id (obrigatório), --company-id/--company; opcionais --account-id, --cost-center-id. |
| **Saídas** | items com account_or_cc, budget, actual, variance, variance_pct e action_if_exceeded. |
| **Regras de negócio** | Lê linhas de budget do fiscal_year/empresa (filtráveis por conta e centro de custo). Realizado = soma debit-credit em gl_entry (is_cancelled=0) no intervalo start_date..end_date do exercício, casando account_id e/ou cost_center_id da linha orçada. variance = budget - actual; variance_pct = variance/budget*100 (0 se budget zero). Carrega o campo action_if_exceeded da linha de orçamento. Apenas leitura. |
| **Efeitos colaterais** | nenhum (somente leitura). |
| **Pré-condições** | Exercício fiscal (fiscal_year) existente; linhas em budget para o exercício; lançamentos em gl_entry. |

## Relatórios Dimensionais

**Objetivo.** Relatórios contábeis quebrados por dimensões contábeis (project, department, etc.) lidas de gl_entry.dimensions_json, para análise por dimensão.

**Ações:**
- `multi-dim-trial-balance` — Balancete agrupado por uma ou mais dimensões (--group-by 'project,department').
- `dimension-balance-report` — Saldo líquido por valor de uma única dimensão (--dimension), opcionalmente restrito a --values.

| Campo | Detalhe |
|---|---|
| **Entradas** | Ambas: --company-id/--company, --to-date (obrigatória); opcional --from-date e pares --dimension-key/--dimension-value. multi-dim-trial-balance: --group-by (lista separada por vírgula, obrigatório). dimension-balance-report: --dimension (obrigatório), --values (lista opcional). |
| **Saídas** | multi-dim: group_by, as_of_date, groups (valor por dimensão + debit/credit/balance), total_debit, total_credit. dimension-balance: dimension, as_of_date, values (value, debit, credit, balance), total_debit, total_credit. |
| **Regras de negócio** | Agrupa por fragmentos json_get(dimensions_json, chave) (dialeto-aware, chave escapada); valores ficam como parâmetros vinculados. Considera is_cancelled=0 e posting_date <= to-date (>= from-date se informado). dimension-balance-report ignora valores nulos da dimensão; --values restringe via IN. balance = debit - credit. Apenas leitura. |
| **Efeitos colaterais** | nenhum (somente leitura). |
| **Pré-condições** | Empresa; lançamentos em gl_entry com dimensions_json populado. (Estes endpoints não exigem registro em dimension_registry — diferente do --group-by da DRE.) |

## Resumo de Impostos (Tax Summary)

**Objetivo.** Resume os impostos coletados e pagos no período por conta de imposto, apurando o saldo líquido a recolher.

**Ações:**
- `tax-summary` — Resumo de impostos do período: coletado, pago e passivo líquido por conta de imposto.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id/--company, --from-date, --to-date (ambas obrigatórias). |
| **Saídas** | collected (total), paid (total), net_liability (collected - paid) e by_account (account_id, account_name, amount líquido por conta). |
| **Regras de negócio** | Considera contas account_type='tax' não-grupo da empresa. Coletado = soma de credit; pago = soma de debit, no período e is_cancelled=0. amount por conta = collected - paid; contas totalmente zeradas são omitidas. net_liability = total coletado - total pago. Apenas leitura. |
| **Efeitos colaterais** | nenhum (somente leitura). |
| **Pré-condições** | Empresa; contas com account_type='tax'; lançamentos de imposto em gl_entry no período. |

## Eliminações Intercompany

**Objetivo.** Cadastra regras de eliminação intercompany (conta-fonte/destino entre duas empresas) e gera lançamentos de eliminação no GL por exercício para consolidação, com trilha de auditoria das eliminações.

**Ações:**
- `add-elimination-rule` — Cria regra de eliminação ligando conta de uma empresa-fonte a conta de uma empresa-destino.
- `list-elimination-rules` — Lista regras de eliminação (com nomes de empresas e contas), filtrável por empresa.
- `run-elimination` — Executa as regras ativas no exercício, criando pares de lançamentos no GL e registros de elimination_entry (idempotente).
- `list-elimination-entries` — Lista os elimination_entry gerados (trilha de auditoria), filtrável por exercício.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-elimination-rule: --name, --company-id (fonte), --target-company-id, --source-account-id, --target-account-id. run-elimination: --fiscal-year-id e --posting-date (ou --as-of-date). list-elimination-rules: --company-id opcional. list-elimination-entries: --fiscal-year-id opcional. |
| **Saídas** | add-elimination-rule: rule_id, name. list-elimination-rules: rules + total. run-elimination: fiscal_year, posting_date, eliminations (rule_name, amount, source_gl_id, target_gl_id, entry_id) e total_eliminated. list-elimination-entries: entries (com empresas/contas/exercício) + total. |
| **Regras de negócio** | add: empresas fonte e destino devem existir e ser diferentes; cada conta deve pertencer à sua empresa. run: valor a eliminar = (credits - debits) da source_account no período do exercício excluindo voucher_type='elimination_entry'; só elimina se > 0; idempotente (pula regra+FY se já houver elimination_entry status='posted'). Cada eliminação debita a conta-fonte (reduz receita) e credita a conta-destino (reduz despesa), em par balanceado. |
| **Efeitos colaterais** | EFEITOS REAIS: add-elimination-rule INSERE em elimination_rule (commit). run-elimination INSERE pares de lançamentos em gl_entry (voucher_type='elimination_entry', entry_set='primary', is_cancelled=0, currency='USD'/exchange_rate=1 fixos, ignorando insert_gl_entries) e em elimination_entry (commit). NÃO grava em stock_ledger_entry/payment_ledger_entry e NÃO chama audit(). list-* são somente leitura. |
| **Pré-condições** | Duas empresas distintas; contas-fonte/destino válidas em cada empresa; regras de eliminação ativas; exercício fiscal (fiscal_year) existente para run-elimination. |

## Status / Diagnóstico

**Objetivo.** Fornece um panorama rápido do estado contábil da empresa: volume de lançamentos, janela de datas e número de exercícios fiscais.

**Ações:**
- `status` — Resumo de saúde: contagem de gl_entry, datas de lançamento mais antiga/recente e nº de exercícios fiscais.
- `gl-summary` — Resumo do GL no período agregado por voucher_type (contagem, total debit/credit).
- `payment-summary` — Resumo de pagamentos do período (recebido x pago) por tipo de parceiro, a partir de payment_entry submetidos.

| Campo | Detalhe |
|---|---|
| **Entradas** | status: --company-id/--company. gl-summary e payment-summary: --company-id/--company, --from-date, --to-date (obrigatórias). |
| **Saídas** | status: gl_entry_count, latest/earliest_posting_date, fiscal_years. gl-summary: by_voucher_type (voucher_type, count, total_debit, total_credit). payment-summary: total_received, total_paid e by_party_type (party_type, count, amount). |
| **Regras de negócio** | Todos consideram a empresa resolvida e is_cancelled=0 onde aplicável. payment-summary soma paid_amount de payment_entry com status='submitted' no período: received = payment_type='receive', paid = payment_type='pay', e quebra por party_type. gl-summary agrupa gl_entry por voucher_type. Apenas leitura. |
| **Efeitos colaterais** | nenhum (somente leitura). |
| **Pré-condições** | Empresa cadastrada; para gl-summary há de existir gl_entry; para payment-summary, registros em payment_entry submetidos; fiscal_year para a contagem em status. |

