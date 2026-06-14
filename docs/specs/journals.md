# Lançamentos Contábeis — `erpclaw-journals`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-journals/db_query.py`. 10 funcionalidades · 17 ações.

## Criação/edição

**Objetivo.** Criar e editar lançamentos contábeis manuais em rascunho, com linhas de débito/crédito balanceadas, antes de sua submissão ao razão (GL).

**Ações:**
- `add-journal-entry` — Cria um novo lançamento contábil em status 'draft' com suas linhas.
- `update-journal-entry` — Atualiza data, tipo, observação e/ou substitui as linhas de um lançamento ainda em rascunho.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --company-id, --posting-date, --entry-type (default 'journal'), --lines (JSON array com account_id, debit, credit, party_type/party_id, cost_center_id, project_id, remark), --remark, --cwip-asset-id (opcional). update: --journal-entry-id e os campos a alterar (--posting-date, --entry-type, --remark, --lines). |
| **Saídas** | add: status 'created', journal_entry_id e naming_series. update: status 'updated', journal_entry_id e lista de updated_fields alterados. |
| **Regras de negócio** | Mínimo de 2 linhas; cada linha exige account_id e exatamente um lado (débito OU crédito) > 0, ambos >= 0; total de débitos deve igualar total de créditos (round_currency). entry-type deve estar em VALID_ENTRY_TYPES (journal, opening, closing, depreciation, write_off, exchange_rate_revaluation, inter_company, credit_note, debit_note). update só é permitido enquanto status='draft' (caso contrário erro pedindo cancelar antes); ao trocar linhas, recalcula total_debit/total_credit. Se --cwip-asset-id for informado, valida que o ativo está 'under_construction'. |
| **Efeitos colaterais** | Persiste em journal_entry (status 'draft') e journal_entry_line; update pode apagar e reinserir todas as linhas. Registra auditoria (add-journal-entry/update-journal-entry). NÃO posta no GL nesta etapa (somente rascunho). |
| **Pré-condições** | Empresa (company) deve existir; todas as contas (account) das linhas devem existir. Tabelas obrigatórias: company e account. Para CWIP, ativo em construção pré-existente. |

## Consulta/listagem

**Objetivo.** Recuperar um lançamento individual com suas linhas ou listar/filtrar lançamentos de uma empresa com paginação.

**Ações:**
- `get-journal-entry` — Retorna um lançamento e todas as suas linhas (com nome da conta).
- `list-journal-entries` — Lista lançamentos de uma empresa com filtros e paginação.

| Campo | Detalhe |
|---|---|
| **Entradas** | get: --journal-entry-id. list: --company-id ou --company (nome); filtros opcionais --status, --entry-type, --from-date, --to-date, --account-id; paginação --limit (default 20) e --offset (default 0). |
| **Saídas** | get: cabeçalho (id, naming_series, posting_date, entry_type, status, total_debit, total_credit, remark, amended_from, company_id) e array de lines. list: entries[], total_count, limit, offset e has_more. |
| **Regras de negócio** | get falha se o lançamento não existir. list resolve a empresa por id ou nome (resolve_company_id) e sempre filtra por company_id; --account-id filtra via subconsulta nas linhas; ordena por posting_date desc e created_at desc. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Empresa existente (para list); lançamento existente (para get). Tabelas company e account presentes. |

## Ciclo de vida

**Objetivo.** Conduzir o lançamento pelo fluxo rascunho -> submetido -> cancelado, efetivando ou revertendo as postagens no razão (GL).

**Ações:**
- `submit-journal-entry` — Submete um rascunho: revalida, posta as entradas no GL e muda status para 'submitted'.
- `cancel-journal-entry` — Cancela um submetido: reverte as entradas do GL e muda status para 'cancelled'.

| Campo | Detalhe |
|---|---|
| **Entradas** | Ambas: --journal-entry-id. |
| **Saídas** | submit: status 'submitted', journal_entry_id, gl_entries_created (e, se CWIP, cwip_asset_id/cwip_accumulation_id). cancel: status 'cancelled', journal_entry_id, reversed=true. |
| **Regras de negócio** | submit exige status='draft'; revalida balanceamento das linhas e chama validate_gl_entries (que rejeita conta congelada, ano fiscal fechado e período congelado). cancel exige status='submitted'. Lançamentos 'opening' são tratados como is_opening na validação/postagem GL. |
| **Efeitos colaterais** | submit: INSERE linhas em gl_entry (voucher_type='journal_entry'), atualiza status para 'submitted'; se CWIP, grava acumulação contra a perna de débito CWIP e ajusta valor do ativo. cancel: insere entradas de reversão em gl_entry e, se CWIP, desfaz a acumulação e o valor contábil do ativo; muda status para 'cancelled'. Ambos registram auditoria. Não há SLE de estoque nem payment_ledger_entry. |
| **Pré-condições** | Lançamento existente no status correto; contas não congeladas; ano fiscal aberto e período não congelado para a data de postagem; tabela fiscal_year disponível para a validação de GL. |

## Retificação

**Objetivo.** Corrigir um lançamento já submetido criando uma versão emendada vinculada, sem editar o documento original.

**Ações:**
- `amend-journal-entry` — Cancela (reverte GL) o lançamento submetido e cria um novo rascunho ligado via amended_from.

| Campo | Detalhe |
|---|---|
| **Entradas** | --journal-entry-id; opcionalmente --lines (novas linhas; senão copia as do original), --posting-date (senão herda) e --remark. |
| **Saídas** | status 'created', original_id, new_journal_entry_id e new_naming_series. |
| **Regras de negócio** | Exige status='submitted'. Reverte o GL do original e marca o original como 'amended'. As novas linhas são validadas pelas mesmas regras de balanceamento; o novo lançamento nasce em 'draft' (precisa ser submetido depois) e referencia o original em amended_from. Herda entry_type e company do original. |
| **Efeitos colaterais** | Insere entradas de reversão no gl_entry do original; muda status do original para 'amended'; cria novo registro em journal_entry (draft) e suas journal_entry_line. Registra auditoria (amend-journal-entry). O novo lançamento ainda NÃO posta no GL (somente ao ser submetido). |
| **Pré-condições** | Lançamento existente e submetido; ano fiscal/período aberto para reverter na data de postagem do original. |

## Exclusão/duplicação

**Objetivo.** Excluir definitivamente rascunhos ou duplicar um lançamento existente como novo rascunho reaproveitando suas linhas.

**Ações:**
- `delete-journal-entry` — Exclui fisicamente um lançamento em rascunho (linhas e cabeçalho).
- `duplicate-journal-entry` — Cria um novo rascunho copiando todas as linhas de um lançamento existente.

| Campo | Detalhe |
|---|---|
| **Entradas** | delete: --journal-entry-id. duplicate: --journal-entry-id e --posting-date opcional (senão usa data atual UTC). |
| **Saídas** | delete: status 'deleted', deleted=true. duplicate: status 'created', new_journal_entry_id e naming_series. |
| **Regras de negócio** | delete só permite status='draft' (sugere cancelar antes se submetido). duplicate copia linhas (conta, débito, crédito, party, centro de custo, projeto, observação), revalida o balanceamento e cria sempre em 'draft' com novo naming_series; herda entry_type, remark e company do original. |
| **Efeitos colaterais** | delete: APAGA fisicamente journal_entry e journal_entry_line do lançamento; registra auditoria com o naming_series antigo. duplicate: insere novo journal_entry (draft) e linhas; registra auditoria. Nenhum afeta o GL. |
| **Pré-condições** | Lançamento existente; para delete, deve estar em rascunho; contas das linhas devem existir. |

## Intercompany

**Objetivo.** Registrar uma transação entre duas empresas criando um par de lançamentos espelhados (recebível na origem, pagável no destino).

**Ações:**
- `create-intercompany-je` — Cria lançamentos pareados entre empresa origem e destino, com contas intercompany e referência cruzada.

| Campo | Detalhe |
|---|---|
| **Entradas** | --source-company-id, --target-company-id, --amount, --posting-date e --description opcional. |
| **Saídas** | source_je_id/source_naming, target_je_id/target_naming, amount e description. |
| **Regras de negócio** | Origem e destino devem ser diferentes; amount > 0; ambas as empresas devem existir e ter a MESMA moeda padrão (multimoeda não suportado na v2). Origem: DR Intercompany Receivable / CR conta de receita; Destino: DR conta de despesa (ou CMV) / CR Intercompany Payable. Cria automaticamente as contas 'Intercompany Receivable' (asset/receivable) e 'Intercompany Payable' (liability/payable) se não existirem; usa o primeiro centro de custo não-grupo de cada empresa para as linhas de P&L. entry_type fixo 'inter_company'. |
| **Efeitos colaterais** | Insere DOIS journal_entry (ambos em 'draft', tipo inter_company) e suas linhas; pode CRIAR contas intercompany (account); grava referência cruzada no campo remark de cada lado. Registra auditoria. NÃO posta no GL (ambos nascem em rascunho, exigindo submit individual). |
| **Pré-condições** | Duas empresas distintas existentes com mesma moeda; origem com conta de receita (não-grupo) e destino com conta de despesa/CMV (não-grupo). |

## Modelos recorrentes

**Objetivo.** Definir e manter modelos de lançamento que se repetem em uma periodicidade, servindo de base para geração automática.

**Ações:**
- `add-recurring-template` — Cria um modelo recorrente ativo com frequência, datas, linhas e flag de auto-submit.
- `update-recurring-template` — Altera campos de um modelo (nome, frequência, datas, tipo, linhas, auto-submit, status active/paused).
- `delete-recurring-template` — Exclui fisicamente um modelo recorrente.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --company-id, --template-name, --frequency (default monthly), --start-date, --end-date opcional, --entry-type, --lines (JSON), --auto-submit, --remark. update: --template-id + campos a alterar (inclui --template-status active\|paused). delete: --template-id. |
| **Saídas** | add: status 'created', template_id, naming_series e next_run_date (= start_date). update: status 'updated', template_id e updated_fields. delete: status 'deleted', deleted=true. |
| **Regras de negócio** | frequency deve estar em (daily, weekly, monthly, quarterly, annual); entry_type em VALID_ENTRY_TYPES; linhas validadas pelo mesmo balanceamento de débito/crédito. next_run_date inicia em start_date. update bloqueia modelos 'completed' e só aceita status 'active' ou 'paused'. Apesar do docstring mencionar soft delete, delete remove o registro fisicamente. |
| **Efeitos colaterais** | Persiste/atualiza/remove recurring_journal_template (linhas guardadas como JSON). Registra auditoria. Nenhum efeito direto no GL ou em journal_entry (apenas o modelo). |
| **Pré-condições** | Empresa existente (add); contas das linhas existentes; modelo existente e não 'completed' (update); modelo existente (delete). |

## Consulta de modelos

**Objetivo.** Consultar um modelo recorrente em detalhe ou listar os modelos de uma empresa.

**Ações:**
- `get-recurring-template` — Retorna um modelo recorrente completo, com as linhas em JSON decodificado.
- `list-recurring-templates` — Lista modelos recorrentes de uma empresa, opcionalmente filtrando por status, com paginação.

| Campo | Detalhe |
|---|---|
| **Entradas** | get: --template-id. list: --company-id ou --company (nome), --template-status opcional, --limit (default 20), --offset (default 0). |
| **Saídas** | get: todos os campos do modelo (frequência, datas, next_run_date, last_generated_date, entry_type, auto_submit, status, lines). list: templates[], total_count, limit, offset, has_more. |
| **Regras de negócio** | get falha se o modelo não existir e tenta decodificar o JSON das linhas. list resolve empresa por id/nome e ordena por next_run_date ascendente. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Modelo existente (get); empresa existente (list). |

## Processamento de recorrências

**Objetivo.** Gerar automaticamente os lançamentos a partir dos modelos recorrentes vencidos de uma empresa em determinada data de corte.

**Ações:**
- `process-recurring` — Varre modelos ativos com next_run_date <= data de corte, gera os lançamentos e avança o próximo agendamento.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id e --as-of-date opcional (default data atual UTC). |
| **Saídas** | generated (quantidade) e results[] com template_id, template_name, journal_entry_id, naming_series, posting_date, je_status, next_run_date e template_status por modelo processado. |
| **Regras de negócio** | Processa apenas modelos status='active' com next_run_date <= as_of_date (idempotente em relação à data). Para cada um: cria o lançamento com posting_date = next_run_date, calcula totais; se auto_submit=1, valida e posta no GL e marca 'submitted' (falha de auto-submit deixa o lançamento como 'draft', sem abortar o lote). Avança next_run_date conforme a frequência (com clamp de fim de mês); se ultrapassar end_date, marca o modelo como 'completed' e zera o próximo agendamento. |
| **Efeitos colaterais** | Insere journal_entry (draft ou submitted) e journal_entry_line para cada modelo vencido; quando auto_submit, INSERE entradas no gl_entry. Atualiza next_run_date, last_generated_date e status do modelo (active/completed). Registra auditoria (process-recurring). Sem SLE de estoque ou payment_ledger. |
| **Pré-condições** | Empresa existente; modelos ativos com linhas válidas; para auto-submit, contas não congeladas e ano fiscal/período aberto na data de postagem. |

## Status

**Objetivo.** Apresentar um panorama agregado dos lançamentos e modelos recorrentes de uma empresa por status.

**Ações:**
- `status` — Conta lançamentos por status (draft/submitted/cancelled/amended) e modelos recorrentes por status.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id ou --company (nome). |
| **Saídas** | total e contagens por status (draft, submitted, cancelled, amended) dos lançamentos, mais recurring_templates com contagens (active, paused, completed). |
| **Regras de negócio** | Resolve a empresa por id ou nome; agrupa journal_entry e recurring_journal_template por status filtrando por company_id. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Empresa existente; tabelas journal_entry e recurring_journal_template presentes. |

