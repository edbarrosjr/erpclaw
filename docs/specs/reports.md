# Relatórios — `glue-reports`

> Spec funcional por ação. Gerada de `scripts/glue-reports/db_query.py`. 14 funcionalidades · 22 ações.

## DRE

**Objetivo.** Demonstração de resultado (receitas, despesas, lucro líquido) flat, agrupada por dimensão, ou comparativa entre períodos.

### `profit-and-loss`

Calcula a demonstração de resultado (receitas menos despesas = lucro líquido) de um período, opcionalmente quebrada por uma dimensão contábil.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --from-date (obrigatório); --to-date (obrigatório); --project-id (filtro opcional); --dimension-key/--dimension-value (pares de filtro M6); --group-by (uma única dimensão, opcional). |
| **Saídas** | Flat: period, income[] (account, account_id, amount), income_total, expenses[], expense_total, net_income. Com --group-by: period, group_by, groups[] (chave, revenue, expenses, net), income_total, expense_total, net_income. |
| **Regras** | Exige from-date e to-date. Receita = credit-debit em contas root_type='income'; despesa = debit-credit em 'expense', ambas is_group=0 e is_cancelled=0; HAVING descarta contas com amount=0. Com --group-by aceita exatamente UMA dimensão (erro se vazia ou múltipla), que precisa estar registrada e ativa; entradas sem a chave caem no bucket '(untagged)'. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; contas income/expense e gl_entry postados no período; para --group-by, a dimensão registrada e ativa em dimension_registry. |

### `comparative-pl`

Compara receitas, despesas e resultado líquido de várias contas income/expense lado a lado entre múltiplos períodos informados.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --periods (obrigatório, JSON array de {from_date, to_date, label}). |
| **Saídas** | accounts[] (account, account_id, root_type, periods[] com label e amount por período); totals[] (label, income, expenses, net por período). |
| **Regras** | Erro se --periods ausente ou não for lista. Para cada período soma income (credit-debit) e expense (debit-credit) por conta (is_group=0, is_cancelled=0); label default é 'from to to'. Acumula cada conta uma vez e anexa um amount por período. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; contas income/expense; gl_entry postados nos períodos informados. |

## Balanço

**Objetivo.** Balanço patrimonial (ativos, passivos, patrimônio) em uma data, incluindo o lucro do exercício no patrimônio.

### `balance-sheet`

Produz o balanço patrimonial em uma data, somando ativos, passivos e patrimônio mais o lucro líquido acumulado do exercício (YTD).

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --as-of-date (obrigatório); --project-id (filtro opcional); --dimension-key/--dimension-value (pares de filtro M6). |
| **Saídas** | as_of_date, assets[] (account, account_id, amount), total_assets, liabilities[], total_liabilities, equity[], total_equity, net_income_ytd. |
| **Regras** | Exige as-of-date. Ativos = debit-credit; passivos e patrimônio = credit-debit; só contas is_group=0, is_cancelled=0 até a data; HAVING descarta saldo zero. net_income_ytd = (income credit-debit) - (expense debit-credit) desde o início do fiscal_year vigente na data; total_equity = patrimônio base + net_income_ytd. O filtro dimensional/projeto é aplicado tanto nas seções quanto no cálculo de lucro para manter o balanço fechando. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; contas asset/liability/equity/income/expense; fiscal_year cobrindo a data (senão net_income_ytd=0); gl_entry postados. |

## Balancete

**Objetivo.** Balancete de verificação por conta com saldos de abertura, movimento do período e fechamento.

### `trial-balance`

Lista o balancete por conta com débito/crédito de abertura, do período e de fechamento, totalizando débitos e créditos.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --to-date (obrigatório); --from-date (opcional, define abertura/movimento); --project-id (filtro opcional); --dimension-key/--dimension-value (pares de filtro M6). |
| **Saídas** | as_of_date, total_debit, total_credit, accounts[] (account_id, account_name, account_number, root_type, opening_debit, opening_credit, debit, credit, closing_debit, closing_credit). |
| **Regras** | Exige to-date. Com --from-date: abertura = soma antes de from-date e movimento = entre from-date e to-date; sem from-date: abertura zero e movimento = tudo até to-date. Fechamento = abertura+período; contas is_group são puladas e as com fechamento débito e crédito zero são omitidas. Sempre is_cancelled=0. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; contas e gl_entry postados; dimensão registrada se usada como filtro. |

## Fluxo de Caixa

**Objetivo.** Demonstração de fluxo de caixa pelo método indireto, classificando movimentos em operacional, investimento e financiamento.

### `cash-flow`

Monta o fluxo de caixa indireto do período com saldos de abertura/fechamento de caixa e bancos e movimentos categorizados.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --from-date (obrigatório); --to-date (obrigatório); --dimension-key/--dimension-value (pares de filtro M6). |
| **Saídas** | operating, investing, financing, net_change, opening_balance, closing_balance, details[] (category, account, amount). |
| **Regras** | Exige from-date e to-date. Abertura/fechamento = debit-credit em contas account_type bank/cash antes/até as datas. Movimentos das demais contas (is_cancelled=0) classificados: income/expense e ativo circulante/passivo→operating; fixed_asset/accumulated_depreciation→investing; 'Long Term Loan' e equity→financing. net_change = fechamento-abertura. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; contas bank/cash e demais com gl_entry postados no período. |

## Razão

**Objetivo.** Livro razão (general ledger) com lançamentos detalhados, saldo de abertura e saldo corrido, paginado e filtrável.

### `general-ledger`

Lista lançamentos do razão no período com saldo de abertura, saldo corrido por linha e totais de débito/crédito.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --from-date (obrigatório); --to-date (obrigatório); --account-id, --party-type, --party-id, --voucher-type (filtros opcionais); --dimension-key/--dimension-value (M6); --limit (default 100); --offset (default 0). |
| **Saídas** | entries[] (posting_date, account_name, debit, credit, balance, voucher_type, voucher_id, party_type, party_id, remarks), opening_balance, total_debit, total_credit, closing_balance. |
| **Regras** | Exige from-date e to-date. Abertura = soma(debit-credit) antes de from-date. --voucher-type é canonicalizado (ex.: 'Sales Invoice'→'sales_invoice') antes de filtrar. Lançamentos ordenados por posting_date e created_at, is_cancelled=0; saldo corrido acumula debit-credit a partir da abertura. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; gl_entry e account; partes/dimensões existentes se usadas como filtro. |

## Razão por Parceiro

**Objetivo.** Razão de um parceiro (cliente ou fornecedor) específico com saldo de abertura, lançamentos e fechamento.

### `party-ledger`

Mostra o razão de um cliente ou fornecedor com saldo de abertura, lançamentos do período e saldo de fechamento.

| | |
|---|---|
| **Entradas** | --party-type (obrigatório, 'customer' ou 'supplier'); --party-id (obrigatório); --from-date (opcional, define abertura); --to-date (opcional). |
| **Saídas** | party_name, opening_balance, entries[] (posting_date, voucher_type, voucher_id, debit, credit, balance), closing_balance. |
| **Regras** | Erro se party-type ausente/inválido ou party-id ausente. Com --from-date a abertura = soma(debit-credit) antes dela; sem from-date a abertura é forçada a zero (cláusula 1=0). Filtra gl_entry por party_type+party_id, is_cancelled=0, ordenado por posting_date/created_at; saldo corrido = abertura + (debit-credit). |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | customer ou supplier existente com o party-id; gl_entry com lançamentos para o parceiro. |

## Aging AR/AP

**Objetivo.** Relatórios de aging de contas a receber (clientes) e a pagar (fornecedores) por faixas de dias a partir do payment_ledger_entry.

### `ar-aging`

Gera o aging de contas a receber por cliente, distribuindo saldos em aberto em faixas de dias até a data de corte.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --as-of-date (obrigatório); --aging-buckets (default '30,60,90,120'). |
| **Saídas** | as_of_date, total_outstanding, customers[] (customer_id, customer_name, current, days_<b>..., days_<último>_plus, total). |
| **Regras** | Exige as-of-date; buckets devem ser inteiros separados por vírgula. Lê payment_ledger_entry com party_type='customer', delinked=0, posting_date<=as_of_date; HAVING mantém saldos com \|total\|>0.005. Idade = as_of_date - posting_date em dias; cada lançamento cai na faixa correspondente ou no bucket além da última. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | customer existente; payment_ledger_entry não-delinkados com party_type='customer'. |

### `ap-aging`

Gera o aging de contas a pagar por fornecedor, distribuindo saldos em aberto em faixas de dias até a data de corte.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --as-of-date (obrigatório); --aging-buckets (default '30,60,90,120'). |
| **Saídas** | as_of_date, total_outstanding, suppliers[] (supplier_id, supplier_name, current, days_<b>..., days_<último>_plus, total). |
| **Regras** | Idêntica a ar-aging mas com party_type='supplier' lendo nomes da tabela supplier. Exige as-of-date e buckets inteiros; HAVING \|total\|>0.005; idade por dias entre posting_date e as_of_date distribuída nas faixas. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | supplier existente; payment_ledger_entry não-delinkados com party_type='supplier'. |

## Faturas Vencidas

**Objetivo.** Identifica faturas de venda vencidas e as agrupa em faixas de atraso a partir da data atual.

### `check-overdue`

Encontra faturas de venda vencidas com saldo em aberto e as agrupa em faixas de atraso (0-30, 31-60, 61-90, 90+).

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido). Sem flags de data: usa a data atual (datetime.now) como referência. |
| **Saídas** | overdue_count, total_overdue, buckets (0_30/31_60/61_90/90_plus com count e total), invoices[] (id, name, customer_name, grand_total, outstanding, due_date, days_overdue). |
| **Regras** | Considera sales_invoice da empresa com status em submitted/partially_paid/overdue, outstanding_amount>0 e due_date<hoje. days_overdue = hoje - due_date; aloca o saldo na faixa por atraso; lista de faturas ordenada por days_overdue desc. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; sales_invoice com saldo em aberto e due_date vencida; tabela customer para o nome. |

## Orçado vs Realizado

**Objetivo.** Compara valores orçados (budget) com o realizado do gl_entry por conta/centro de custo dentro de um exercício fiscal.

### `budget-vs-actual`

Compara o valor orçado de cada budget com o realizado no período do exercício fiscal, calculando variação absoluta e percentual.

| | |
|---|---|
| **Entradas** | --fiscal-year-id (obrigatório); --company-id ou --company (resolvido); --account-id (filtro opcional); --cost-center-id (filtro opcional). |
| **Saídas** | items[] (account_or_cc, budget, actual, variance, variance_pct, action_if_exceeded). |
| **Regras** | Erro se fiscal-year-id ausente ou fiscal_year não encontrado. Realizado = soma(debit-credit) em gl_entry (is_cancelled=0) dentro de start_date/end_date do FY, filtrado pelo account_id/cost_center_id do budget. variance = budget-actual; variance_pct = variance/budget*100 (0 se budget=0). |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | fiscal_year existente; registros budget para a empresa/FY; gl_entry postados; cost_center/account referenciados. |

### `budget-variance`

Alias de budget-vs-actual: compara orçado e realizado por conta/centro de custo no exercício fiscal.

| | |
|---|---|
| **Entradas** | Mesmas de budget-vs-actual: --fiscal-year-id (obrigatório); --company-id/--company; --account-id; --cost-center-id. Mapeado para a mesma função no dispatch. |
| **Saídas** | Mesmas de budget-vs-actual: items[] (account_or_cc, budget, actual, variance, variance_pct, action_if_exceeded). |
| **Regras** | Comportamento idêntico a budget-vs-actual (mesma função handler); apenas um nome alternativo no ACTIONS. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | Iguais a budget-vs-actual: fiscal_year e budgets existentes; gl_entry postados. |

## Dimensionais

**Objetivo.** Relatórios agrupados por dimensões contábeis registradas (dimensions_json), com balancete multi-dimensional e saldo por valor de dimensão.

### `multi-dim-trial-balance`

Produz um balancete agrupado por uma ou mais dimensões contábeis lidas de gl_entry.dimensions_json, somando débito/crédito por grupo.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --to-date (obrigatório); --group-by (obrigatório, ex.: 'project,department'); --from-date (opcional); --dimension-key/--dimension-value (pares de filtro M6). |
| **Saídas** | group_by[], as_of_date, groups[] (uma chave por dimensão + debit, credit, balance), total_debit, total_credit. |
| **Regras** | Erro se to-date ou group-by ausentes. Cada chave é extraída via json_get de dimensions_json; agrupa por todas as chaves até to-date (e desde from-date se dado), is_cancelled=0. balance = debit-credit por grupo. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; gl_entry com dimensions_json populado nas chaves pedidas. |

### `dimension-balance-report`

Retorna o saldo líquido (débito-crédito) por valor distinto de uma única dimensão contábil, com filtro opcional de valores.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --dimension (obrigatório, chave K); --to-date (obrigatório); --from-date (opcional); --values (opcional, lista CSV restringindo os valores). |
| **Saídas** | dimension, as_of_date, values[] (value, debit, credit, balance), total_debit, total_credit. |
| **Regras** | Erro se --dimension ou --to-date ausentes. Extrai o valor da dimensão via json_get; soma debit/credit por valor (is_cancelled=0, até to-date, desde from-date se dado), descartando valores NULL; --values limita a um IN dos valores informados. balance = debit-credit. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; gl_entry com dimensions_json contendo a chave K. |

## Resumo de Impostos

**Objetivo.** Resumo de impostos coletados e pagos por conta de imposto no período, com passivo líquido.

### `tax-summary`

Resume impostos coletados (créditos) e pagos (débitos) por conta de imposto no período e calcula o passivo líquido.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --from-date (obrigatório); --to-date (obrigatório). |
| **Saídas** | collected, paid, net_liability, by_account[] (account_id, account_name, amount). |
| **Regras** | Exige from-date e to-date. Considera apenas contas account_type='tax', is_group=0; collected=soma(credit), paid=soma(debit) no período (is_cancelled=0); pula contas sem movimento; net_liability = total coletado - total pago; amount por conta = collected-paid. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; contas account_type='tax' com gl_entry postados no período. |

## Resumos Operacionais

**Objetivo.** Resumos agregados de pagamentos (payment_entry) e do razão (gl_entry) por tipo, não cobertos pelos demonstrativos principais.

### `payment-summary`

Resume pagamentos recebidos e pagos no período e os agrega por tipo de parte a partir de payment_entry submetidos.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --from-date (obrigatório); --to-date (obrigatório). |
| **Saídas** | total_received, total_paid, by_party_type[] (party_type, count, amount). |
| **Regras** | Exige from-date e to-date. Lê payment_entry com status='submitted' no período: total_received soma paid_amount de payment_type='receive', total_paid de 'pay'; agrega contagem e soma de paid_amount por party_type. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; payment_entry submetidos no período. |

### `gl-summary`

Resume o razão por tipo de voucher no período, com contagem e totais de débito/crédito por voucher_type.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido); --from-date (obrigatório); --to-date (obrigatório). |
| **Saídas** | by_voucher_type[] (voucher_type, count, total_debit, total_credit). |
| **Regras** | Exige from-date e to-date. Agrupa gl_entry (join account da empresa, is_cancelled=0) por voucher_type no período, contando linhas e somando debit/credit; ordenado por voucher_type. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; gl_entry postados no período. |

## Eliminações Intercompany

**Objetivo.** Gestão e execução de regras de eliminação intercompany, criando lançamentos de eliminação e mantendo trilha de auditoria.

### `add-elimination-rule`

Cria uma regra de eliminação intercompany ligando uma conta de origem (empresa fonte) a uma conta de destino (empresa alvo).

| | |
|---|---|
| **Entradas** | --name (obrigatório, ou --rule-name); --company-id (obrigatório, empresa fonte); --target-company-id (obrigatório); --source-account-id (obrigatório); --target-account-id (obrigatório). |
| **Saídas** | rule_id, name. |
| **Regras** | Erro se faltar qualquer campo, se fonte=alvo, se empresas não existirem, se contas não existirem ou não pertencerem às respectivas empresas. Gera rule_id UUID; insere a regra (status default da tabela). |
| **Efeitos colaterais** | Escreve: INSERT em elimination_rule (id, name, source/target company e account); conn.commit(). Sem postagem em gl_entry. |
| **Pré-condições** | Duas company distintas existentes; source_account na empresa fonte e target_account na empresa alvo. |

### `list-elimination-rules`

Lista as regras de eliminação intercompany com nomes de empresas e contas de origem/destino.

| | |
|---|---|
| **Entradas** | --company-id (filtro opcional: regras onde a empresa é fonte ou alvo). |
| **Saídas** | rules[] (id, name, status, source_company, target_company, source_account, target_account), total. |
| **Regras** | Junta elimination_rule a company e account (origem/destino). Com --company-id filtra por source_company_id OU target_company_id; sem ele retorna todas. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | Tabelas elimination_rule, company e account; regras previamente criadas. |

### `run-elimination`

Executa as regras de eliminação ativas para um exercício fiscal, criando pares balanceados de lançamentos de eliminação no gl_entry.

| | |
|---|---|
| **Entradas** | --fiscal-year-id (obrigatório); --posting-date ou --as-of-date (obrigatório, um deles). |
| **Saídas** | fiscal_year, posting_date, eliminations[] (rule_name, amount, source_gl_id, target_gl_id, entry_id), total_eliminated. |
| **Regras** | Erro se fiscal-year-id ou data ausentes, ou FY não encontrado, ou sem regras ativas. Para cada regra status='active': idempotente (pula se já existe elimination_entry posted para a regra+FY); valor = credit-debit da conta de origem no período do FY (excluindo voucher_type='elimination_entry'); pula se <=0. Cria DR na conta origem e CR na conta destino (par balanceado em USD). |
| **Efeitos colaterais** | Escreve: 2 INSERTs em gl_entry por regra (voucher_type='elimination_entry', is_cancelled=0) e 1 INSERT em elimination_entry; conn.commit(). Postagem direta no gl_entry contornando insert_gl_entries. |
| **Pré-condições** | fiscal_year existente; ao menos uma elimination_rule ativa; gl_entry de receita na conta de origem dentro do período. |

### `list-elimination-entries`

Lista os lançamentos de eliminação já criados, formando a trilha de auditoria das eliminações intercompany.

| | |
|---|---|
| **Entradas** | --fiscal-year-id (filtro opcional). |
| **Saídas** | entries[] (id, posting_date, amount, status, rule_name, source_company, target_company, source_account, target_account, fiscal_year), total. |
| **Regras** | Junta elimination_entry a elimination_rule, company (origem/destino), account (origem/destino) e fiscal_year. Com --fiscal-year-id filtra por FY; ordenado por posting_date desc. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | Tabela elimination_entry com lançamentos previamente criados por run-elimination. |

## Status

**Objetivo.** Diagnóstico do estado dos dados contábeis da empresa para os relatórios.

### `status`

Reporta o estado de saúde dos dados de relatório: contagem de lançamentos, datas de postagem mais antiga/recente e número de exercícios fiscais.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvido). |
| **Saídas** | gl_entry_count, latest_posting_date, earliest_posting_date, fiscal_years. |
| **Regras** | Conta gl_entry não cancelados (join account da empresa), pega min/max posting_date e conta fiscal_year da empresa. Apenas resolve a empresa, sem outras validações. |
| **Efeitos colaterais** | nenhum (leitura) |
| **Pré-condições** | company existente; tabelas gl_entry, account e fiscal_year presentes. |

