# Folha de Pagamento — `glue-payroll`

> Spec funcional por ação. Gerada de `scripts/glue-payroll/db_query.py`. 13 funcionalidades · 30 ações.

## Componentes

**Objetivo.** Cria e lista componentes salariais (proventos, descontos e contribuições do empregador) que servem de blocos para as estruturas salariais.

### `add-salary-component`

Cria um componente salarial (earning, deduction ou employer_contribution) com suas flags fiscais.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --component-type (obrigatório: earning\|deduction\|employer_contribution); --is-tax-applicable (default 1); --is-statutory (default 0); --is-pre-tax (default 0); --variable-based-on-taxable-salary (default 0); --depends-on-payment-days (default 1); --is-supplemental (default 0); --gl-account-id; --description. |
| **Saídas** | salary_component_id, name, component_type. |
| **Regras** | component_type deve estar em (earning, deduction, employer_contribution); nome único (erro se já existe); se --gl-account-id informado o account deve existir; flags booleanas aceitam 1/0, true/false, yes/no. Sem ciclo draft/submit. |
| **Efeitos colaterais** | Insere 1 linha em salary_component; grava audit_log (add-salary-component). 2 commits. |
| **Pré-condições** | Tabelas company e employee existem (REQUIRED_TABLES); GL account opcional precisa existir se informado. |

### `list-salary-components`

Lista componentes salariais com filtro opcional por tipo e busca textual, paginado.

| | |
|---|---|
| **Entradas** | --component-type (filtro opcional, validado contra os tipos válidos); --search (LIKE no name); --limit (default 20); --offset (default 0). |
| **Saídas** | count, components[] (id, name, component_type, flags, gl_account_id, description, created_at, updated_at), limit, offset, has_more. |
| **Regras** | Se --component-type informado e inválido, erro. Ordena por name. has_more = offset+limit < total. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma além das tabelas base. |

## Estruturas

**Objetivo.** Define estruturas salariais (conjunto de componentes com valor fixo, percentual ou fórmula) e permite consultá-las.

### `add-salary-structure`

Cria uma estrutura salarial com seus detalhes de componentes (amount/percentage/formula).

| | |
|---|---|
| **Entradas** | --name (obrigatório); --company-id (obrigatório); --components (obrigatório, JSON array); --payroll-frequency (default monthly: monthly\|biweekly\|weekly). |
| **Saídas** | salary_structure_id, name, payroll_frequency, component_count. |
| **Regras** | Frequência deve ser válida; company deve existir; nome único; cada item do JSON precisa de salary_component_id existente, sem duplicatas; no máximo um de amount/percentage/formula por componente; percentage em [0,100]; base_component_id (se informado) deve existir; currency fixado em USD; is_active=1. |
| **Efeitos colaterais** | Insere 1 linha em salary_structure e N linhas em salary_structure_detail; grava audit_log (add-salary-structure). 2 commits. |
| **Pré-condições** | Company existente; salary_components referenciados já criados. |

### `get-salary-structure`

Retorna uma estrutura salarial com a lista detalhada de seus componentes.

| | |
|---|---|
| **Entradas** | --salary-structure-id (obrigatório). |
| **Saídas** | salary_structure { campos da estrutura, components[] (id, salary_component_id, component_name, component_type, amount, percentage, formula, base_component_id, base_component_name, sort_order), component_count }. |
| **Regras** | Estrutura deve existir (erro caso contrário); enriquece base_component_name a partir de salary_component; ordena por sort_order. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Estrutura salarial existente. |

### `list-salary-structures`

Lista estruturas salariais com filtro por empresa e busca, incluindo a contagem de componentes.

| | |
|---|---|
| **Entradas** | --company-id (filtro); --search (LIKE no name); --limit (default 20); --offset (default 0). |
| **Saídas** | count, structures[] (id, name, payroll_frequency, currency, company_id, is_active, component_count, timestamps), limit, offset, has_more. |
| **Regras** | component_count via subconsulta correlacionada em salary_structure_detail; ordena por name. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma além das tabelas base. |

## Atribuições

**Objetivo.** Vincula uma estrutura salarial a um funcionário com valor-base e vigência, e lista essas atribuições.

### `add-salary-assignment`

Atribui uma estrutura salarial a um funcionário com base_amount e período de vigência, fechando automaticamente a atribuição anterior.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório); --salary-structure-id (obrigatório); --base-amount (obrigatório, decimal texto); --effective-from (obrigatório, YYYY-MM-DD); --effective-to (opcional). |
| **Saídas** | salary_assignment_id, employee_id, salary_structure_id, base_amount, effective_from, effective_to e previous_assignment_closed (se houve). |
| **Regras** | Funcionário e estrutura devem existir; estrutura e funcionário devem ser da mesma company; base_amount não negativo; effective_to >= effective_from; se houver atribuição ativa anterior, ela é fechada com effective_to = dia anterior ao novo effective_from; currency USD; base arredondada. |
| **Efeitos colaterais** | Insere 1 linha em salary_assignment; pode atualizar a linha da atribuição anterior (effective_to/updated_at); grava audit_log (add-salary-assignment). 2 commits. |
| **Pré-condições** | Funcionário e estrutura salarial existentes na mesma empresa. |

### `list-salary-assignments`

Lista atribuições salariais com filtros por funcionário, empresa e janela de datas (sobreposição), paginado.

| | |
|---|---|
| **Entradas** | --employee-id; --company-id; --from-date (atribuição ativa em/depois); --to-date (effective_from <= to-date); --limit (default 20); --offset (default 0). |
| **Saídas** | count, assignments[] (campos da atribuição + employee_name + salary_structure_name), limit, offset, has_more. |
| **Regras** | JOIN com employee e salary_structure; filtros de data tratam effective_to NULL como aberto; ordena por effective_from DESC. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma além das tabelas base. |

## Tabelas de IR

**Objetivo.** Configura faixas progressivas de imposto de renda federal e estadual e o vínculo de estados do funcionário.

### `add-income-tax-slab`

Cria uma faixa (slab) de imposto de renda federal ou estadual com seus brackets de alíquota.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --tax-jurisdiction (obrigatório: federal\|state); --effective-from (obrigatório); --filing-status; --state-code (obrigatório se state); --standard-deduction (default 0); --rates (JSON array de brackets). |
| **Saídas** | income_tax_slab_id, name, tax_jurisdiction, state_code, filing_status, effective_from, standard_deduction, rate_count. |
| **Regras** | jurisdiction válida; state exige state-code (federal ignora state-code); filing_status válido se informado; standard_deduction >= 0; brackets contíguos (from_amount == to_amount anterior), último pode ter to_amount null; rate em [0,100]; to_amount > from_amount. is_active=1. |
| **Efeitos colaterais** | Insere 1 linha em income_tax_slab e N linhas em income_tax_slab_rate; grava audit_log (add-income-tax-slab). 2 commits. |
| **Pré-condições** | Nenhuma específica além das tabelas base. |

### `add-state-tax-slab`

Adiciona um único bracket de imposto estadual para um estado/filing_status.

| | |
|---|---|
| **Entradas** | --state-code (obrigatório); --bracket-start (obrigatório); --rate (obrigatório); --bracket-end (opcional); --filing-status (default single). |
| **Saídas** | state_tax_slab_id, state_code, bracket_start, bracket_end, rate, filing_status. |
| **Regras** | filing_status válido; bracket-start >= 0; bracket-end > bracket-start se informado; rate em [0,100]; state_code uppercase; valores arredondados. |
| **Efeitos colaterais** | Insere 1 linha em state_tax_slab. 1 commit. Não grava audit_log. |
| **Pré-condições** | Nenhuma específica além das tabelas base. |

### `update-employee-state-config`

Define ou atualiza o estado de trabalho e o estado de residência de um funcionário (UPSERT).

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório); --work-state (obrigatório); --residence-state (obrigatório). |
| **Saídas** | employee_id, work_state, residence_state. |
| **Regras** | Funcionário deve existir; estados em uppercase; UPSERT por employee_id (ON CONFLICT atualiza work_state/residence_state/updated_at). |
| **Efeitos colaterais** | Insere ou atualiza 1 linha em employee_state_config. 1 commit. Não grava audit_log. |
| **Pré-condições** | Funcionário existente. |

## Config. de Impostos (FICA/FUTA)

**Objetivo.** Configura por ano-fiscal as alíquotas FICA (Social Security/Medicare) e as bases/alíquotas FUTA/SUTA.

### `update-fica-config`

Insere ou atualiza (UPSERT) as taxas de Social Security e Medicare para um ano-fiscal.

| | |
|---|---|
| **Entradas** | Todos obrigatórios: --tax-year; --ss-wage-base; --ss-employee-rate; --ss-employer-rate; --medicare-employee-rate; --medicare-employer-rate; --additional-medicare-threshold; --additional-medicare-rate. |
| **Saídas** | tax_year, ss_wage_base, ss_employee_rate, ss_employer_rate, medicare_employee_rate, medicare_employer_rate, additional_medicare_threshold, additional_medicare_rate, action (created\|updated). |
| **Regras** | tax_year inteiro em [2000,2100]; todos os campos decimais válidos e não negativos; UPSERT por tax_year (ON CONFLICT atualiza todas as taxas). |
| **Efeitos colaterais** | Insere ou atualiza 1 linha em fica_config; grava audit_log (update-fica-config) com old_values/new_values. 2 commits. |
| **Pré-condições** | Nenhuma específica além das tabelas base. |

### `update-futa-suta-config`

Insere ou atualiza (UPSERT) a configuração FUTA (federal) ou SUTA (estadual) de desemprego por ano-fiscal.

| | |
|---|---|
| **Entradas** | --tax-year (obrigatório); --wage-base (obrigatório); --rate (obrigatório); --state-code (opcional, NULL=FUTA federal, valor=SUTA estadual); --employer-rate-override (opcional). |
| **Saídas** | tax_year, state_code, config_type, wage_base, rate, employer_rate_override, action (created\|updated). |
| **Regras** | tax_year em [2000,2100]; wage_base >= 0; rate em [0,100]; employer_rate_override em [0,100] se informado; UPSERT por (tax_year, state_code). |
| **Efeitos colaterais** | Insere ou atualiza 1 linha em futa_suta_config; grava audit_log (update-futa-suta-config) com old/new. 2 commits. |
| **Pré-condições** | Nenhuma específica além das tabelas base. |

## Ciclos de Folha

**Objetivo.** Gerencia o ciclo de vida do payroll_run: criação em rascunho, geração de holerites, submissão com postagem contábil e cancelamento com estorno.

### `create-payroll-run`

Cria um payroll_run em rascunho para um período de pagamento.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --period-start (obrigatório); --period-end (obrigatório); --department-id (opcional, filtro); --payroll-frequency (default monthly). |
| **Saídas** | payroll_run_id, naming_series, period_start, period_end, payroll_frequency. |
| **Regras** | period_start < period_end; frequência válida; company existe; department existe se informado (resolve por id ou name); erro se houver payroll_run sobreposto não cancelado na mesma empresa; gera naming_series; status='draft', totais zerados. |
| **Efeitos colaterais** | Insere 1 linha em payroll_run (status draft); grava audit_log (create-payroll-run). 1 commit. |
| **Pré-condições** | Company existente; department existente se informado. |

### `generate-salary-slips`

Calcula e gera os holerites (salary_slip) de todos os funcionários elegíveis do payroll_run, com proventos, impostos e descontos.

| | |
|---|---|
| **Entradas** | --payroll-run-id (obrigatório). |
| **Saídas** | payroll_run_id, slips_generated, total_gross, total_deductions, total_net. |
| **Regras** | Run deve existir e estar em 'draft'; apaga slips draft anteriores (regeração); seleciona funcionários ativos com salary_assignment vigente (e department se houver); calcula dias trabalhados/pagos com leave não-pago; proventos fixos/percentuais com proração; hora extra via overtime_policy + attendance; pré-tax 401k/HSA; IR federal progressivo (anualizado) + flat 22%/37% para wages suplementares; IR estadual; FICA (SS com teto, Medicare e Additional Medicare); penhoras pós-tax priorizadas com tetos federais. Erro se não houver funcionários elegíveis. |
| **Efeitos colaterais** | Deleta e insere linhas em salary_slip e salary_slip_detail; pode criar salary_components estatutários (auto); atualiza cumulative_paid e status de wage_garnishment; atualiza totais/employee_count do payroll_run; grava audit_log (generate-salary-slips). 1 commit. Não posta GL. |
| **Pré-condições** | Payroll_run em draft; funcionários ativos com salary_assignment vigente; FICA/tax slabs configurados para cálculo completo. |

### `submit-payroll-run`

Submete o payroll_run: marca holerites como submitted e posta as lançamentos contábeis balanceados no razão.

| | |
|---|---|
| **Entradas** | --payroll-run-id (obrigatório); --cost-center-id (usa centro de custo default se omitido). |
| **Saídas** | payroll_run_id, naming_series, gl_entries (qtd), total_gross, total_net, total_employer_tax. |
| **Regras** | Run deve existir e estar 'draft'; deve ter slips draft; resolve contas de GL (salary_expense e payroll_payable obrigatórias); calcula impostos patronais (SS/Medicare empregador, FUTA, SUTA) por funcionário; monta DR despesa salarial/patronal e CR payroll_payable (por funcionário, com partido), IR federal/estadual, SS, Medicare, FUTA, SUTA; auto-corrige diferenças de arredondamento <=1.00; remove entradas zero; aborta com rollback se o GL falhar. |
| **Efeitos colaterais** | Insere lançamentos em gl_entry via insert_gl_entries (voucher_type payroll_entry); atualiza salary_slip para 'submitted' e payroll_run para 'submitted'; grava audit_log (submit-payroll-run). 1 commit final. |
| **Pré-condições** | Payroll_run em draft com slips gerados; contas de despesa salarial e payroll payable existentes; centro de custo disponível. |

### `cancel-payroll-run`

Cancela um payroll_run submetido, estornando os lançamentos contábeis e marcando holerites como cancelled.

| | |
|---|---|
| **Entradas** | --payroll-run-id (obrigatório). |
| **Saídas** | payroll_run_id, naming_series, reversed_entries (qtd). |
| **Regras** | Run deve existir e estar 'submitted' (erro caso contrário); estorna via reverse_gl_entries; aborta com rollback se o estorno falhar. |
| **Efeitos colaterais** | Cria lançamentos de estorno em gl_entry (reverse_gl_entries); atualiza salary_slip para 'cancelled' e payroll_run para 'cancelled'; grava audit_log (cancel-payroll-run) com old/new. 1 commit final. |
| **Pré-condições** | Payroll_run em status submitted com GL postado. |

## Holerites

**Objetivo.** Consulta individual e listagem dos holerites (salary_slip) gerados, com seus proventos e descontos.

### `get-salary-slip`

Retorna um holerite com seus detalhes aninhados de proventos e descontos.

| | |
|---|---|
| **Entradas** | --salary-slip-id (obrigatório). |
| **Saídas** | Campos do slip no topo + employee_name/first_name/last_name + earnings[], deductions[], details[] (id, salary_component_id, component_name, component_type, amount, year_to_date). |
| **Regras** | Slip deve existir (erro caso contrário); separa detalhes em earnings vs deductions; details = earnings + deductions. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Salary slip existente. |

### `list-salary-slips`

Lista holerites com filtros por payroll run, funcionário e status, paginado.

| | |
|---|---|
| **Entradas** | --payroll-run-id; --employee-id; --status (draft\|submitted\|paid\|cancelled); --limit (default 20); --offset (default 0). |
| **Saídas** | count, slips[] (campos do slip + employee_name), limit, offset, has_more. |
| **Regras** | JOIN com employee; ordena por created_at DESC; has_more = offset+limit < total. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma além das tabelas base. |

## W-2

**Objetivo.** Gera os dados de W-2 de fim de ano para os funcionários a partir dos holerites submetidos.

### `generate-w2-data`

Agrega holerites submetidos do ano e produz os boxes de W-2 por funcionário.

| | |
|---|---|
| **Entradas** | --tax-year (obrigatório); --company-id (obrigatório). |
| **Saídas** | tax_year, company_id, company_name, employee_count, w2_data[] (employee_id, employee_name, ssn_last_four, filing_status, boxes{1..6, 12{D,W}}). |
| **Regras** | tax_year inteiro; company deve existir; soma todos os slips submitted do ano; Box1=gross-pretax, Box2=federal, Box3=min(gross, ss_wage_base), Box4=SS, Box5=gross, Box6=Medicare, Box12 D=401k, W=HSA (só se >0); ss_wage_base de fica_config (default 168600); SSN descriptografado e exposto só nos últimos 4 dígitos. |
| **Efeitos colaterais** | nenhum (leitura). Lê salary_slip/salary_slip_detail/salary_component/employee/company/fica_config; descriptografa SSN. |
| **Pré-condições** | Holerites submetidos no ano-fiscal; company existente; idealmente fica_config do ano. |

## Penhoras

**Objetivo.** Gerencia ordens de penhora salarial (wage garnishment) por funcionário, com prioridade federal e tetos.

### `add-garnishment`

Adiciona uma ordem de penhora salarial para um funcionário.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório); --order-number (obrigatório); --creditor-name (obrigatório); --garnishment-type (obrigatório: child_support\|tax_levy\|student_loan\|creditor); --start-date (obrigatório); --amount-or-percentage (default 0); --is-percentage (flag); --total-owed; --end-date. |
| **Saídas** | garnishment_id, priority. |
| **Regras** | Funcionário deve existir; type válido; priority derivada do tipo (child_support=1..creditor=4); max_percentage 50 para child_support, senão 25; status inicial 'active', cumulative_paid '0'. |
| **Efeitos colaterais** | Insere 1 linha em wage_garnishment; grava audit_log (add-garnishment). 1 commit. |
| **Pré-condições** | Funcionário existente. |

### `update-garnishment`

Atualiza campos de uma penhora (status, valor, total devido, data final).

| | |
|---|---|
| **Entradas** | --garnishment-id (obrigatório); --status (active\|paused\|completed\|cancelled); --amount-or-percentage; --total-owed; --end-date. |
| **Saídas** | updated (true). |
| **Regras** | Penhora deve existir; status (se informado) deve ser válido; erro se nenhum campo a atualizar; atualiza updated_at. |
| **Efeitos colaterais** | Atualiza 1 linha em wage_garnishment via dynamic_update; grava audit_log (update-garnishment). 1 commit. |
| **Pré-condições** | Penhora existente. |

### `list-garnishments`

Lista penhoras filtrando por funcionário, empresa e status, ordenadas por prioridade.

| | |
|---|---|
| **Entradas** | --employee-id; --company-id; --status. |
| **Saídas** | garnishments[] (linhas de wage_garnishment), count. |
| **Regras** | Filtros opcionais combinam por AND; ordena por priority e created_at. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma além das tabelas base. |

### `get-garnishment`

Retorna uma penhora individual pelo ID.

| | |
|---|---|
| **Entradas** | --garnishment-id (obrigatório). |
| **Saídas** | Linha completa de wage_garnishment. |
| **Regras** | Erro se a penhora não existir. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Penhora existente. |

## Horas Extras

**Objetivo.** Configura a política de horas extras da empresa e calcula as horas/valores de overtime de um funcionário no período.

### `add-overtime-policy`

Cria ou atualiza (UPSERT) a política de horas extras de uma empresa.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --weekly-threshold (default 40); --daily-threshold; --ot-multiplier (default 1.5); --double-ot-multiplier (default 2.0). |
| **Saídas** | company_id, weekly_threshold, daily_threshold, ot_multiplier, double_ot_multiplier. |
| **Regras** | Company deve existir; thresholds/multiplicadores numéricos e não negativos; UPSERT por company_id (ON CONFLICT atualiza thresholds/multiplicadores/updated_at). |
| **Efeitos colaterais** | Insere ou atualiza 1 linha em overtime_policy. 1 commit. Não grava audit_log. |
| **Pré-condições** | Company existente. |

### `calculate-overtime`

Calcula horas regulares/extras e valores de overtime de um funcionário em um período a partir da attendance.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório); --period-start (obrigatório); --period-end (obrigatório); --hourly-rate (opcional; senão derivado da salary_assignment). |
| **Saídas** | employee_id, period_start, period_end, total_hours, regular_hours, ot_hours, hourly_rate, ot_multiplier, regular_amount, ot_amount, total_amount. |
| **Regras** | Funcionário deve existir; deve haver overtime_policy da empresa (senão erro); hourly_rate derivado de base_amount*12/2080 se não informado (erro se sem assignment); soma horas de attendance (present/wfh/half_day); OT = max(OT diário, OT semanal=horas acima do weekly_threshold*num_semanas); valores arredondados. |
| **Efeitos colaterais** | nenhum (leitura). Lê employee, overtime_policy, salary_assignment, attendance. |
| **Pré-condições** | Funcionário existente; overtime_policy da empresa; attendance no período; salary_assignment se hourly-rate omitido. |

## Retro

**Objetivo.** Calcula pagamento retroativo comparando a taxa salarial atual com a anterior e registra os ajustes pendentes.

### `calculate-retro-pay`

Calcula pagamento retroativo de um funcionário com base na diferença entre as duas últimas atribuições salariais e registra ajustes.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório); --from-date (opcional); --to-date (opcional). |
| **Saídas** | employee_id, periods_affected, total_retro_amount, details[] (period_from, period_to, old_rate, new_rate, adjustment_amount) e message quando não há retro. |
| **Regras** | Funcionário deve existir; precisa de >=2 salary_assignments (erro caso contrário); compara última (current) vs penúltima (previous); se current_rate <= old_rate retorna 0 sem ajustes; período retro entre os effective_from, limitado por from/to-date; aplica diferença por slip não-cancelado no período, ou por períodos mensais aproximados (30 dias) se não houver slips. |
| **Efeitos colaterais** | Insere N linhas em retro_pay_adjustment (status 'pending'). 1 commit. Não grava audit_log. |
| **Pré-condições** | Funcionário com pelo menos 2 atribuições salariais. |

## ACH/NACHA

**Objetivo.** Cadastra contas bancárias de funcionários (criptografadas) e gera o arquivo NACHA/ACH de depósito direto a partir de um payroll run.

### `add-employee-bank-account`

Cadastra uma conta bancária de funcionário para ACH/depósito direto, com routing/account criptografados.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório); --bank-name (obrigatório); --routing-number (obrigatório, 9 dígitos); --account-number (obrigatório, 4-17 dígitos); --account-type (checking\|savings, default checking). |
| **Saídas** | employee_bank_account_id, employee_id, bank_name, account_type, message. |
| **Regras** | Funcionário deve existir; routing exatamente 9 dígitos numéricos; account 4-17 dígitos numéricos; account_type válido; routing e account são criptografados antes de gravar; is_primary=1. |
| **Efeitos colaterais** | Insere 1 linha em employee_bank_account (campos sensíveis cifrados); grava audit_log (add-employee-bank-account). 1 commit. |
| **Pré-condições** | Funcionário existente. |

### `list-employee-bank-accounts`

Lista as contas bancárias de um funcionário com número de conta mascarado.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório). |
| **Saídas** | accounts[] (campos da conta com account_number mascarado ****+4, account_number_masked, routing_number descriptografado), count. |
| **Regras** | Descriptografa colunas cifradas; mascara account_number (apenas últimos 4); ordena por created_at. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Funcionário existente; contas cadastradas. |

### `generate-nacha-file`

Gera o conteúdo de um arquivo NACHA/ACH de pagamento a partir dos holerites de um payroll run submetido/pago.

| | |
|---|---|
| **Entradas** | --payroll-run-id (obrigatório). |
| **Saídas** | file_content (texto fixed-width NACHA), entry_count, total_amount, payroll_run_id. |
| **Regras** | Run deve existir e estar 'submitted' ou 'paid'; usa slips não cancelados com net_pay>0; cada funcionário precisa de conta primária (senão é pulado); descriptografa routing/account; monta registros tipo 1/5/6/8/9; txn_code 22 (checking) ou 32 (savings); erro se nenhum funcionário com conta bancária. |
| **Efeitos colaterais** | nenhum (leitura). Lê payroll_run, company, salary_slip, employee_bank_account; não persiste o arquivo no banco. |
| **Pré-condições** | Payroll_run submitted/paid com slips; funcionários com employee_bank_account primária. |

## Status

**Objetivo.** Retorna métricas e contagens resumidas do domínio de folha de pagamento.

### `status`

Retorna métricas-resumo de folha: contagens de componentes, estruturas, atribuições ativas, runs por status, holerites, FICA/tax slabs e o run mais recente.

| | |
|---|---|
| **Entradas** | --company-id (opcional, filtra estruturas/atribuições/runs/slips por empresa). |
| **Saídas** | total_salary_components, components_by_type, total/active_salary_structures, total/active_salary_assignments, total_payroll_runs, payroll_runs_by_status, total_salary_slips, fica_configs, fica_years, total_income_tax_slabs, tax_slabs_by_jurisdiction, futa_suta_configs, latest_payroll_run. |
| **Regras** | Componentes e FICA/tax slabs são globais (sem filtro de empresa); atribuições ativas = effective_from<=hoje e effective_to NULL/futuro; latest_payroll_run por period_end DESC. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma além das tabelas base. |

