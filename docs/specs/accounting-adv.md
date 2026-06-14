# Contabilidade Avançada — `erpclaw-accounting-adv`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-accounting-adv/db_query.py`. 16 funcionalidades · 49 ações.

## Contratos de Receita (ASC 606)

**Objetivo.** Gerenciar o ciclo de vida de contratos de receita conforme ASC 606 (CRUD e modificação), servindo de cabeçalho para obrigações de desempenho, consideração variável e cronogramas de apropriação.

**Ações:**
- `add-revenue-contract` — Cria contrato de receita em status 'draft' com naming series RCON-, total_value informado e allocated_value zerado.
- `update-revenue-contract` — Atualiza cliente, número, datas, total_value e/ou contract_status (validado contra lista de status).
- `get-revenue-contract` — Retorna o contrato com suas obrigações de desempenho e considerações variáveis aninhadas.
- `list-revenue-contracts` — Lista paginada com filtros por empresa, contract_status e busca textual em cliente/número.
- `modify-contract` — Marca contrato como 'modified' e incrementa modification_count (apenas se draft ou active).

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id, --customer-name, --contract-number, --start-date, --end-date, --total-value, --contract-status; para get/update/modify: --id; filtros: --search, --limit, --offset. |
| **Saídas** | JSON com id, naming_series (RCON-), customer_name, contract_status, total_value; get inclui obligations[], obligation_count e variable_considerations[]; list traz rows[], total_count, has_more. |
| **Regras de negócio** | total_value deve ser Decimal válido; contract_status restrito a draft/active/modified/completed/terminated; ciclo: cria em draft, modify só de draft/active passa a modified incrementando contador; customer_name obrigatório na criação. |
| **Efeitos colaterais** | Insere/atualiza em advacct_revenue_contract; grava trilha de auditoria (audit) em cada criação/atualização/modificação; commit transacional. Nenhuma postagem em GL/gl_entry nem SLE de estoque. |
| **Pré-condições** | Empresa (company) deve existir; tabela advacct_revenue_contract criada via init_db.py. |

## Obrigações de Desempenho

**Objetivo.** Registrar e satisfazer obrigações de desempenho (performance obligations) de um contrato ASC 606, controlando preço autônomo, alocado, método/base de reconhecimento e percentual de conclusão.

**Ações:**
- `add-performance-obligation` — Cria obrigação 'unsatisfied' usando standalone_price como allocated_price e re-soma allocated_value do contrato.
- `list-performance-obligations` — Lista paginada com filtros por contrato, empresa e obligation_status.
- `satisfy-performance-obligation` — Define pct_complete (0-100) e deriva status: 100=satisfied (com satisfied_date), >0=partially_satisfied, 0=unsatisfied.
- `update-performance-obligation` — Atualiza standalone_price, allocated_price, nome, método e base de reconhecimento.

| Campo | Detalhe |
|---|---|
| **Entradas** | --contract-id, --company-id, --name, --standalone-price, --recognition-method (point_in_time/over_time), --recognition-basis (output/input/time); satisfy/update: --id, --pct-complete, --allocated-price. |
| **Saídas** | JSON com id, contract_id, name, standalone_price, allocated_price, recognition_method, obligation_status; satisfy retorna pct_complete e novo obligation_status. |
| **Regras de negócio** | recognition_method e recognition_basis validados contra listas; allocated_price recebe standalone_price na criação; pct_complete deve estar entre 0 e 100; não permite satisfazer obrigação já 'satisfied'; ao criar, recalcula e atualiza allocated_value do contrato (soma de allocated_price, arredondada a 0.01). |
| **Efeitos colaterais** | Insere/atualiza em advacct_performance_obligation; atualiza allocated_value/updated_at em advacct_revenue_contract na criação; grava auditoria; commit. Sem GL/SLE. |
| **Pré-condições** | Contrato de receita (advacct_revenue_contract) e empresa existentes; nome da obrigação obrigatório. |

## Consideração Variável

**Objetivo.** Registrar e listar estimativas de consideração variável (descontos, bônus, multas) de um contrato ASC 606, com método de estimativa e valor de restrição (constraint).

**Ações:**
- `add-variable-consideration` — Cria registro de consideração variável com valor estimado, constraint, método e probabilidade.
- `list-variable-considerations` — Lista paginada das considerações variáveis filtrando por contrato e empresa.

| Campo | Detalhe |
|---|---|
| **Entradas** | --contract-id, --company-id, --description, --estimated-amount, --constraint-amount, --method (expected_value/most_likely), --probability; list: --limit, --offset. |
| **Saídas** | JSON com id, contract_id, description, estimated_amount, method; list traz rows[], total_count, has_more. |
| **Regras de negócio** | method restrito a expected_value/most_likely; description obrigatória; estimated_amount, constraint_amount e probability default '0'; sem ciclo de status (registro append-only, sem updated_at). |
| **Efeitos colaterais** | Insere em advacct_variable_consideration; grava auditoria; commit. Sem efeito em GL/estoque/contrato. |
| **Pré-condições** | Contrato de receita e empresa existentes. |

## Cronograma / Apropriação de Receita

**Objetivo.** Gerar o cronograma mensal de receita de uma obrigação e efetivar o reconhecimento das parcelas, suportando modificações de contrato (ajuste de períodos futuros) e reconhecimento ponto-a-ponto.

**Ações:**
- `calculate-revenue-schedule` — Recria o cronograma mensal distribuindo allocated_price linearmente entre os meses do contrato (resto no último mês).
- `generate-revenue-entries` — Marca como recognized=1 todas as parcelas ainda não reconhecidas da obrigação e soma o total reconhecido.
- `update-schedule-amounts` — Atualiza o valor de todas as parcelas não reconhecidas (modificação upgrade/downgrade afeta só o futuro).
- `recognize-schedule-entry` — Marca uma única parcela específica como reconhecida pelo seu id (reconhecimento período-a-período).

| Campo | Detalhe |
|---|---|
| **Entradas** | --obligation-id; para recognize-schedule-entry: --id da parcela; para update-schedule-amounts: --amount. |
| **Saídas** | JSON com obligation_id, entries_created, monthly_amount, total_amount; generate retorna recognized_count e total_recognized; recognize-schedule-entry retorna id, recognized=1 e amount. |
| **Regras de negócio** | Contrato precisa de start_date e end_date; meses = diferença ano/mês + 1, deve ser >0; allocated_price deve ser >0; valor mensal arredondado a 0.01 com resíduo no último mês; calculate APAGA cronograma anterior da obrigação antes de recriar; generate exige existir parcela não reconhecida; recognize-schedule-entry rejeita parcela já reconhecida. |
| **Efeitos colaterais** | Insere/exclui/atualiza em advacct_revenue_schedule (DELETE+INSERT em calculate; flag recognized em generate/recognize; amount em update); grava auditoria; commit. Apenas marca 'recognized' — NÃO cria gl_entry; não há postagem contábil real. |
| **Pré-condições** | Obrigação de desempenho existente; contrato associado com datas; allocated_price positivo. |

## Relatórios de Receita

**Objetivo.** Fornecer relatórios analíticos de receita: waterfall de contratos x obrigações e resumo de reconhecimento por período.

**Ações:**
- `revenue-waterfall-report` — Agrega por contrato: total_value, allocated_value, status, contagem de obrigações e quantas estão satisfeitas.
- `revenue-recognition-summary` — Agrega o cronograma por period_date somando total, reconhecido e não reconhecido por período.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id (filtro opcional). |
| **Saídas** | JSON com report, rows[] e total_contracts (waterfall) ou total_periods (summary). |
| **Regras de negócio** | waterfall usa LEFT JOIN contrato x obrigação agrupado por contrato; summary agrupa parcelas por period_date e separa recognized=1 de recognized=0; sem validações de escrita. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Tabelas advacct_revenue_contract, advacct_performance_obligation e advacct_revenue_schedule existentes. |

## Arrendamentos (ASC 842)

**Objetivo.** Gerenciar o cadastro de arrendamentos (leases) conforme ASC 842 (CRUD) e classificá-los como operacional ou financeiro.

**Ações:**
- `add-lease` — Cria lease em 'draft' (naming LEAS-) com locatário, locador, prazo, pagamento mensal e taxa; ROU e passivo ficam nulos.
- `update-lease` — Atualiza partes, datas, pagamento, taxa, escalonamento, opção de compra, tipo e prazo.
- `get-lease` — Retorna o lease com pagamentos e lançamentos de amortização aninhados.
- `list-leases` — Lista paginada filtrando por empresa, lease_type, lease_status e busca textual.
- `classify-lease` — Classifica como finance (prazo >=36 meses) ou operating; aceita override via --lease-type.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id, --lessee-name, --lessor-name, --asset-description, --lease-type (operating/finance), --term-months, --monthly-payment, --annual-escalation, --discount-rate, --purchase-option-price; get/update/classify: --id. |
| **Saídas** | JSON com id, naming_series (LEAS-), lessee_name, lessor_name, lease_status, term_months; get inclui payments[], payment_count e amortization_entries[]; classify retorna lease_type. |
| **Regras de negócio** | lease_type restrito a operating/finance (default operating); lease_status restrito a draft/active/modified/expired/terminated; lessee_name e lessor_name obrigatórios; classify usa regra simplificada por prazo (>=36 meses => finance); ciclo inicia em draft. |
| **Efeitos colaterais** | Insere/atualiza em advacct_lease (classify atualiza lease_type); grava auditoria; commit. Sem GL/SLE. |
| **Pré-condições** | Empresa existente; tabela advacct_lease criada. |

## ROU / Passivo de Arrendamento

**Objetivo.** Calcular o ativo de direito de uso (ROU) e o passivo de arrendamento como valor presente dos pagamentos mensais usando a taxa de desconto.

**Ações:**
- `calculate-rou-asset` — Calcula rou_asset_value = VP de uma anuidade ordinária dos pagamentos mensais e grava no lease.
- `calculate-lease-liability` — Calcula lease_liability = VP dos pagamentos restantes (igual ao ROU no início) e grava no lease.

| Campo | Detalhe |
|---|---|
| **Entradas** | --id (lease). |
| **Saídas** | JSON com id e rou_asset_value (ou lease_liability). |
| **Regras de negócio** | term_months e monthly_payment devem ser >0; taxa mensal = discount_rate/12; VP via fórmula de anuidade ordinária com Decimal (se taxa=0, VP = pagamento x períodos), arredondado a 0.01. |
| **Efeitos colaterais** | Atualiza rou_asset_value ou lease_liability em advacct_lease; grava auditoria; commit. Sem postagem em GL. |
| **Pré-condições** | Lease existente com term_months e monthly_payment positivos e discount_rate informada. |

## Amortização / Pagamentos de Arrendamento

**Objetivo.** Gerar o cronograma de amortização do passivo e registrar pagamentos de arrendamento decompostos em principal e juros.

**Ações:**
- `generate-amortization-schedule` — Recria mês a mês o cronograma de amortização (saldo abertura, pagamento, juros, principal, saldo final) a partir do VP.
- `record-lease-payment` — Registra um pagamento 'paid' calculando juros sobre o saldo corrente, principal e saldo após o pagamento.

| Campo | Detalhe |
|---|---|
| **Entradas** | --lease-id, --payment-date, --payment-amount (record); generate usa --lease-id. |
| **Saídas** | generate: lease_id, entries_created, initial_balance, monthly_payment; record: id, lease_id, payment_amount, principal, interest, balance_after, payment_status='paid'. |
| **Regras de negócio** | term_months e monthly_payment >0 e start_date obrigatória (generate); saldo inicial = VP da anuidade; juros = saldo x taxa mensal, principal = pagamento - juros; último período zera o saldo (ajuste de arredondamento); record usa o closing_balance da última parcela de amortização, senão lease_liability, senão 0, como saldo corrente. |
| **Efeitos colaterais** | generate APAGA e reinsere advacct_amortization_entry; record insere em advacct_lease_payment; grava auditoria; commit. Não gera gl_entry nem payment_ledger_entry — apenas tabelas próprias. |
| **Pré-condições** | Lease existente com prazo, pagamento e start_date; para record, idealmente cronograma de amortização ou lease_liability já calculados. |

## Relatórios de Leasing

**Objetivo.** Fornecer relatórios de maturidade, divulgação (disclosure) e resumo dos arrendamentos para fins de demonstração financeira ASC 842.

**Ações:**
- `lease-maturity-report` — Lista leases ordenados por data de término com prazo, pagamento, ROU e passivo.
- `lease-disclosure-report` — Agrega por lease_type: contagem, soma de pagamentos mensais, total de ROU e total de passivos.
- `lease-summary` — Conta total de leases e distribui por lease_status e lease_type.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id (filtro opcional). |
| **Saídas** | JSON com report e rows[] (maturity/disclosure); summary traz total_leases, by_status{} e by_type{}. |
| **Regras de negócio** | disclosure usa COALESCE de ROU/passivo para '0' e agrupa por tipo; summary agrupa contagens por status e tipo; somente leitura. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Tabela advacct_lease existente (e advacct_lease_payment/advacct_amortization_entry para valores derivados). |

## Transações Intercompany

**Objetivo.** Gerenciar transações entre empresas do grupo (sale, purchase, service, loan, dividend, allocation) com fluxo de aprovação e postagem (draft → approved → posted).

**Ações:**
- `add-ic-transaction` — Cria transação IC em 'draft' (naming ICT-) entre duas empresas distintas com tipo, valor e moeda.
- `update-ic-transaction` — Atualiza descrição, valor, moeda, tipo e método de preço (só em draft/pending_approval).
- `get-ic-transaction` — Retorna uma transação IC pelo id.
- `list-ic-transactions` — Lista paginada filtrando por empresa, from/to, tipo, ic_status e busca.
- `approve-ic-transaction` — Move status para 'approved' (a partir de draft/pending_approval).
- `post-ic-transaction` — Move status para 'posted' e grava posted_date (apenas se 'approved').

| Campo | Detalhe |
|---|---|
| **Entradas** | --from-company-id, --to-company-id, --company-id, --transaction-type, --amount, --currency, --transfer-price-method; get/update/approve/post: --id. |
| **Saídas** | JSON com id, naming_series (ICT-), from_company_id, to_company_id, transaction_type, amount, ic_status; post retorna posted_date. |
| **Regras de negócio** | from e to devem existir e ser diferentes; transaction_type validado; amount Decimal >0; transfer_price_method (se informado) validado; ciclo: draft → approved → posted; update só em draft/pending_approval; approve só de draft/pending_approval; post só de approved; status eliminated alcançado fora deste fluxo direto. |
| **Efeitos colaterais** | Insere/atualiza em advacct_ic_transaction (post grava posted_date); grava auditoria; commit. 'posted' é apenas marcação de status — NÃO gera gl_entry real nas duas empresas. |
| **Pré-condições** | Três empresas válidas (from, to, company); tabela advacct_ic_transaction existente. |

## Preços de Transferência (Transfer Pricing)

**Objetivo.** Cadastrar e listar regras de preço de transferência por método (cost_plus, resale_minus, comparable, other) e markup aplicáveis a transações intercompany.

**Ações:**
- `add-transfer-price-rule` — Cria regra de transfer pricing com método, markup_pct, tipo de transação e vigência.
- `list-transfer-price-rules` — Lista paginada filtrando por empresa, from/to e transaction_type.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id, --from-company-id, --to-company-id, --transaction-type, --method, --markup-pct, --effective-date, --expiry-date. |
| **Saídas** | JSON com id, method, markup_pct, transaction_type; list traz rows[], total_count, has_more. |
| **Regras de negócio** | method restrito a cost_plus/resale_minus/comparable/other (default cost_plus); transaction_type (se informado) validado; markup_pct default '0'; regra é cadastro de referência, não aplica automaticamente preço nas transações IC. |
| **Efeitos colaterais** | Insere em advacct_transfer_price_rule; grava auditoria; commit. Sem GL; não altera transações existentes. |
| **Pré-condições** | Empresa existente; tabela advacct_transfer_price_rule existente. |

## Relatórios Intercompany

**Objetivo.** Fornecer relatórios de reconciliação e de eliminação das transações intercompany para conferência e preparação da consolidação.

**Ações:**
- `ic-reconciliation-report` — Agrupa transações por from/to/tipo/status somando contagem e valor total.
- `ic-elimination-report` — Lista transações 'posted' e soma o total a eliminar na consolidação.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id (filtro opcional). |
| **Saídas** | reconciliation: report e rows[] agrupados; elimination: rows[], total_to_eliminate e transaction_count. |
| **Regras de negócio** | elimination considera apenas ic_status='posted'; total_to_eliminate é a soma Decimal dos amounts; somente leitura. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Tabela advacct_ic_transaction existente com transações postadas (para o relatório de eliminação). |

## Grupos de Consolidação

**Objetivo.** Definir grupos de consolidação multi-entidade (controladora, moeda de consolidação) e cadastrar as entidades participantes com percentual de propriedade e método de consolidação.

**Ações:**
- `add-consolidation-group` — Cria grupo de consolidação 'active' (naming CGRP-) com controladora e moeda de consolidação.
- `list-consolidation-groups` — Lista paginada filtrando por empresa, group_status e busca por nome.
- `add-group-entity` — Adiciona entidade ativa ao grupo com ownership_pct, moeda funcional e método (full/proportional/equity).

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id, --name, --parent-company-id, --consolidation-currency; add-group-entity: --group-id, --entity-company-id, --entity-name, --ownership-pct, --functional-currency, --consolidation-method. |
| **Saídas** | JSON com id, naming_series (CGRP-), name, group_status (grupo); add-group-entity retorna id, group_id, entity_company_id, entity_name, ownership_pct, consolidation_method. |
| **Regras de negócio** | name obrigatório; group_status default 'active' (válidos active/inactive); consolidation_method validado contra full/proportional/equity (default full); ownership_pct default '100'; moeda de consolidação/funcional default 'USD'; entidade criada com is_active=1. |
| **Efeitos colaterais** | Insere em advacct_consolidation_group e advacct_group_entity; grava auditoria; commit. Sem GL. |
| **Pré-condições** | Empresa existente; para add-group-entity, grupo de consolidação já criado. |

## Execução de Consolidação

**Objetivo.** Executar a consolidação de um grupo em uma data-base e gerar lançamentos de eliminação (eliminações intercompany e ajustes de conversão cambial).

**Ações:**
- `run-consolidation` — Executa consolidação do grupo numa data, lista entidades ativas e marca a execução como concluída.
- `generate-elimination-entries` — Cria lançamentos de eliminação para IC transactions 'posted' entre entidades do grupo (débito IC Revenue, crédito IC Expense).
- `add-currency-translation` — Cria lançamento de ajuste de conversão cambial (CTA) do tipo currency_translation.

| Campo | Detalhe |
|---|---|
| **Entradas** | --group-id, --period-date; generate/add-currency: --company-id; add-currency-translation: --amount, --debit-account, --credit-account, --description. |
| **Saídas** | run-consolidation: group_id, group_name, period_date, entity_count, entities[] e consolidation_run='completed'; generate: entries_created; add-currency: id, group_id, amount, entry_type. |
| **Regras de negócio** | run exige período e ao menos uma entidade ativa; generate exige período, empresa e >=2 entidades ativas, eliminando IC transactions 'posted' com from e to dentro do grupo; entry_type fixo 'ic_elimination' (generate) ou 'currency_translation'; contas padrão 'IC Revenue'/'IC Expense' e 'CTA - Debit'/'CTA - Credit'. |
| **Efeitos colaterais** | generate-elimination-entries e add-currency-translation INSEREM em advacct_elimination_entry; run-consolidation NÃO grava lançamentos (apenas audita a execução). Todas gravam auditoria e commit. Eliminações ficam em tabela própria — NÃO postam em gl_entry; não alteram o ic_status das transações (não vira 'eliminated'). |
| **Pré-condições** | Grupo de consolidação com entidades ativas (>=2 para eliminação); transações IC 'posted' entre as entidades; empresa válida. |

## Relatórios de Consolidação

**Objetivo.** Apresentar o balancete consolidado (trial balance) com entidades e eliminações, e o resumo do grupo com totais de eliminações por tipo.

**Ações:**
- `consolidation-trial-balance-report` — Lista entidades ativas e lançamentos de eliminação do grupo (filtráveis por período) somando o total eliminado.
- `consolidation-summary` — Resume o grupo: contagem de entidades, de eliminações e eliminações agrupadas por entry_type com totais.

| Campo | Detalhe |
|---|---|
| **Entradas** | --group-id; trial-balance: --period-date (opcional). |
| **Saídas** | trial-balance: group_name, period_date, entities[], elimination_entries[], total_eliminations, entity_count; summary: entity_count, elimination_count, eliminations_by_type{} com count e total. |
| **Regras de negócio** | ambos validam existência do grupo; trial-balance filtra eliminações por period_date quando informado; totais somados em Decimal e arredondados a 0.01; somente leitura. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Grupo de consolidação existente; idealmente entidades e lançamentos de eliminação já cadastrados. |

## Conformidade / Status

**Objetivo.** Fornecer um painel de conformidade às normas (ASC 606/842, intercompany, consolidação) e o status técnico do módulo com contagem de registros.

**Ações:**
- `standards-compliance-dashboard` — Painel com contadores: contratos e obrigações não satisfeitas (606), leases ativos e sem ROU (842), IC não postadas e grupos ativos.
- `status` — Retorna skill, versão e contagem de registros de todas as 12 tabelas do módulo.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id (filtro opcional, apenas no dashboard). |
| **Saídas** | dashboard: report e blocos asc_606, asc_842, intercompany, consolidation com contadores; status: skill, version (1.0.0), total_tables (12) e record_counts{} por tabela. |
| **Regras de negócio** | dashboard sinaliza pendências (obrigações != satisfied, leases não-draft sem rou_asset_value, IC fora de posted/eliminated); status tolera tabela ausente retornando contagem 0; somente leitura. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Banco inicializado; tabelas do módulo idealmente criadas (status funciona mesmo sem elas, retornando 0). |

