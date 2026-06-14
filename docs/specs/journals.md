# Lançamentos — `erpclaw-journals`

> Spec funcional por ação. Gerada de `scripts/erpclaw-journals/db_query.py`. 11 funcionalidades · 17 ações.

## Criação/edição

**Objetivo.** Criar e alterar lançamentos contábeis em rascunho, validando partidas balanceadas e contas existentes.

### `add-journal-entry`

Cria um novo lançamento contábil (journal entry) em rascunho com suas linhas.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --posting-date (obrigatório); --lines JSON array (obrigatório); --entry-type (default 'journal'); --remark (opcional); --cwip-asset-id (opcional, hook CWIP). |
| **Saídas** | status='created', journal_entry_id, naming_series. |
| **Regras** | entry_type deve estar em VALID_ENTRY_TYPES; lines validadas por _validate_lines (>=2 linhas, debit/credit >=0, não ambos >0, ao menos um >0, total débito==crédito após round_currency); cada account_id deve existir; se --cwip-asset-id, o ativo deve estar 'under_construction' (validado no add, accumulation só no submit). Status inicial 'draft'. |
| **Efeitos colaterais** | INSERT em journal_entry (status='draft') e journal_entry_line; grava audit_log via audit(); commit. Sem postagem em gl_entry. |
| **Pré-condições** | Empresa (company) existente; contas (account) das linhas existentes; se CWIP, asset under_construction. |

### `update-journal-entry`

Atualiza um lançamento em rascunho (data, tipo, remark e/ou substitui linhas).

| | |
|---|---|
| **Entradas** | --journal-entry-id (obrigatório); opcionais --posting-date, --entry-type, --remark, --lines (substitui todas as linhas). |
| **Saídas** | status='updated', journal_entry_id, updated_fields (lista de campos alterados). |
| **Regras** | JE deve existir e status=='draft' (senão erro com sugestão de cancelar). entry_type novo validado contra VALID_ENTRY_TYPES; se --lines, revalida por _validate_lines e existência das contas; erro 'No fields to update' se nada informado. |
| **Efeitos colaterais** | UPDATE em journal_entry (campos + total_debit/total_credit e updated_at); se linhas: DELETE+INSERT em journal_entry_line; grava audit_log; commit. Sem gl_entry. |
| **Pré-condições** | JE existente em status 'draft'; contas das novas linhas existentes. |

## Consulta/listagem

**Objetivo.** Recuperar um lançamento individual ou listar lançamentos com filtros e paginação (somente leitura).

### `get-journal-entry`

Retorna um lançamento contábil com todas as suas linhas.

| | |
|---|---|
| **Entradas** | --journal-entry-id (obrigatório). |
| **Saídas** | id, naming_series, posting_date, entry_type, status, total_debit, total_credit, remark, amended_from, company_id, lines[] (id, account_id, account_name, debit, credit, party_type, party_id, cost_center_id, project_id, remark). |
| **Regras** | JE deve existir (senão erro 'not found'). Linhas ordenadas por line_order com join em account para nome. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | JE existente. |

### `list-journal-entries`

Lista lançamentos de uma empresa com filtros e paginação.

| | |
|---|---|
| **Entradas** | company resolvido por --company-id ou --company (obrigatório resolver um); opcionais --status, --entry-type, --from-date, --to-date, --account-id; --limit (default 20), --offset (default 0). |
| **Saídas** | entries[] (id, naming_series, posting_date, entry_type, status, total_debit, total_credit, remark), total_count, limit, offset, has_more. |
| **Regras** | Filtro obrigatório por company_id (resolve_company_id); --account-id filtra via subquery em journal_entry_line; ordenação por posting_date desc, created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa identificável por id ou nome. |

## Ciclo de vida

**Objetivo.** Transicionar o lançamento entre rascunho, submetido e cancelado, postando ou revertendo entradas no razão (gl_entry).

### `submit-journal-entry`

Submete um rascunho: revalida, posta entradas balanceadas no razão e muda status para 'submitted'.

| | |
|---|---|
| **Entradas** | --journal-entry-id (obrigatório). |
| **Saídas** | status='submitted', journal_entry_id, gl_entries_created; se CWIP: cwip_asset_id, cwip_accumulation_id. |
| **Regras** | JE deve existir e status=='draft'. Revalida linhas; chama validate_gl_entries (is_opening se entry_type=='opening') e insert_gl_entries (allow_cwip se cwip_asset_id). Erros de GL/CWIP abortam (err). Para CWIP: exatamente uma conta capital_work_in_progress debitada, senão erro. |
| **Efeitos colaterais** | INSERT em gl_entry (via insert_gl_entries); se CWIP, registra accumulation (record_cwip_accumulation); UPDATE journal_entry.status='submitted'; grava audit_log; commit (transação única). |
| **Pré-condições** | JE existente em 'draft'; contas/cost centers válidos para postagem; se CWIP, asset under_construction e leg de CWIP presente. |

### `cancel-journal-entry`

Cancela um lançamento submetido, revertendo suas entradas no razão e marcando status 'cancelled'.

| | |
|---|---|
| **Entradas** | --journal-entry-id (obrigatório). |
| **Saídas** | status='cancelled', journal_entry_id, reversed=true. |
| **Regras** | JE deve existir e status=='submitted'. Reverte via reverse_gl_entries; se cwip_asset_id, desfaz accumulations (reverse_cwip_accumulations). Falha de reversão aborta. |
| **Efeitos colaterais** | INSERT de entradas reversas em gl_entry (reverse_gl_entries); se CWIP, desfaz cwip accumulation/carrying value; UPDATE journal_entry.status='cancelled'; grava audit_log; commit. |
| **Pré-condições** | JE existente em status 'submitted' com gl_entries postadas. |

## Retificação

**Objetivo.** Corrigir um lançamento submetido cancelando o original e gerando um novo rascunho vinculado.

### `amend-journal-entry`

Retifica um lançamento submetido: cancela o original e cria um novo rascunho ligado (amended_from).

| | |
|---|---|
| **Entradas** | --journal-entry-id (obrigatório); opcionais --lines (novas linhas; se ausente copia as originais), --posting-date (default data do original), --remark (default remark do original). |
| **Saídas** | status='created', original_id, new_journal_entry_id, new_naming_series. |
| **Regras** | JE deve existir e status=='submitted'. Reverte GL do original e marca-o status='amended'; valida as linhas do novo JE por _validate_lines. Novo JE herda entry_type e company do original, status 'draft', amended_from=original. |
| **Efeitos colaterais** | reverse_gl_entries (entradas reversas em gl_entry); UPDATE original.status='amended'; INSERT novo journal_entry (draft, amended_from) + journal_entry_line; grava audit_log; commit. |
| **Pré-condições** | JE existente em status 'submitted'. |

## Exclusão/duplicação

**Objetivo.** Excluir rascunhos definitivamente ou duplicar um lançamento existente como novo rascunho.

### `delete-journal-entry`

Exclui definitivamente um lançamento em rascunho (cabeçalho e linhas).

| | |
|---|---|
| **Entradas** | --journal-entry-id (obrigatório). |
| **Saídas** | status='deleted', deleted=true. |
| **Regras** | JE deve existir e status=='draft' (senão erro com sugestão de cancelar). Apaga linhas antes do cabeçalho (FK). |
| **Efeitos colaterais** | DELETE em journal_entry_line e journal_entry; grava audit_log (old_values naming_series); commit. |
| **Pré-condições** | JE existente em status 'draft'. |

### `duplicate-journal-entry`

Duplica um lançamento (qualquer status) como um novo rascunho, copiando todas as linhas.

| | |
|---|---|
| **Entradas** | --journal-entry-id (obrigatório); --posting-date (opcional, default data atual UTC). |
| **Saídas** | status='created', new_journal_entry_id, naming_series. |
| **Regras** | JE de origem deve existir; copia account_id/debit/credit/party/cost_center/project/remark das linhas e revalida por _validate_lines. Novo JE herda entry_type e company, status 'draft', remark do original. |
| **Efeitos colaterais** | INSERT novo journal_entry (draft) + journal_entry_line; grava audit_log; commit. Sem gl_entry. |
| **Pré-condições** | JE de origem existente. |

## Intercompany

**Objetivo.** Gerar lançamentos pareados entre duas empresas com contas intercompany de receber/pagar.

### `create-intercompany-je`

Cria dois lançamentos pareados entre empresa origem e destino (DR Intercompany Receivable/CR Revenue e DR Expense/CR Intercompany Payable).

| | |
|---|---|
| **Entradas** | --source-company-id (obrigatório); --target-company-id (obrigatório); --amount (obrigatório, >0); --posting-date (obrigatório); --description (opcional, default 'Intercompany transaction'). |
| **Saídas** | source_je_id, source_naming, target_je_id, target_naming, amount, description. |
| **Regras** | Origem != destino; amount>0; ambas empresas existem e mesma default_currency (senão erro v2). Cria/reaproveita contas Intercompany Receivable (asset) e Payable (liability); exige conta revenue na origem e expense/cogs no destino; usa cost center não-grupo se houver. Ambos JEs entry_type='inter_company', status 'draft', com cross-reference no remark. |
| **Efeitos colaterais** | Pode INSERT em account (contas intercompany ausentes); INSERT 2x journal_entry (draft) e respectivas journal_entry_line; UPDATE remark com referência cruzada; grava audit_log; commit. Sem gl_entry (ficam em rascunho). |
| **Pré-condições** | Duas empresas distintas, existentes, mesma moeda; origem com conta de receita e destino com conta de despesa/CMV não-grupo. |

## Modelos recorrentes

**Objetivo.** Criar e alterar modelos de lançamentos recorrentes que servem de base para geração automática.

### `add-recurring-template`

Cria um modelo de lançamento recorrente com frequência, vigência e linhas.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --template-name (obrigatório); --start-date (obrigatório); --lines JSON (obrigatório); --frequency (default 'monthly'); --entry-type (default 'journal'); --end-date (opcional); --auto-submit (flag, default off); --remark (opcional). |
| **Saídas** | status='created', template_id, naming_series, next_run_date (=start_date). |
| **Regras** | frequency em VALID_FREQUENCIES; entry_type em VALID_ENTRY_TYPES; lines validadas por _validate_lines e contas existentes; status inicial 'active', next_run_date=start_date, lines armazenadas como JSON. |
| **Efeitos colaterais** | INSERT em recurring_journal_template (status='active'); grava audit_log; commit. Não gera journal_entry nem gl_entry. |
| **Pré-condições** | Empresa existente; contas das linhas existentes. |

### `update-recurring-template`

Atualiza um modelo recorrente (nome, frequência, vigência, tipo, remark, auto_submit, linhas e/ou status).

| | |
|---|---|
| **Entradas** | --template-id (obrigatório); opcionais --template-name, --frequency, --end-date, --entry-type, --remark, --auto-submit, --lines, --template-status (apenas 'active'/'paused'). |
| **Saídas** | status='updated', template_id, updated_fields. |
| **Regras** | Template deve existir e status != 'completed'. frequency/entry_type validados; lines revalidadas e contas verificadas; template_status só pode ser 'active' ou 'paused'; erro 'No fields to update' se nada informado. |
| **Efeitos colaterais** | UPDATE em recurring_journal_template (campos informados + updated_at); grava audit_log; commit. |
| **Pré-condições** | Template existente não 'completed'. |

## Consulta de modelos

**Objetivo.** Listar e detalhar modelos de lançamentos recorrentes (somente leitura).

### `list-recurring-templates`

Lista os modelos recorrentes de uma empresa com paginação.

| | |
|---|---|
| **Entradas** | company resolvido por --company-id ou --company (obrigatório); --status (filtro opcional); --limit (default 20), --offset (default 0). |
| **Saídas** | templates[] (id, naming_series, name, frequency, start_date, end_date, next_run_date, last_generated_date, entry_type, auto_submit, remark, status), total_count, limit, offset, has_more. |
| **Regras** | Filtro obrigatório por company_id; filtro opcional por status; ordenado por next_run_date asc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa identificável por id ou nome. |

### `get-recurring-template`

Retorna um modelo recorrente com todos os campos, incluindo as linhas parseadas.

| | |
|---|---|
| **Entradas** | --template-id (obrigatório). |
| **Saídas** | Todos os campos do template (row_to_dict), com 'lines' convertido de JSON para array quando possível. |
| **Regras** | Template deve existir (senão erro 'not found'); tenta json.loads em lines (ignora se falhar). |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Template existente. |

## Processamento de recorrências

**Objetivo.** Gerar lançamentos a partir dos modelos recorrentes vencidos e avançar o calendário de execução.

### `process-recurring`

Gera lançamentos de todos os modelos ativos vencidos (next_run_date <= data) e avança suas datas de execução.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --as-of-date (opcional, default data atual UTC). |
| **Saídas** | generated (contagem), results[] (template_id, template_name, journal_entry_id, naming_series, posting_date, je_status, next_run_date, template_status). |
| **Regras** | Idempotente: só modelos status='active' com next_run_date<=as_of_date. Cria JE 'draft' com posting_date=next_run_date; se auto_submit, valida e posta GL e marca 'submitted' (falha mantém 'draft'). Avança next_run_date por _advance_date; se passar de end_date marca template 'completed'. |
| **Efeitos colaterais** | INSERT journal_entry (draft) + journal_entry_line por modelo; se auto_submit, INSERT em gl_entry e UPDATE je.status='submitted'; UPDATE recurring_journal_template (next_run_date, last_generated_date, status); grava audit_log; commit. |
| **Pré-condições** | --company-id informado; modelos recorrentes ativos com next_run_date vencido. |

## Exclusão de modelos

**Objetivo.** Remover modelos de lançamentos recorrentes.

### `delete-recurring-template`

Exclui um modelo de lançamento recorrente.

| | |
|---|---|
| **Entradas** | --template-id (obrigatório). |
| **Saídas** | status='deleted', deleted=true. |
| **Regras** | Template deve existir (senão erro 'not found'). Apesar do docstring mencionar soft delete, o código executa DELETE físico da linha. |
| **Efeitos colaterais** | DELETE em recurring_journal_template; grava audit_log; commit. |
| **Pré-condições** | Template existente. |

## Status

**Objetivo.** Resumir contagens de lançamentos e de modelos recorrentes por status para uma empresa.

### `status`

Mostra a contagem de lançamentos por status e de modelos recorrentes por status para a empresa.

| | |
|---|---|
| **Entradas** | company resolvido por --company-id ou --company (obrigatório). |
| **Saídas** | total, draft, submitted, cancelled, amended e recurring_templates (active, paused, completed). |
| **Regras** | Filtro obrigatório por company_id (resolve_company_id); agrega journal_entry e recurring_journal_template por status via GROUP BY. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa identificável por id ou nome. |

