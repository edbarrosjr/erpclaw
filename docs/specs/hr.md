# Recursos Humanos — `erpclaw-hr`

> Spec funcional por ação. Gerada de `scripts/erpclaw-hr/db_query.py`. 12 funcionalidades · 39 ações.

## Funcionários

**Objetivo.** Cadastro, atualização e consulta de funcionários e seus dados de RH/folha.

### `add-employee`

Cria um novo registro de funcionário com status inicial 'active'.

| | |
|---|---|
| **Entradas** | --first-name (obrigatório), --date-of-joining (obrigatório), --company-id (obrigatório); opcionais: --last-name, --date-of-birth, --gender, --employment-type (default full_time), --department-id, --designation-id, --employee-grade-id, --branch, --reporting-to, --company-email, --personal-email, --cell-phone, --emergency-contact (JSON), --bank-details (JSON), --federal-filing-status, --w4-allowances (default 0), --holiday-list-id, --payroll-cost-center-id. |
| **Saídas** | employee_id, naming_series, full_name, message. |
| **Regras** | Valida existência de company e dos FKs informados (department/designation/grade/reporting-to/holiday-list/cost-center); valida gender, employment_type e federal_filing_status contra listas válidas; valida formatos de datas (YYYY-MM-DD) e de e-mails (regex); calcula full_name = first+last; gera naming_series via get_next_name; status fixo 'active'. |
| **Efeitos colaterais** | INSERT em employee; INSERT em employee_lifecycle_event (event_type='hiring'); audit_log via audit(); commit. |
| **Pré-condições** | Company existente; FKs referenciados (se informados) devem existir. |

### `update-employee`

Atualiza dinamicamente campos de um funcionário existente.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório); opcionais (qualquer subconjunto): --first-name, --last-name, --date-of-birth, --gender, --date-of-joining, --date-of-exit, --employment-type, --status, --department-id, --designation-id, --employee-grade-id, --branch, --reporting-to, --company-email, --personal-email, --cell-phone, --emergency-contact, --bank-details, --federal-filing-status, --w4-allowances, --w4-additional-withholding, --state-filing-status, --state-withholding-allowances, --employee-401k-rate, --hsa-contribution, --is-exempt-from-fica, --salary-structure-id, --leave-policy-id, --shift-id, --holiday-list-id, --attendance-device-id, --payroll-cost-center-id. |
| **Saídas** | employee_id, updated_fields (lista de campos alterados), message. |
| **Regras** | Funcionário deve existir; recomputa full_name se nome muda; valida formatos de data/e-mail e enums (gender/employment_type/status/federal_filing_status); impede reporting_to == próprio employee; FKs validados quando não-vazios; erro se nenhum campo a atualizar. |
| **Efeitos colaterais** | UPDATE em employee (dynamic_update, inclui updated_at); audit_log com old/new values; commit. |
| **Pré-condições** | Funcionário existente; FKs informados devem existir. |

### `get-employee`

Retorna detalhes de um funcionário com saldos de férias, resumo de ponto e cadeia de reporte.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório). |
| **Saídas** | employee (linha completa com department_name, designation_name, employee_grade_name, holiday_list_name, emergency_contact/bank_details parseados, leave_balances do ano fiscal corrente, attendance_summary do mês corrente, reporting_to_name, direct_reports_count). |
| **Regras** | Erro se funcionário não existir; parseia JSON de emergency_contact/bank_details; saldos de férias só preenchidos se houver ano fiscal aberto para hoje; resumo de ponto agrega o mês corrente. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Funcionário existente. |

### `list-employees`

Lista funcionários com filtros e paginação.

| | |
|---|---|
| **Entradas** | Opcionais: --company-id, --department-id, --designation-id, --status, --employment-type, --search (full_name/naming_series/company_email/cell_phone), --limit (default 20), --offset (default 0). |
| **Saídas** | employees (com department_name/designation_name), total_count, limit, offset, has_more. |
| **Regras** | Valida status e employment_type contra enums quando informados; ordena por full_name; busca via LIKE em 4 campos. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma (tabela company exigida na dependência do módulo). |

## Estrutura Org.

**Objetivo.** Gestão de departamentos e cargos (designações) da organização.

### `add-department`

Cria um novo departamento dentro de uma empresa.

| | |
|---|---|
| **Entradas** | --name (obrigatório), --company-id (obrigatório); opcionais: --parent-id, --cost-center-id. |
| **Saídas** | department_id, name, message. |
| **Regras** | Valida company; valida parent (deve existir e pertencer à mesma company); valida cost_center se informado; impede nome duplicado dentro da mesma company. |
| **Efeitos colaterais** | INSERT em department; audit_log; commit. |
| **Pré-condições** | Company existente; parent/cost-center (se informados) existentes. |

### `list-departments`

Lista departamentos com nome do pai, da empresa e contagem de funcionários ativos.

| | |
|---|---|
| **Entradas** | Opcionais: --company-id, --parent-id, --limit (default 20), --offset (default 0). |
| **Saídas** | departments (com parent_name, company_name, employee_count), total_count, limit, offset, has_more. |
| **Regras** | Conta apenas funcionários com status 'active' por departamento; ordena por name. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `add-designation`

Cria uma nova designação (cargo/título).

| | |
|---|---|
| **Entradas** | --name (obrigatório); opcional: --description. |
| **Saídas** | designation_id, name, message. |
| **Regras** | designation.name é UNIQUE: erro se já existir. |
| **Efeitos colaterais** | INSERT em designation; audit_log; commit. |
| **Pré-condições** | Nenhuma. |

### `list-designations`

Lista todas as designações com contagem de funcionários ativos.

| | |
|---|---|
| **Entradas** | Opcionais: --limit (default 20), --offset (default 0). |
| **Saídas** | designations (com employee_count), total_count, limit, offset, has_more. |
| **Regras** | Conta apenas funcionários 'active' por designação; ordena por name. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Tipos/Alocação de Férias

**Objetivo.** Definição de tipos de férias/licença e alocação anual de dias por funcionário, incluindo saldos.

### `add-leave-type`

Cria um novo tipo de licença/férias com regras de dias e carry-forward.

| | |
|---|---|
| **Entradas** | --name (obrigatório), --max-days-allowed (obrigatório); opcionais: --is-paid-leave (default 1), --is-carry-forward (default 0), --max-carry-forward-days, --is-compensatory (default 0), --applicable-after-days (default 0). |
| **Saídas** | leave_type_id, name, max_days_allowed, message. |
| **Regras** | max_days_allowed deve ser > 0; leave_type.name é UNIQUE; flags booleanas restritas a 0/1; max_carry_forward_days >= 0; applicable_after_days inteiro >= 0. |
| **Efeitos colaterais** | INSERT em leave_type; audit_log; commit. |
| **Pré-condições** | Nenhuma. |

### `list-leave-types`

Lista todos os tipos de licença/férias.

| | |
|---|---|
| **Entradas** | Opcionais: --limit (default 20), --offset (default 0). |
| **Saídas** | leave_types (campos completos), total_count, limit, offset, has_more. |
| **Regras** | Ordena por name. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `add-leave-allocation`

Aloca dias de férias a um funcionário para um ano fiscal, aplicando carry-forward quando configurado.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório), --leave-type-id (obrigatório), --total-leaves (obrigatório), --fiscal-year (obrigatório). |
| **Saídas** | allocation_id, employee_id, leave_type, fiscal_year, total_leaves, used_leaves, remaining_leaves, message; (carry_forwarded, carry_forwarded_from se aplicável). |
| **Regras** | Valida employee, leave_type e existência do fiscal_year; total_leaves >= 0; impede alocação duplicada (employee+leave_type+fiscal_year); se leave_type.is_carry_forward, soma remaining da alocação do ano anterior (limitado por max_carry_forward_days); used_leaves=0 e remaining=total na criação. |
| **Efeitos colaterais** | INSERT em leave_allocation; audit_log; commit. |
| **Pré-condições** | Funcionário, tipo de licença e ano fiscal (por nome) existentes; sem alocação prévia para a mesma combinação. |

### `get-leave-balance`

Retorna o saldo de férias de um funcionário por tipo no ano fiscal.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório); opcionais: --leave-type-id, --fiscal-year (default ano fiscal corrente). |
| **Saídas** | employee_id, fiscal_year, balances (allocation_id, leave_type_id/name, is_paid_leave, total/used/remaining_leaves, pending_days), total_count. |
| **Regras** | Funcionário deve existir; se fiscal_year omitido usa o ano fiscal aberto de hoje (erro se inexistente); valida leave_type se filtrado; calcula pending_days somando total_days de leave_application em status 'draft'. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Funcionário existente; ano fiscal aberto se não informado. |

## Solicitações de Férias

**Objetivo.** Ciclo de vida das solicitações de férias: criação (rascunho), aprovação, rejeição e listagem.

### `add-leave-application`

Cria uma solicitação de férias em status 'draft' calculando dias úteis.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório), --leave-type-id (obrigatório), --from-date (obrigatório), --to-date (obrigatório); opcionais: --half-day (0/1), --half-day-date (default from-date), --reason. |
| **Saídas** | leave_application_id, naming_series, employee_id, leave_type, from_date, to_date, total_days, half_day, status='draft', holidays_excluded, message. |
| **Regras** | Funcionário deve estar 'active'; valida datas e from<=to; total_days = dias úteis (exclui fins de semana e feriados do funcionário, -0.5 se half_day); erro se total_days<=0; respeita applicable_after_days do tipo; checa saldo na leave_allocation do ano fiscal (erro se insuficiente ou sem alocação); impede sobreposição com applications draft/approved; gera naming_series. |
| **Efeitos colaterais** | INSERT em leave_application (status draft); audit_log; commit. |
| **Pré-condições** | Funcionário ativo; leave_type existente; alocação de férias no ano fiscal do from-date. |

### `approve-leave`

Aprova uma solicitação de férias em rascunho e deduz o saldo alocado.

| | |
|---|---|
| **Entradas** | --leave-application-id (obrigatório), --approved-by (obrigatório). |
| **Saídas** | leave_application_id, status='approved', approved_by, approver_name, total_days, leave_type, message. |
| **Regras** | Application deve existir e estar 'draft'; approved_by deve ser funcionário válido e diferente do solicitante; deduz used_leaves += e remaining_leaves -= na leave_allocation do ano fiscal; rollback+erro se saldo ficaria negativo, sem alocação ou sem ano fiscal aberto. |
| **Efeitos colaterais** | UPDATE leave_application (status/approved_by); UPDATE leave_allocation (used/remaining); audit_log; commit. |
| **Pré-condições** | Application em 'draft'; aprovador válido; alocação existente no ano fiscal. |

### `reject-leave`

Rejeita uma solicitação de férias em rascunho.

| | |
|---|---|
| **Entradas** | --leave-application-id (obrigatório); opcional: --reason (default 'No reason provided'). |
| **Saídas** | leave_application_id, status='rejected', leave_type, employee_id, rejection_reason, message. |
| **Regras** | Application deve existir e estar 'draft'; não altera saldo de alocação. |
| **Efeitos colaterais** | UPDATE leave_application (status='rejected'); audit_log; commit. |
| **Pré-condições** | Application em 'draft'. |

### `list-leave-applications`

Lista solicitações de férias com filtros e paginação.

| | |
|---|---|
| **Entradas** | Opcionais: --employee-id, --status, --leave-type-id, --from-date, --to-date, --limit (default 20), --offset (default 0). |
| **Saídas** | leave_applications (com employee_name/series, leave_type_name, approved_by_name), total_count, limit, offset, has_more. |
| **Regras** | Valida status contra VALID_LEAVE_STATUSES quando informado; ordena por created_at desc; from-date filtra >=, to-date filtra <=. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Ponto

**Objetivo.** Registro de presença (individual e em lote) e consulta de ponto dos funcionários.

### `mark-attendance`

Registra a presença de um funcionário em uma data.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório), --date (obrigatório), --status (obrigatório); opcionais: --shift, --check-in-time, --check-out-time, --working-hours, --late-entry (0/1, default 0), --early-exit (0/1, default 0), --source (manual\|biometric\|app, default manual). |
| **Saídas** | attendance_id, employee_id, employee_name, date, status, source, message. |
| **Regras** | Funcionário deve existir; data válida e não futura; valida status/source/late_entry/early_exit; impede duplicidade por (employee_id, attendance_date). |
| **Efeitos colaterais** | INSERT em attendance; audit_log; commit. |
| **Pré-condições** | Funcionário existente; sem registro de ponto prévio para a mesma data. |

### `bulk-mark-attendance`

Registra presença para vários funcionários numa data, pulando duplicados.

| | |
|---|---|
| **Entradas** | --date (obrigatório), --entries (JSON array de {employee_id, status}, obrigatório); opcional: --source (default manual). |
| **Saídas** | date, total, created, skipped_duplicates, errors (lista), message. |
| **Regras** | Valida data e source; cada entry exige employee_id e status válido e funcionário existente (caso contrário adiciona à lista errors e continua); registros já existentes na data contam como skipped_duplicates; late_entry/early_exit fixos em 0. |
| **Efeitos colaterais** | INSERT em attendance por entry válida e não duplicada; commit (sem audit_log). |
| **Pré-condições** | Funcionários referenciados existentes (entradas inválidas são apenas reportadas). |

### `list-attendance`

Lista registros de ponto com filtros, paginação e resumo agregado.

| | |
|---|---|
| **Entradas** | Opcionais: --employee-id, --from-date, --to-date, --status, --limit (default 20), --offset (default 0). |
| **Saídas** | attendance (com employee_name/series), total_count, limit, offset, has_more, summary (contagens por status). |
| **Regras** | Valida status contra enum quando informado; ordena por attendance_date desc e full_name; summary usa os mesmos filtros. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Regularização

**Objetivo.** Regras de regularização de atrasos e sua aplicação em massa sobre registros de ponto.

### `add-regularization-rule`

Adiciona uma regra de regularização de atraso para uma empresa.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório), --late-threshold-minutes (obrigatório), --regularization-action (obrigatório: half_day\|deduct_leave\|warn). |
| **Saídas** | rule_id, company_id, late_threshold_minutes, action, message. |
| **Regras** | Company deve existir; late_threshold_minutes inteiro > 0; action restrita a VALID_REGULARIZATION_ACTIONS. |
| **Efeitos colaterais** | INSERT em attendance_regularization_rule; audit_log; commit. |
| **Pré-condições** | Company existente. |

### `apply-attendance-regularization`

Aplica as regras de regularização aos registros de ponto com atraso de uma empresa.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); opcionais: --from-date, --to-date. |
| **Saídas** | records_processed, records_updated, warnings (lista), warning_count. |
| **Regras** | Erro se não houver regras para a company; processa attendance com late_entry=1; calcula minutos de atraso a partir de check_in_time (referência 9h); para a primeira regra cujo threshold é atingido aplica: half_day (atualiza status), warn ou deduct_leave (apenas registra warning). |
| **Efeitos colaterais** | UPDATE attendance SET status='half_day' para registros que casam regra half_day; commit; warn/deduct_leave não escrevem (apenas reportam). |
| **Pré-condições** | Pelo menos uma regra de regularização cadastrada para a company. |

## Feriados

**Objetivo.** Criação de listas de feriados e suas datas para cálculo de dias úteis.

### `add-holiday-list`

Cria uma lista de feriados com datas-filho opcionais para uma empresa.

| | |
|---|---|
| **Entradas** | --name (obrigatório), --company-id (obrigatório), --from-date (obrigatório), --to-date (obrigatório); opcional: --holidays (JSON array de {date, description}). |
| **Saídas** | holiday_list_id, name, from_date, to_date, holiday_count, message. |
| **Regras** | Company deve existir; datas válidas e from<=to; holiday_list.name é UNIQUE; feriados com data inválida ou fora do intervalo são ignorados (não contam). |
| **Efeitos colaterais** | INSERT em holiday_list e em holiday (um por feriado válido); audit_log; commit. |
| **Pré-condições** | Company existente. |

## Reembolsos de Despesas

**Objetivo.** Ciclo de vida das despesas de funcionários: rascunho, submissão, aprovação com lançamento contábil, rejeição, atualização de status e listagem.

### `add-expense-claim`

Cria uma despesa de funcionário em status 'draft' com itens.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório), --expense-date (obrigatório), --company-id (obrigatório), --items (JSON array de {expense_type, description, amount, account_id}, obrigatório). |
| **Saídas** | expense_claim_id, naming_series, employee_id, employee_name, expense_date, total_amount, item_count, status='draft', message. |
| **Regras** | Valida employee, company e data; cada item exige expense_type válido e amount>0; account_id (se informado) deve existir, não ser grupo e pertencer à mesma company; total_amount = soma dos itens (arredondada); gera naming_series. |
| **Efeitos colaterais** | INSERT em expense_claim (status draft) e em expense_claim_item (um por item); audit_log; commit. |
| **Pré-condições** | Funcionário e company existentes; contas dos itens válidas se informadas. |

### `submit-expense-claim`

Submete uma despesa em rascunho para aprovação.

| | |
|---|---|
| **Entradas** | --expense-claim-id (obrigatório). |
| **Saídas** | expense_claim_id, naming_series, status='submitted', message. |
| **Regras** | Despesa deve existir e estar 'draft'. |
| **Efeitos colaterais** | UPDATE expense_claim (status='submitted'); audit_log; commit. |
| **Pré-condições** | Despesa em 'draft'. |

### `approve-expense-claim`

Aprova uma despesa submetida e gera lançamentos contábeis (GL).

| | |
|---|---|
| **Entradas** | --expense-claim-id (obrigatório), --approved-by (obrigatório). |
| **Saídas** | expense_claim_id, naming_series, status='approved', approved_by, approver_name, total_amount, gl_entry_count, gl_entry_ids, message. |
| **Regras** | Despesa deve existir e estar 'submitted'; approved_by funcionário válido e diferente do solicitante; exige itens; resolve conta a pagar (default_payable_account_id da company, ou conta payable, ou liability) e conta de despesa (account_id do item ou default_expense_account_id/conta expense); exige cost center e ano fiscal aberto; DR conta de despesa por item, CR conta a pagar pelo total (party employee); rollback+erro em qualquer falha de GL/contas. |
| **Efeitos colaterais** | INSERT em gl_entry (via insert_gl_entries) — DR despesas / CR a pagar; UPDATE expense_claim (status='approved', approved_by, approval_date); audit_log; commit. |
| **Pré-condições** | Despesa em 'submitted' com itens; contas a pagar/despesa, cost center e ano fiscal aberto disponíveis para a company. |

### `reject-expense-claim`

Rejeita uma despesa submetida.

| | |
|---|---|
| **Entradas** | --expense-claim-id (obrigatório); opcional: --reason (default 'No reason provided'). |
| **Saídas** | expense_claim_id, naming_series, status='rejected', employee_id, rejection_reason, message. |
| **Regras** | Despesa deve existir e estar 'submitted'; não gera lançamento contábil. |
| **Efeitos colaterais** | UPDATE expense_claim (status='rejected'); audit_log; commit. |
| **Pré-condições** | Despesa em 'submitted'. |

### `update-expense-claim-status`

Atualiza o status (e vínculo de pagamento) de uma despesa; usado entre skills (ex.: pagamentos para marcar 'paid').

| | |
|---|---|
| **Entradas** | --expense-claim-id (obrigatório), --status (obrigatório, deve ser VALID_EXPENSE_STATUSES); opcional: --payment-entry-id. |
| **Saídas** | expense_claim_id, naming_series, old_status, new_status, payment_entry_id, message. |
| **Regras** | Despesa deve existir; status validado contra enum; grava payment_entry_id se informado; não valida transição de estado específica. |
| **Efeitos colaterais** | UPDATE expense_claim (status e opcionalmente payment_entry_id, via dynamic_update); audit_log; commit. |
| **Pré-condições** | Despesa existente. |

### `list-expense-claims`

Lista despesas de funcionários com filtros, paginação e contagem de itens.

| | |
|---|---|
| **Entradas** | Opcionais: --employee-id, --status, --company-id, --from-date, --to-date, --limit (default 20), --offset (default 0). |
| **Saídas** | expense_claims (com employee_name/series e item_count via subquery), total_count, limit, offset, has_more. |
| **Regras** | Valida status contra enum quando informado; usa SQL bruto com subquery correlacionada para item_count; ordena por created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Turnos

**Objetivo.** Definição de tipos de turno e atribuição/listagem de turnos por funcionário.

### `add-shift-type`

Cria um tipo de turno com horários de início e fim.

| | |
|---|---|
| **Entradas** | --name (obrigatório), --start-time (obrigatório), --end-time (obrigatório), --company-id (obrigatório); opcional: --status (default 'active'). |
| **Saídas** | shift_type_id, name, start_time, end_time, company_id, shift_status. |
| **Regras** | status restrito a active/inactive; start/end-time no formato HH:MM ou HH:MM:SS; company deve existir; shift_type.name único. |
| **Efeitos colaterais** | INSERT em shift_type; commit (sem audit_log). |
| **Pré-condições** | Company existente; nome de turno não usado. |

### `list-shift-types`

Lista tipos de turno com filtros opcionais.

| | |
|---|---|
| **Entradas** | Opcionais: --company-id, --status, --limit (default 20), --offset (default 0). |
| **Saídas** | shift_types (linhas completas), count. |
| **Regras** | Ordena por name; status comparado em minúsculas. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `update-shift-type`

Atualiza campos de um tipo de turno existente.

| | |
|---|---|
| **Entradas** | --shift-type-id (obrigatório); opcionais: --name, --start-time, --end-time, --status. |
| **Saídas** | linha do shift_type atualizado (com status renomeado para shift_status). |
| **Regras** | Turno deve existir; novo name deve ser único; start/end-time validados (HH:MM[:SS]); status restrito a active/inactive; erro se nenhum campo informado. |
| **Efeitos colaterais** | UPDATE shift_type (SQL bruto, inclui updated_at); commit (sem audit_log). |
| **Pré-condições** | Tipo de turno existente. |

### `assign-shift`

Atribui um tipo de turno a um funcionário num período.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório), --shift-type-id (obrigatório), --start-date (obrigatório); opcionais: --end-date, --status (default 'active'). |
| **Saídas** | shift_assignment_id, employee_id, shift_type_id, start_date, end_date, assignment_status. |
| **Regras** | status restrito a active/inactive; funcionário e tipo de turno devem existir; datas no formato YYYY-MM-DD; end_date não pode ser anterior a start_date. |
| **Efeitos colaterais** | INSERT em shift_assignment; commit (sem audit_log). |
| **Pré-condições** | Funcionário e tipo de turno existentes. |

### `list-shift-assignments`

Lista atribuições de turno com filtros opcionais.

| | |
|---|---|
| **Entradas** | Opcionais: --employee-id, --shift-type-id, --status, --company-id, --limit (default 20), --offset (default 0). |
| **Saídas** | shift_assignments (com shift_name e employee_name), count. |
| **Regras** | JOIN com shift_type e employee; --company-id filtra pela company do funcionário; ordena por start_date desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Documentos

**Objetivo.** Cadastro, consulta e monitoramento de vencimento de documentos dos funcionários.

### `add-employee-document`

Adiciona um documento ao funcionário com status inicial 'active'.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório), --document-type (obrigatório, VALID_DOCUMENT_TYPES), --document-name (obrigatório); opcionais: --expiry-date, --notes. |
| **Saídas** | employee_document_id, employee_id, employee_name, document_type, document_name, expiry_date, message. |
| **Regras** | Funcionário deve existir; document_type validado contra lista (passport/visa/drivers_license/i9/w4/offer_letter/contract/certificate/other); expiry_date validada (YYYY-MM-DD) se informada; status fixo 'active'. |
| **Efeitos colaterais** | INSERT em employee_document; audit_log; commit. |
| **Pré-condições** | Funcionário existente. |

### `list-employee-documents`

Lista os documentos de um funcionário.

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório); opcionais: --document-type, --status. |
| **Saídas** | documents (linhas completas), count. |
| **Regras** | Filtra por document_type/status (minúsculas) quando informados; ordena por created_at. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma (não revalida existência do funcionário). |

### `get-employee-document`

Retorna um documento específico de funcionário.

| | |
|---|---|
| **Entradas** | --document-id (obrigatório). |
| **Saídas** | linha completa do employee_document. |
| **Regras** | Erro se o documento não existir. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Documento existente. |

### `check-expiring-documents`

Lista documentos ativos que vencem dentro de N dias.

| | |
|---|---|
| **Entradas** | Opcionais: --company-id, --days (default 30). |
| **Saídas** | expiring_documents (com employee_name, company_id, days_until_expiry, is_expired), count, days_window. |
| **Regras** | Considera apenas documentos com expiry_date não nula, status 'active' e expiry_date <= hoje+days; filtra por company quando informado; calcula days_until_expiry e is_expired (expiry < hoje); ordena por expiry_date. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Eventos de Carreira

**Objetivo.** Registro de eventos do ciclo de vida do funcionário, com efeito de desligamento.

### `record-lifecycle-event`

Registra um evento de ciclo de vida do funcionário (contratação, promoção, desligamento, etc.).

| | |
|---|---|
| **Entradas** | --employee-id (obrigatório), --event-type (obrigatório, VALID_LIFECYCLE_EVENTS), --event-date (obrigatório); opcionais: --details (JSON), --old-values (JSON), --new-values (JSON). |
| **Saídas** | event_id, employee_id, employee_name, event_type, event_date, message; (employee_status_updated, new_employee_status='left', date_of_exit se desligamento). |
| **Regras** | Funcionário deve existir; event_type validado (hiring/confirmation/promotion/transfer/separation/resignation/retirement); data válida; para separation/resignation/retirement atualiza employee para status 'left' e define date_of_exit. |
| **Efeitos colaterais** | INSERT em employee_lifecycle_event; UPDATE employee (status='left' + date_of_exit) em eventos de desligamento; audit_log; commit. |
| **Pré-condições** | Funcionário existente. |

## Status

**Objetivo.** Resumo geral do módulo de RH com contagens e indicadores agregados.

### `status`

Retorna um resumo do módulo de RH (funcionários, departamentos, férias, ponto, despesas e eventos recentes).

| | |
|---|---|
| **Entradas** | Opcional: --company-id (filtra por empresa). |
| **Saídas** | total_employees, employees_by_status, total_departments, leave_summary, attendance_summary_current_month, expense_claims_by_status, recent_lifecycle_events (últimos 10), fiscal_year. |
| **Regras** | Contagens por status só incluídas quando > 0; leave_summary baseado no ano fiscal corrente; resumo de ponto do mês corrente; tudo filtrável por company. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

