# Folha de Pagamento — `erpclaw-payroll`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-payroll/db_query.py`. 13 funcionalidades · 29 ações.

## Componentes

**Objetivo.** Cadastrar e listar componentes salariais (vencimentos, descontos e contribuições patronais) que servem de blocos para montar estruturas salariais e calcular holerites.

**Ações:**
- `add-salary-component` — Cria um componente salarial com tipo (earning/deduction/employer_contribution) e flags fiscais.
- `list-salary-components` — Lista componentes com filtro por tipo, busca por nome e paginação.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --name, --component-type (obrigatórios), --is-tax-applicable, --is-statutory, --is-pre-tax, --variable-based-on-taxable-salary, --depends-on-payment-days, --is-supplemental, --gl-account-id, --description. list: --component-type, --search, --limit, --offset. |
| **Saídas** | add: salary_component_id, name, component_type. list: count, components[], limit, offset, has_more. |
| **Regras de negócio** | component-type deve estar em (earning, deduction, employer_contribution). Nome único (erro se já existir). Booleanos aceitam 1/0, true/false, yes/no com defaults: is_tax_applicable=1, depends_on_payment_days=1, demais=0. Se --gl-account-id informado, valida que a conta existe. |
| **Efeitos colaterais** | Insere em salary_component e grava auditoria (audit) para add-salary-component. list é somente leitura. |
| **Pré-condições** | Tabelas company e employee existentes. Conta GL deve existir se --gl-account-id for usado. |

## Estruturas

**Objetivo.** Definir estruturas salariais que agrupam componentes com regra de cálculo (valor fixo, percentual sobre base, ou fórmula) e frequência de pagamento; consultar e listar essas estruturas.

**Ações:**
- `add-salary-structure` — Cria estrutura salarial com array JSON de componentes e seus detalhes de cálculo.
- `get-salary-structure` — Retorna a estrutura com o detalhamento ordenado de seus componentes.
- `list-salary-structures` — Lista estruturas com filtro por empresa/busca e contagem de componentes.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --name, --company-id, --components (JSON: salary_component_id, amount?, percentage?, formula?, base_component_id?, sort_order?), --payroll-frequency (default monthly). get: --salary-structure-id. list: --company-id, --search, --limit, --offset. |
| **Saídas** | add: salary_structure_id, name, payroll_frequency, component_count. get: salary_structure com components[] (inclui base_component_name) e component_count. list: count, structures[] com component_count. |
| **Regras de negócio** | payroll-frequency em (monthly, biweekly, weekly). Nome único. Empresa deve existir. Cada componente: no máximo UM de amount/percentage/formula; percentual entre 0 e 100; sem componentes duplicados; base_component_id e salary_component_id devem existir. Moeda fixada em USD; is_active=1. |
| **Efeitos colaterais** | Insere em salary_structure e salary_structure_detail; grava auditoria. get e list são somente leitura. |
| **Pré-condições** | Empresa cadastrada e componentes salariais já criados (referenciados por id no JSON). |

## Atribuições

**Objetivo.** Vincular um funcionário a uma estrutura salarial com um valor-base e vigência, gerenciando o histórico de atribuições; listar atribuições.

**Ações:**
- `add-salary-assignment` — Atribui estrutura salarial ao funcionário com base-amount e vigência, auto-encerrando a atribuição anterior.
- `list-salary-assignments` — Lista atribuições com filtros por funcionário, empresa e intervalo de datas.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --employee-id, --salary-structure-id, --base-amount, --effective-from (obrigatórios), --effective-to (opcional). list: --employee-id, --company-id, --from-date, --to-date, --limit, --offset. |
| **Saídas** | add: salary_assignment_id, employee_id, salary_structure_id, base_amount, effective_from, effective_to, e previous_assignment_closed se houve encerramento. list: count, assignments[] (com employee_name e salary_structure_name), paginação. |
| **Regras de negócio** | Funcionário e estrutura devem existir e pertencer à MESMA empresa. base-amount não-negativo (arredondado). effective-to >= effective-from. Se já existe atribuição ativa (effective_to nula ou >= novo effective_from), ela é encerrada no dia anterior ao novo início. Moeda USD. |
| **Efeitos colaterais** | Insere em salary_assignment; faz UPDATE da atribuição anterior (effective_to); grava auditoria com descrição do encerramento. list é somente leitura. |
| **Pré-condições** | Funcionário e estrutura salarial existentes e da mesma empresa. |

## Tabelas de IR (Income Tax Slabs)

**Objetivo.** Configurar tabelas progressivas de imposto de renda federal/estadual com faixas (brackets) de alíquotas e dedução padrão, usadas no cálculo do holerite; também cadastrar faixas estaduais para folha multi-estado.

**Ações:**
- `add-income-tax-slab` — Cria tabela de IR federal/estadual com faixas contíguas de alíquota e dedução padrão.
- `add-state-tax-slab` — Cria uma faixa (bracket) de imposto estadual por estado e filing-status.

| Campo | Detalhe |
|---|---|
| **Entradas** | income-tax-slab: --name, --tax-jurisdiction (federal/state), --effective-from (obrig.), --filing-status, --state-code, --standard-deduction, --rates (JSON: from_amount, to_amount, rate). state-tax-slab: --state-code, --bracket-start, --rate (obrig.), --bracket-end, --filing-status (default single). |
| **Saídas** | income-tax-slab: income_tax_slab_id, name, tax_jurisdiction, state_code, filing_status, effective_from, standard_deduction, rate_count. state-tax-slab: state_tax_slab_id, state_code, bracket_start, bracket_end, rate, filing_status. |
| **Regras de negócio** | jurisdiction em (federal, state); state-code obrigatório para state e ignorado para federal. filing-status em (single, married_jointly, married_separately, head_of_household). Faixas devem ser contíguas (from == to anterior); última pode ter to_amount null; rate 0-100; to>from. Alíquotas são percentuais. Aplicação no cálculo é progressiva (graduada). |
| **Efeitos colaterais** | add-income-tax-slab insere em income_tax_slab e income_tax_slab_rate e grava auditoria. add-state-tax-slab insere em state_tax_slab (sem auditoria). |
| **Pré-condições** | Nenhuma dependência de outras entidades; estado válido para faixas estaduais. |

## Config. de Impostos (FICA/FUTA/SUTA)

**Objetivo.** Configurar por ano-fiscal as alíquotas e bases de FICA (Social Security e Medicare) e os tributos de desemprego FUTA (federal) e SUTA (estadual), parâmetros que alimentam o cálculo das retenções e contribuições patronais.

**Ações:**
- `update-fica-config` — Upsert da configuração FICA do ano: base salarial e alíquotas de SS/Medicare empregado/empregador e Medicare adicional.
- `update-futa-suta-config` — Upsert de FUTA (state_code nulo) ou SUTA (state_code preenchido) com base, alíquota e override patronal.

| Campo | Detalhe |
|---|---|
| **Entradas** | fica: --tax-year, --ss-wage-base, --ss-employee-rate, --ss-employer-rate, --medicare-employee-rate, --medicare-employer-rate, --additional-medicare-threshold, --additional-medicare-rate (todos obrig.). futa-suta: --tax-year, --wage-base, --rate (obrig.), --state-code (NULL=FUTA), --employer-rate-override. |
| **Saídas** | Os parâmetros gravados mais action='created' ou 'updated' (e, em futa-suta, config_type 'FUTA (federal)' ou 'SUTA (XX)'). |
| **Regras de negócio** | tax-year inteiro em [2000,2100]. Todos os valores decimais validados e não-negativos; rate 0-100. FICA usa ON CONFLICT(tax_year); FUTA/SUTA usa ON CONFLICT(tax_year, state_code). employer_rate_override permite ajuste por empresa (SUTA experience-rated). |
| **Efeitos colaterais** | Upsert em fica_config e futa_suta_config respectivamente; grava auditoria com old_values/new_values. Nenhuma postagem contábil aqui (apenas configuração). |
| **Pré-condições** | Nenhuma dependência de empresa/funcionário; apenas o ano-fiscal. |

## Ciclos de Folha (Payroll Runs)

**Objetivo.** Gerenciar o ciclo de vida de uma corrida de folha por período: criar (rascunho), gerar holerites, submeter com postagem no GL e cancelar com estorno; também o status individual da corrida.

**Ações:**
- `create-payroll-run` — Cria uma corrida de folha em status 'draft' para um período, validando sobreposição.
- `submit-payroll-run` — Submete a corrida: marca holerites como 'submitted' e posta entradas no GL de forma atômica e balanceada.
- `cancel-payroll-run` — Cancela corrida submetida, estorna o GL e marca holerites como 'cancelled'.

| Campo | Detalhe |
|---|---|
| **Entradas** | create: --company-id, --period-start, --period-end (obrig.), --department-id, --payroll-frequency. submit: --payroll-run-id, --cost-center-id (busca default se ausente). cancel: --payroll-run-id. |
| **Saídas** | create: payroll_run_id, naming_series, período, frequência. submit: gl_entries (qtd), total_gross, total_net, total_employer_tax. cancel: reversed_entries (qtd), naming_series. |
| **Regras de negócio** | Ciclo: draft -> submitted -> cancelled. create exige period_start < period_end, empresa existente, departamento válido se informado, e proíbe corrida sobreposta não-cancelada. submit exige status 'draft' e ao menos 1 holerite draft; calcula impostos patronais (SS/Medicare/FUTA/SUTA), monta DR despesa salarial+tributos patronais e CR líquido(+pré-tax por funcionário)/IR federal/estadual/SS/Medicare/FUTA/SUTA, valida DR=CR (auto-corrige diferença <=1.00) e descarta entradas zeradas. cancel exige status 'submitted'. |
| **Efeitos colaterais** | create: insere payroll_run, auditoria. submit: insere gl_entry via insert_gl_entries (voucher_type='payroll_entry'), atualiza salary_slip para 'submitted' e payroll_run para 'submitted', auditoria; rollback se a postagem falhar. cancel: reverse_gl_entries, atualiza slips e run para 'cancelled', auditoria. |
| **Pré-condições** | Empresa com plano de contas (conta de despesa salarial e payroll payable localizáveis), FICA/FUTA/SUTA do ano configurados para os tributos patronais, cost center, e holerites já gerados antes do submit. |

## Holerites (Salary Slips)

**Objetivo.** Gerar, consultar e listar os holerites de cada funcionário de uma corrida, executando o motor de cálculo completo (vencimentos, proporcionalização, pré-tax, IR federal/estadual, FICA, horas extras e penhoras).

**Ações:**
- `generate-salary-slips` — Motor de cálculo: gera salary_slip e salary_slip_detail para todos os funcionários elegíveis da corrida.
- `get-salary-slip` — Retorna um holerite com earnings e deductions aninhados.
- `list-salary-slips` — Lista holerites filtrando por corrida, funcionário e status, com paginação.

| Campo | Detalhe |
|---|---|
| **Entradas** | generate: --payroll-run-id. get: --salary-slip-id. list: --payroll-run-id, --employee-id, --status, --limit, --offset. |
| **Saídas** | generate: payroll_run_id, slips_generated, total_gross, total_deductions, total_net. get: campos do slip + earnings[], deductions[], details[]. list: count, slips[] (com employee_name), paginação. |
| **Regras de negócio** | generate exige run em 'draft'; reapaga slips draft existentes (permite regerar). Vencimentos por valor/percentual sobre base (percentual tem prioridade) e prorrateio por payment_days (dias úteis menos folga não-paga). Pré-tax 401k (% do bruto) e HSA do cadastro do funcionário. IR federal progressivo anualizado menos dedução padrão; salário suplementar com flat 22% (37% acima de 1M YTD). IR estadual via employee_state_config. FICA: SS limitado à wage base via YTD, Medicare sem teto + Medicare adicional 0.9% acima do limiar; respeita is_exempt_from_fica. Penhoras pós-imposto por prioridade com teto federal. Slips criados em status 'draft'. |
| **Efeitos colaterais** | generate: deleta/insere salary_slip e salary_slip_detail, atualiza totais da payroll_run, ATUALIZA wage_garnishment (cumulative_paid e auto status 'completed'), pode auto-criar componentes estatutários, auditoria. get/list são somente leitura. Sem postagem GL nesta etapa (ocorre no submit). |
| **Pré-condições** | Corrida em 'draft'; funcionários ativos com salary_assignment vigente; estrutura com componentes; FICA do ano para reter FICA; opcionalmente tabelas de IR, overtime_policy, employee_state_config e penhoras. |

## W-2 (Dados de Fim de Ano)

**Objetivo.** Consolidar todos os holerites submetidos do ano por funcionário e produzir os dados das caixas (boxes) do formulário W-2 para fins de declaração anual.

**Ações:**
- `generate-w2-data` — Agrega slips submetidos do ano e calcula as caixas 1-6 e 12 (códigos D/W) do W-2 por funcionário.

| Campo | Detalhe |
|---|---|
| **Entradas** | --tax-year, --company-id (ambos obrigatórios). |
| **Saídas** | tax_year, company_id, company_name, employee_count e w2_data[] com employee_id, employee_name, ssn_last_four, filing_status e boxes (1=salários líquidos de pré-tax, 2=IR federal, 3=salário SS limitado à base, 4=SS retido, 5=salário Medicare, 6=Medicare retido, 12.D=401k, 12.W=HSA). |
| **Regras de negócio** | tax-year inteiro; empresa deve existir. Considera apenas slips com status 'submitted' do ano-calendário. Box1 = bruto - pré-tax (401k+HSA+demais pré-tax). Box3 limitado à ss_wage_base do FICA (default 168600 se sem config). Box12 só inclui códigos não-zero. SSN é descriptografado e mascarado para os 4 últimos dígitos. |
| **Efeitos colaterais** | Nenhum (somente leitura); apenas descriptografa SSN para exibição parcial. |
| **Pré-condições** | Empresa cadastrada; holerites do ano já submetidos; idealmente FICA do ano configurado para a base de SS da Box 3. |

## Penhoras (Wage Garnishments)

**Objetivo.** Gerenciar ordens de penhora salarial por funcionário (pensão, levy fiscal, empréstimo estudantil, credor), com prioridade legal e teto federal, aplicadas pós-imposto na geração dos holerites.

**Ações:**
- `add-garnishment` — Cria ordem de penhora com tipo, valor/percentual, prioridade e teto federal.
- `update-garnishment` — Atualiza status, valor, total devido ou data-fim da penhora.
- `list-garnishments` — Lista penhoras por funcionário/empresa/status, ordenadas por prioridade.
- `get-garnishment` — Retorna uma penhora pelo id.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --employee-id, --order-number, --creditor-name, --garnishment-type, --start-date (obrig.), --amount-or-percentage, --is-percentage, --total-owed, --end-date. update: --garnishment-id + campos. list: --employee-id, --company-id, --status. get: --garnishment-id. |
| **Saídas** | add: garnishment_id, priority. update: updated=true. list: garnishments[], count. get: registro completo. |
| **Regras de negócio** | garnishment-type em (child_support, tax_levy, student_loan, creditor) com prioridade 1-4 nessa ordem; teto (max_percentage) 50% para child_support, 25% para os demais. Status válidos: active/paused/completed/cancelled. Criada com status 'active' e cumulative_paid=0. Na folha, aplica-se por prioridade sobre a renda disponível, respeitando teto e saldo devedor. |
| **Efeitos colaterais** | add insere em wage_garnishment + auditoria; update faz dynamic_update + auditoria; list/get somente leitura. O cumulative_paid e o status 'completed' são atualizados em generate-salary-slips (não nestas ações). |
| **Pré-condições** | Funcionário existente (a empresa é derivada do funcionário). |

## Horas Extras (Overtime)

**Objetivo.** Configurar a política de horas extras da empresa e calcular HE de um funcionário a partir da frequência (attendance), integrando o valor de HE ao bruto na geração de holerites.

**Ações:**
- `add-overtime-policy` — Cria/atualiza (upsert) a política de HE da empresa: limiares semanal/diário e multiplicadores.
- `calculate-overtime` — Calcula horas regulares/extras e valores de um funcionário no período a partir da attendance.

| Campo | Detalhe |
|---|---|
| **Entradas** | policy: --company-id (obrig.), --weekly-threshold (default 40), --daily-threshold, --ot-multiplier (default 1.5), --double-ot-multiplier (default 2.0). calculate: --employee-id, --period-start, --period-end (obrig.), --hourly-rate (senão derivado da atribuição). |
| **Saídas** | policy: company_id e parâmetros gravados. calculate: total_hours, regular_hours, ot_hours, hourly_rate, ot_multiplier, regular_amount, ot_amount, total_amount. |
| **Regras de negócio** | Empresa deve existir; multiplicadores e limiares não-negativos. Upsert ON CONFLICT(company_id). Hora derivada = salário-base*12/2080. HE = maior entre HE diária (horas>daily_threshold) e HE semanal (total - weekly_threshold*nº semanas), sem dupla contagem. Considera attendance com status present/work_from_home/half_day (working_hours default 8). |
| **Efeitos colaterais** | add-overtime-policy faz upsert em overtime_policy (sem auditoria). calculate-overtime é somente leitura. Observação: a integração de HE ao bruto e a criação do componente 'Overtime Pay' ocorrem em generate-salary-slips. |
| **Pré-condições** | Empresa cadastrada e política de HE existente (para calculate); registros de attendance no período; salary_assignment vigente se não for passada --hourly-rate. |

## Retro (Pagamento Retroativo)

**Objetivo.** Calcular pagamento retroativo de um funcionário comparando a taxa-base atual com a anterior e gerando ajustes por período afetado.

**Ações:**
- `calculate-retro-pay` — Compara as duas últimas atribuições e gera ajustes retroativos por período afetado.

| Campo | Detalhe |
|---|---|
| **Entradas** | --employee-id (obrig.), --from-date, --to-date (limitam o intervalo). |
| **Saídas** | employee_id, periods_affected, total_retro_amount, details[] (period_from, period_to, old_rate, new_rate, adjustment_amount); mensagem se não houver retro. |
| **Regras de negócio** | Exige >= 2 atribuições salariais. Compara as duas mais recentes; se a atual não for maior que a anterior, retorna 0 sem gerar ajustes. Intervalo padrão = effective_from da anterior até o da atual, ajustável por from/to-date. Ajuste por período = diferença de taxa-base (rate_diff). Se houver slips no intervalo, gera um ajuste por slip; senão, gera por períodos aproximados de 30 dias. |
| **Efeitos colaterais** | Insere registros em retro_pay_adjustment com status 'pending'. Sem postagem no GL e sem auditoria nesta ação. |
| **Pré-condições** | Funcionário com pelo menos duas atribuições salariais no histórico. |

## ACH/NACHA (Depósito Direto)

**Objetivo.** Gerenciar contas bancárias dos funcionários (com criptografia em repouso) e gerar o arquivo NACHA/ACH de pagamento líquido a partir de uma corrida submetida.

**Ações:**
- `add-employee-bank-account` — Cadastra conta bancária do funcionário para depósito direto, criptografando routing/conta.
- `list-employee-bank-accounts` — Lista contas do funcionário com número de conta mascarado.
- `generate-nacha-file` — Gera o arquivo NACHA de largura fixa (registros 1/5/6/8/9) com os líquidos da corrida.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --employee-id, --bank-name, --routing-number, --account-number (obrig.), --account-type (checking/savings, default checking). list: --employee-id. nacha: --payroll-run-id. |
| **Saídas** | add: employee_bank_account_id e dados básicos. list: accounts[] (account_number mascarado, routing descriptografado), count. nacha: file_content, entry_count, total_amount, payroll_run_id. |
| **Regras de negócio** | routing-number exatamente 9 dígitos; account-number 4-17 dígitos; account-type checking/savings (conta criada como is_primary=1). NACHA exige corrida em status 'submitted' ou 'paid'; usa apenas conta primária por funcionário e líquido > 0; txn code 22(checking)/32(savings); monta header de arquivo/lote, entry details, batch e file control com entry hash e totais em centavos. |
| **Efeitos colaterais** | add-employee-bank-account insere em employee_bank_account (campos sensíveis criptografados) + auditoria. list e generate-nacha-file são somente leitura (descriptografam para exibir/montar o arquivo); o arquivo é retornado no JSON, não persistido. |
| **Pré-condições** | Funcionário existente; para NACHA, corrida submetida/paga com holerites não-cancelados e funcionários com conta bancária primária cadastrada. |

## Status

**Objetivo.** Retornar um painel de métricas e contagens do domínio de folha (componentes, estruturas, atribuições ativas, corridas por status, holerites, configs FICA/IR/FUTA-SUTA e última corrida).

**Ações:**
- `status` — Resumo agregado de contadores da folha, opcionalmente filtrado por empresa.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id (opcional, filtra contagens scoped por empresa). |
| **Saídas** | total_salary_components e por tipo, total/active salary_structures, total/active salary_assignments, total_payroll_runs e por status, total_salary_slips, fica_configs e fica_years, total_income_tax_slabs e por jurisdição, futa_suta_configs e latest_payroll_run. |
| **Regras de negócio** | Componentes salariais são globais (não filtrados por empresa); demais contagens respeitam --company-id quando informado. Atribuições 'ativas' = effective_to nula ou futura e effective_from <= hoje. Última corrida ordenada por period_end desc. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Banco inicializado com as tabelas do domínio; empresa opcional para filtro. |

