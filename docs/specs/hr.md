# Recursos Humanos — `erpclaw-hr`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-hr/db_query.py`. 12 funcionalidades · 39 ações.

## Funcionários

**Objetivo.** Cadastrar, atualizar, consultar e listar funcionários, incluindo dados pessoais, vínculo organizacional e parâmetros fiscais/folha (W4, FICA, 401k, HSA).

**Ações:**
- `add-employee` — Cria funcionário com status 'active', gera naming_series e calcula full_name.
- `update-employee` — Atualização dinâmica de campos do funcionário (nome, datas, status, FKs, campos fiscais/folha).
- `get-employee` — Retorna o funcionário com nomes de depto/cargo/grade/lista de feriados e resumos derivados.
- `list-employees` — Lista paginada com filtros e busca textual.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --first-name, --date-of-joining, --company-id (obrigatórios) + opcionais (--last-name, --gender, --employment-type, --department-id, --designation-id, --employee-grade-id, --reporting-to, --emergency-contact/--bank-details JSON, --federal-filing-status, --w4-allowances, --holiday-list-id, --payroll-cost-center-id). update: --employee-id + qualquer campo opcional. get: --employee-id. list: --company-id, --department-id, --designation-id, --status, --employment-type, --search, --limit(20), --offset(0). |
| **Saídas** | add: employee_id, naming_series, full_name. update: employee_id, updated_fields. get: objeto employee (com emergency_contact/bank_details em JSON parseado), leave_balances do ano fiscal corrente, attendance_summary do mês corrente, reporting_to_name e direct_reports_count. list: lista de funcionários, total_count, paginação e has_more. |
| **Regras de negócio** | Validações: gênero em VALID_GENDERS; employment_type em VALID_EMPLOYMENT_TYPES (default full_time); status em VALID_EMPLOYEE_STATUSES; datas ISO YYYY-MM-DD; e-mails por regex; FKs (depto, cargo, grade, gestor, holiday_list, cost_center) devem existir. Funcionário não pode reportar a si mesmo. update exige ao menos um campo; full_name recalculado quando nome muda. |
| **Efeitos colaterais** | add-employee: INSERT em employee + INSERT de evento de ciclo de vida 'hiring' (employee_lifecycle_event) + auditoria. update-employee: UPDATE em employee + auditoria com old/new values. get-employee e list-employees: nenhum (somente leitura). Sem postagens no GL ou estoque. |
| **Pré-condições** | Empresa (company) deve existir; tabela 'company' é dependência obrigatória (REQUIRED_TABLES). FKs referenciadas (departamento, cargo, grade, gestor, holiday_list, cost_center) precisam existir previamente quando informadas. |

## Estrutura Org.

**Objetivo.** Gerir a estrutura organizacional: departamentos (hierárquicos, por empresa) e designações/cargos (job titles globais).

**Ações:**
- `add-department` — Cria departamento vinculado a empresa, com pai e cost center opcionais.
- `list-departments` — Lista departamentos com nome do pai, da empresa e contagem de funcionários ativos.
- `add-designation` — Cria designação (cargo) com nome único global.
- `list-designations` — Lista designações com contagem de funcionários ativos por cargo.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-department: --name, --company-id (obrig.) + --parent-id, --cost-center-id. list-departments: --company-id, --parent-id, --limit, --offset. add-designation: --name (obrig.) + --description. list-designations: --limit, --offset. |
| **Saídas** | add-department: department_id, name. list-departments: departments (com parent_name, company_name, employee_count), total_count, paginação. add-designation: designation_id, name. list-designations: designations (com employee_count), total_count, paginação. |
| **Regras de negócio** | Departamento: empresa deve existir; pai (se informado) deve existir e pertencer à mesma empresa; cost center deve existir; nome único por empresa. Designação: nome é UNIQUE global (duplicidade rejeitada). Contagens consideram apenas funcionários com status 'active'. |
| **Efeitos colaterais** | add-department: INSERT em department + auditoria. add-designation: INSERT em designation + auditoria. list-*: nenhum (somente leitura). Sem GL/estoque. |
| **Pré-condições** | Empresa deve existir para departamento. Cost center e departamento pai (quando usados) precisam existir. Designação não depende de empresa. |

## Tipos/Alocação de Férias

**Objetivo.** Definir tipos de licença/férias e suas regras (pago, carry-forward, compensatório, carência) e alocar saldos por funcionário e ano fiscal, incluindo transporte de saldo do ano anterior.

**Ações:**
- `add-leave-type` — Cria tipo de licença com limites e flags (pago, carry-forward, compensatório, carência).
- `list-leave-types` — Lista os tipos de licença cadastrados.
- `add-leave-allocation` — Aloca dias de licença ao funcionário num ano fiscal, aplicando carry-forward quando habilitado.
- `get-leave-balance` — Retorna o saldo por tipo de licença, com dias pendentes em rascunho.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-leave-type: --name, --max-days-allowed (obrig.) + --is-paid-leave(1), --is-carry-forward(0), --max-carry-forward-days, --is-compensatory(0), --applicable-after-days(0). add-leave-allocation: --employee-id, --leave-type-id, --total-leaves, --fiscal-year (obrig.). get-leave-balance: --employee-id (obrig.) + --leave-type-id, --fiscal-year. |
| **Saídas** | add-leave-type: leave_type_id, name, max_days_allowed. add-leave-allocation: allocation_id, total/used/remaining_leaves, e carry_forwarded/carry_forwarded_from quando aplicável. get-leave-balance: balances por tipo (total/used/remaining + pending_days em rascunho), fiscal_year, total_count. |
| **Regras de negócio** | leave_type.name é UNIQUE; max_days_allowed > 0; flags 0/1; max_carry_forward_days >= 0; applicable_after_days >= 0. Alocação: funcionário/tipo/ano fiscal devem existir; total_leaves >= 0; impede alocação duplicada (mesmo emp+tipo+ano). Carry-forward: se o tipo permite, busca alocação do ano anterior e soma remaining_leaves (limitado a max_carry_forward_days). remaining = total - used (used inicia 0). |
| **Efeitos colaterais** | add-leave-type: INSERT em leave_type + auditoria. add-leave-allocation: INSERT em leave_allocation (com carry_forwarded_from) + auditoria. list/get: nenhum (somente leitura). Sem GL/estoque. |
| **Pré-condições** | Para alocação: funcionário, leave_type e fiscal_year (registro em fiscal_year) devem existir. get-leave-balance usa o ano fiscal aberto corrente quando não informado. |

## Solicitações de Férias

**Objetivo.** Gerir o ciclo de solicitações de licença/férias: criação (rascunho), aprovação com baixa de saldo, rejeição e consulta.

**Ações:**
- `add-leave-application` — Cria solicitação em 'draft' calculando dias úteis (excluindo fins de semana e feriados).
- `approve-leave` — Aprova solicitação 'draft' e deduz used/remaining da alocação.
- `reject-leave` — Rejeita solicitação em 'draft'.
- `list-leave-applications` — Lista solicitações com nomes de funcionário, tipo e aprovador.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --employee-id, --leave-type-id, --from-date, --to-date (obrig.) + --half-day(0/1), --half-day-date, --reason. approve: --leave-application-id, --approved-by (obrig.). reject: --leave-application-id (obrig.) + --reason. list: --employee-id, --status, --from-date, --to-date, --leave-type-id, --limit, --offset. |
| **Saídas** | add: leave_application_id, naming_series, total_days, half_day, status 'draft', holidays_excluded. approve: status 'approved', approver_name, total_days, leave_type. reject: status 'rejected', rejection_reason. list: leave_applications + total_count e paginação. |
| **Regras de negócio** | Ciclo: draft -> approved \| rejected. add: funcionário deve estar 'active'; from <= to; half-day-date dentro do intervalo; respeita applicable_after_days do tipo; total_days = dias úteis excluindo feriados (- 0,5 se half-day) e deve ser > 0; valida saldo suficiente na alocação; bloqueia sobreposição com solicitações draft/approved. approve: exige status 'draft', aprovador válido, não pode aprovar a própria; deduz da alocação e bloqueia saldo negativo (rollback). reject: exige status 'draft'. |
| **Efeitos colaterais** | add: INSERT em leave_application (status draft) + auditoria. approve: UPDATE leave_application (approved, approved_by) + UPDATE leave_allocation (used += total_days, remaining -= total_days) + auditoria. reject: UPDATE leave_application (rejected) + auditoria. list: nenhum (somente leitura). Sem GL/estoque. |
| **Pré-condições** | Funcionário ativo e tipo de licença existentes; alocação de licença para o ano fiscal da from-date (approve faz rollback se não houver alocação ou ano fiscal aberto). Feriados via lista do funcionário ou da empresa. |

## Ponto

**Objetivo.** Registrar e consultar marcações de ponto/presença por funcionário e data, individualmente ou em lote.

**Ações:**
- `mark-attendance` — Marca o ponto de um funcionário numa data com status, horários e flags.
- `bulk-mark-attendance` — Marca o ponto de vários funcionários numa data (pula duplicados, acumula erros).
- `list-attendance` — Lista marcações com nome do funcionário e resumo agregado por status.

| Campo | Detalhe |
|---|---|
| **Entradas** | mark: --employee-id, --date, --status (obrig.) + --shift, --check-in-time, --check-out-time, --working-hours, --late-entry(0/1), --early-exit(0/1), --source. bulk: --date, --entries (JSON [{employee_id,status}]) + --source. list: --employee-id, --from-date, --to-date, --status, --limit, --offset. |
| **Saídas** | mark: attendance_id, employee_name, date, status, source. bulk: total, created, skipped_duplicates, errors[]. list: attendance[] + total_count, paginação e summary (contagens por status: present/absent/half_day/on_leave/work_from_home). |
| **Regras de negócio** | status em VALID_ATTENDANCE_STATUSES; source em VALID_ATTENDANCE_SOURCES (default manual); late_entry/early_exit 0/1; data ISO e não futura (mark). Unicidade por employee_id+attendance_date: mark rejeita duplicado; bulk pula duplicado (skipped_duplicates) e valida cada entrada acumulando erros sem abortar. |
| **Efeitos colaterais** | mark-attendance: INSERT em attendance + auditoria. bulk-mark-attendance: INSERT em attendance por entrada válida (sem auditoria por linha). list: nenhum (somente leitura). Sem GL/estoque. |
| **Pré-condições** | Funcionário deve existir. Não pode haver marcação prévia para a mesma data (chave única employee_id+attendance_date). |

## Regularização

**Objetivo.** Definir regras de regularização de atraso por empresa e aplicá-las às marcações de ponto com atraso, ajustando status ou gerando avisos.

**Ações:**
- `add-regularization-rule` — Cria regra com limite de minutos de atraso e ação (half_day/deduct_leave/warn).
- `apply-attendance-regularization` — Aplica as regras às marcações com late_entry=1 num período.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-regularization-rule: --company-id, --late-threshold-minutes, --regularization-action (obrig.). apply-attendance-regularization: --company-id (obrig.) + --from-date, --to-date. |
| **Saídas** | add: rule_id, company_id, late_threshold_minutes, action. apply: records_processed, records_updated, warnings[] (com employee_id, data, late_minutes) e warning_count. |
| **Regras de negócio** | Ação em VALID_REGULARIZATION_ACTIONS (half_day, deduct_leave, warn); late_threshold_minutes inteiro > 0. apply: processa apenas attendance com late_entry=1 da empresa no período; calcula atraso a partir de check_in_time considerando início às 9h; ao atingir o threshold da primeira regra aplicável: 'half_day' altera status, 'warn'/'deduct_leave' apenas geram aviso (não alteram saldo de licença). |
| **Efeitos colaterais** | add-regularization-rule: INSERT em attendance_regularization_rule + auditoria. apply-attendance-regularization: UPDATE em attendance (status='half_day') para registros com ação half_day; ações warn/deduct_leave NÃO alteram dados (somente avisos). Sem GL/estoque e sem auditoria por registro alterado. |
| **Pré-condições** | Empresa deve existir. apply exige ao menos uma regra de regularização cadastrada para a empresa; depende de marcações de ponto com late_entry=1 e check_in_time preenchido. |

## Feriados

**Objetivo.** Cadastrar listas de feriados por empresa, com entradas filhas de datas, usadas no cálculo de dias úteis das solicitações de licença.

**Ações:**
- `add-holiday-list` — Cria lista de feriados com período e entradas de datas filtradas ao intervalo.

| Campo | Detalhe |
|---|---|
| **Entradas** | --name, --company-id, --from-date, --to-date (obrig.) + --holidays (JSON [{date, description}]). |
| **Saídas** | holiday_list_id, name, from_date, to_date, holiday_count (feriados efetivamente inseridos). |
| **Regras de negócio** | Empresa deve existir; from <= to; holiday_list.name é UNIQUE. Cada feriado precisa de date válida e dentro do intervalo (datas inválidas ou fora do range são ignoradas silenciosamente). |
| **Efeitos colaterais** | INSERT em holiday_list + INSERT em holiday para cada feriado válido + auditoria. Somente escrita nessas tabelas; sem GL/estoque. |
| **Pré-condições** | Empresa deve existir. As listas/feriados são posteriormente consumidos no cálculo de licenças (lista do funcionário ou da empresa). |

## Reembolsos de Despesas

**Objetivo.** Gerir o ciclo de reembolso de despesas de funcionários: rascunho com itens, submissão, aprovação com postagem contábil, rejeição, integração com pagamentos e consulta.

**Ações:**
- `add-expense-claim` — Cria reembolso 'draft' com itens, calcula total e gera naming_series.
- `submit-expense-claim` — Submete reembolso 'draft' para aprovação (status 'submitted').
- `approve-expense-claim` — Aprova reembolso 'submitted' e gera lançamentos no GL (DR despesa / CR conta a pagar).
- `reject-expense-claim` — Rejeita reembolso 'submitted'.
- `update-expense-claim-status` — Atualiza status/payment_entry_id (uso cross-skill por payments, ex.: marcar 'paid').
- `list-expense-claims` — Lista reembolsos com nome do funcionário e contagem de itens.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --employee-id, --expense-date, --company-id, --items (JSON [{expense_type,description,amount,account_id}]) (obrig.). submit/approve/reject: --expense-claim-id (approve também --approved-by; reject opcional --reason). update-status: --expense-claim-id, --status (+ --payment-entry-id). list: --employee-id, --status, --company-id, --from-date, --to-date, --limit, --offset. |
| **Saídas** | add: expense_claim_id, naming_series, total_amount, item_count, status 'draft'. submit: status 'submitted'. approve: status 'approved', gl_entry_count, gl_entry_ids. reject: status 'rejected'. update-status: old_status/new_status. list: expense_claims (com item_count) + total_count e paginação. |
| **Regras de negócio** | Ciclo: draft -> submitted -> approved \| rejected; pode ir a 'paid' via update-status. add: itens não vazios; expense_type em VALID_EXPENSE_TYPES; amount > 0; account_id (se informado) deve existir, não ser grupo e ser da empresa; total = soma dos itens. submit exige 'draft'; approve exige 'submitted' e aprovador válido (não pode aprovar o próprio); reject exige 'submitted'. update-status valida status em VALID_EXPENSE_STATUSES. |
| **Efeitos colaterais** | add: INSERT em expense_claim + expense_claim_item + auditoria. submit/reject: UPDATE de status + auditoria. approve-expense-claim: postagem REAL no GL via insert_gl_entries (voucher_type='expense_claim') — DR conta de despesa de cada item, CR conta a pagar/passivo da empresa pelo total (party employee); UPDATE status='approved' + approval_date + auditoria; rollback se faltar conta a pagar/despesa ou ano fiscal. update-expense-claim-status: UPDATE status e payment_entry_id + auditoria (sem GL). list: somente leitura. Sem SLE de estoque. |
| **Pré-condições** | Funcionário e empresa devem existir; contas dos itens (quando informadas) devem existir/não-grupo/mesma empresa. Para aprovar: empresa precisa de conta a pagar (default_payable_account_id ou conta payable/liability) e conta de despesa default, cost center não-grupo e ano fiscal aberto na data. |

## Turnos

**Objetivo.** Definir tipos de turno por empresa e atribuí-los a funcionários por período.

**Ações:**
- `add-shift-type` — Cria tipo de turno com horários de início/fim e status.
- `list-shift-types` — Lista tipos de turno por empresa/status.
- `update-shift-type` — Atualiza nome/horários/status de um tipo de turno.
- `assign-shift` — Atribui um tipo de turno a um funcionário num intervalo de datas.
- `list-shift-assignments` — Lista atribuições com nome do turno e do funcionário.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-shift-type: --name, --start-time, --end-time, --company-id (obrig.) + --status. update-shift-type: --shift-type-id + campos opcionais. assign-shift: --employee-id, --shift-type-id, --start-date (obrig.) + --end-date, --status. list-shift-types: --company-id, --status, --limit, --offset. list-shift-assignments: --employee-id, --shift-type-id, --status, --company-id, --limit, --offset. |
| **Saídas** | add-shift-type: shift_type_id, name, horários, shift_status. update: registro atualizado (status renomeado para shift_status). assign-shift: shift_assignment_id, datas, assignment_status. list-*: listas + count. |
| **Regras de negócio** | Horários em HH:MM ou HH:MM:SS (regex); status em (active, inactive); shift_type.name é único (validado na criação e atualização). assign-shift: funcionário e tipo de turno devem existir; datas em YYYY-MM-DD; end_date não anterior a start_date. update exige ao menos um campo. |
| **Efeitos colaterais** | add-shift-type: INSERT em shift_type (sem auditoria). update-shift-type: UPDATE em shift_type (sem auditoria). assign-shift: INSERT em shift_assignment (sem auditoria). list-*: somente leitura. Sem GL/estoque. |
| **Pré-condições** | Empresa deve existir (tipo de turno). Funcionário e tipo de turno devem existir para atribuição. |

## Documentos

**Objetivo.** Gerir documentos de funcionários (passaporte, visto, I9, W4, contrato etc.), consultá-los e monitorar vencimentos.

**Ações:**
- `add-employee-document` — Adiciona documento ao funcionário com tipo, nome, validade e status 'active'.
- `list-employee-documents` — Lista documentos de um funcionário com filtros por tipo/status.
- `get-employee-document` — Retorna um documento específico por id.
- `check-expiring-documents` — Lista documentos ativos a vencer em N dias, com dias restantes e flag de vencido.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --employee-id, --document-type, --document-name (obrig.) + --expiry-date, --notes. list: --employee-id (obrig.) + --document-type, --status. get: --document-id (obrig.). check-expiring: --company-id, --days (default 30). |
| **Saídas** | add: employee_document_id, employee_name, document_type, expiry_date. list/get: documento(s) (campos completos). check-expiring: expiring_documents (com days_until_expiry e is_expired), count, days_window. |
| **Regras de negócio** | document_type em VALID_DOCUMENT_TYPES; status em VALID_DOCUMENT_STATUSES (default 'active'); expiry_date ISO YYYY-MM-DD quando informado. check-expiring considera apenas documentos 'active' com expiry_date <= hoje+N dias. |
| **Efeitos colaterais** | add-employee-document: INSERT em employee_document + auditoria. list/get/check-expiring: nenhum (somente leitura). Sem GL/estoque. |
| **Pré-condições** | Funcionário deve existir (add e list). Sem outras dependências contábeis. |

## Eventos de Carreira

**Objetivo.** Registrar eventos do ciclo de vida do funcionário (contratação, promoção, transferência, desligamento etc.), atualizando o cadastro em eventos de saída.

**Ações:**
- `record-lifecycle-event` — Registra evento de ciclo de vida; em separation/resignation/retirement marca o funcionário como 'left' e define date_of_exit.

| Campo | Detalhe |
|---|---|
| **Entradas** | --employee-id, --event-type, --event-date (obrig.) + --details, --old-values, --new-values (JSON). |
| **Saídas** | event_id, employee_name, event_type, event_date; em eventos de saída inclui employee_status_updated=true, new_employee_status='left' e date_of_exit. |
| **Regras de negócio** | event_type em VALID_LIFECYCLE_EVENTS (hiring, confirmation, promotion, transfer, separation, resignation, retirement); event_date ISO. Para separation/resignation/retirement: além de registrar o evento, atualiza employee.status='left' e date_of_exit = event_date. Obs.: 'hiring' também é gerado automaticamente ao criar funcionário em add-employee. |
| **Efeitos colaterais** | INSERT em employee_lifecycle_event + auditoria; em eventos de saída, UPDATE em employee (status='left', date_of_exit). Sem GL/estoque. |
| **Pré-condições** | Funcionário deve existir. Sem dependências contábeis. |

## Status

**Objetivo.** Fornecer um painel-resumo do módulo de RH com contagens e indicadores agregados, opcionalmente por empresa.

**Ações:**
- `status` — Resumo: funcionários por status, departamentos, licenças e ponto do período corrente, reembolsos por status e eventos recentes.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id (opcional, filtra todos os agregados por empresa). |
| **Saídas** | total_employees, employees_by_status, total_departments, leave_summary (ano fiscal corrente), attendance_summary_current_month, expense_claims_by_status, recent_lifecycle_events (últimos 10) e fiscal_year. |
| **Regras de negócio** | Agrega contagens por status/categoria sobre employee, department, leave_application, attendance e expense_claim; licenças e ponto usam o ano fiscal aberto corrente e o mês corrente, respectivamente; quando --company-id é informado, todos os recortes são filtrados pela empresa. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Tabela 'company' presente (dependência do módulo). Indicadores de licença dependem de existir ano fiscal aberto para a data corrente. |

