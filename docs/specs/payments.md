# Pagamentos — `erpclaw-payments`

> Spec funcional por ação. Gerada de `scripts/erpclaw-payments/db_query.py`. 9 funcionalidades · 16 ações.

## Cadastro

**Objetivo.** Criar e editar lançamentos de pagamento (payment_entry) em rascunho, incluindo suas alocações iniciais.

### `add-payment`

Cria um novo lançamento de pagamento em status draft (receive, pay ou internal_transfer).

| | |
|---|---|
| **Entradas** | --company-id (obrigatório), --payment-type (obrigatório: receive\|pay\|internal_transfer), --posting-date (obrigatório), --party-type (obrigatório salvo internal_transfer; deve estar registrado em party_type_registry), --party-id (obrigatório salvo internal_transfer), --paid-from-account (obrigatório), --paid-to-account (obrigatório), --paid-amount (obrigatório, >0), --payment-currency (default USD), --exchange-rate (default 1), --reference-number, --reference-date, --allocations (JSON opcional). |
| **Saídas** | status='created', payment_entry_id, naming_series. |
| **Regras** | Valida company existente; valida que ambas as contas existem e não são group (auto-resolve para filha-folha única, senão erro); paid_amount convertido com round_currency e deve ser >0; received_amount = paid_amount*exchange_rate; --allocations malformado gera erro JSON. Cria sempre em status 'draft' com unallocated_amount = paid_amount (recalculado se houver alocações). |
| **Efeitos colaterais** | Escreve em payment_entry (1 linha, status draft); insere linhas em payment_allocation se --allocations; recalcula unallocated_amount; grava audit_log (add-payment). Nenhuma postagem em gl_entry/PLE. conn.commit(). |
| **Pré-condições** | Company, contas paid-from/paid-to e (se aplicável) party_type registrado e party devem existir. |

### `update-payment`

Atualiza campos editáveis (valor, número de referência, alocações) de um pagamento ainda em draft.

| | |
|---|---|
| **Entradas** | --payment-entry-id (obrigatório); opcionais --paid-amount (>0), --reference-number, --allocations (JSON). |
| **Saídas** | status='updated', payment_entry_id, updated_fields (lista dos campos alterados). |
| **Regras** | Erro se pagamento não está em 'draft' (sugere cancelar primeiro). Se --paid-amount: recalcula received_amount = amount*exchange_rate existente. --allocations substitui (DELETE + reinsert) e recalcula unallocated. Erro 'No fields to update' se nada informado; JSON de alocações inválido gera erro. |
| **Efeitos colaterais** | UPDATE em payment_entry (paid_amount/received_amount/reference_number); DELETE+INSERT em payment_allocation; recalcula unallocated_amount; grava audit_log (update-payment) com old/new values. conn.commit(). Nenhuma postagem em gl_entry/PLE. |
| **Pré-condições** | Payment entry existente em status 'draft'. |

## Listagem

**Objetivo.** Consultas de leitura de pagamentos: detalhe individual e listagem filtrada/paginada.

### `get-payment`

Retorna um lançamento de pagamento completo com suas alocações.

| | |
|---|---|
| **Entradas** | --payment-entry-id (obrigatório). |
| **Saídas** | id, naming_series, payment_type, posting_date, party_type, party_id, paid_from_account, paid_to_account, paid_amount, received_amount, payment_currency, exchange_rate, reference_number, reference_date, status, unallocated_amount, company_id, allocations[] (id, voucher_type, voucher_id, allocated_amount, exchange_gain_loss). |
| **Regras** | Erro se payment_entry não encontrado (sugere 'list payments'). Alocações ordenadas por created_at depois id. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Payment entry existente. |

### `list-payments`

Lista lançamentos de pagamento de uma empresa com filtros e paginação.

| | |
|---|---|
| **Entradas** | --company-id ou --company (nome) para resolver empresa; filtros opcionais --payment-type, --party-type, --party-id, --status (pe_status), --from-date, --to-date; --limit (default 20), --offset (default 0). |
| **Saídas** | payments[] (id, naming_series, payment_type, posting_date, party_type, party_id, paid_amount, status, unallocated_amount, party_name resolvido), total_count, limit, offset, has_more. |
| **Regras** | company_id resolvido via resolve_company_id (id ou nome). party_name obtido por subconsulta CASE em customer/supplier/employee. Ordena por posting_date desc, created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa identificável por id ou nome. |

## Ciclo de Vida

**Objetivo.** Transições draft→submit→cancel e exclusão de rascunhos, com postagens e reversões contábeis.

### `submit-payment`

Submete um pagamento draft: posta GL, cria PLE, aplica desconto por pagamento antecipado e liquida faturas alocadas.

| | |
|---|---|
| **Entradas** | --payment-entry-id (obrigatório). |
| **Saídas** | status='submitted', payment_entry_id, gl_entries_created, documents_cleared, outstanding_updated (bool); opcional early_payment_discount{discount_amount,bank_amount,details}; opcional exchange_gain_loss. |
| **Regras** | Erro se status != 'draft'. Re-valida contas não-group (auto-resolve+update). Exige currency da fatura == payment_currency (senão erro de mismatch). Calcula desconto antecipado via payment_terms (discount_percentage/discount_days) dentro da janela. Monta GL: receive DR paid_to/CR paid_from; pay DR paid_to/CR paid_from; internal_transfer banco-a-banco; com desconto adiciona leg na conta de desconto. Roteia porção de adiantamento (unallocated) para sub-conta de advance se configurada. Branch FX dormente (rate==1 garantido). Falha de GL ou de clearing faz rollback e erro; se nomeou alocações de fatura mas nenhuma liquidou, rollback e erro. |
| **Efeitos colaterais** | INSERT em gl_entry (via insert_gl_entries, voucher_type=payment_entry); INSERT em payment_ledger_entry (PLE party-level -paid_amount) e PLE por-alocação (-allocated, INV-22); UPDATE payment_entry.status='submitted' e advance_account_id se roteado; UPDATE em sales_invoice/purchase_invoice (outstanding/status via apply_payment_to_document); possível UPDATE payment_allocation.exchange_gain_loss; audit_log (submit-payment). conn.commit(). |
| **Pré-condições** | Payment entry em 'draft'; contas válidas; moeda da fatura igual à do pagamento. |

### `cancel-payment`

Cancela um pagamento submetido: reverte GL, desfaz liquidação das faturas e reverte PLE.

| | |
|---|---|
| **Entradas** | --payment-entry-id (obrigatório). |
| **Saídas** | status='cancelled', payment_entry_id, reversed=true. |
| **Regras** | Erro se status != 'submitted'. Reverte GL via reverse_gl_entries (erro de reversão aborta). Para cada alocação de fatura, restaura outstanding/status via reverse_payment_on_document (lê grand_total). Seleciona todas as PLE não-delinked do pagamento (party-level + por-alocação) e cria linhas estornantes. |
| **Efeitos colaterais** | INSERT de gl_entry de reversão; UPDATE payment_ledger_entry.delinked=1 nas linhas originais + INSERT de PLE estornantes (valor negado, preservando against_voucher); UPDATE em sales_invoice/purchase_invoice (outstanding/status); UPDATE payment_entry.status='cancelled'; audit_log (cancel-payment). conn.commit(). |
| **Pré-condições** | Payment entry em 'submitted'. |

### `delete-payment`

Exclui fisicamente um pagamento que ainda está em draft.

| | |
|---|---|
| **Entradas** | --payment-entry-id (obrigatório). |
| **Saídas** | status='deleted', deleted=true. |
| **Regras** | Erro se status != 'draft' (somente drafts; sugere cancelar primeiro). Remove dependências antes do registro principal. |
| **Efeitos colaterais** | DELETE em payment_allocation, payment_deduction e payment_entry do registro; audit_log (delete-payment) com old_values. conn.commit(). Nenhuma postagem em gl_entry/PLE. |
| **Pré-condições** | Payment entry existente em status 'draft'. |

## Alocação a Faturas

**Objetivo.** Alocar um pagamento submetido a uma fatura específica, liquidando o documento e gerando PLE de offset.

### `allocate-payment`

Aloca parte do valor não-alocado de um pagamento submetido a um voucher (fatura), liquidando-o.

| | |
|---|---|
| **Entradas** | --payment-entry-id (obrigatório), --voucher-type (obrigatório; canonicalizado), --voucher-id (obrigatório), --allocated-amount (obrigatório, >0). |
| **Saídas** | status='created', allocation_id, document_cleared (bool), remaining_unallocated. |
| **Regras** | Erro se pagamento != 'submitted'. amount deve ser >0 e <= unallocated_amount (senão erro de excesso). Insere alocação e recalcula unallocated. Se advance_account_id setado, posta GL de reclassificação (receive: DR advance/CR AR; pay: DR AP/CR advance). Liquida a fatura via _clear_invoice_allocation; voucher de tipo fatura que não liquida nada gera rollback+erro; tipos advance/on-account liquidam nada legitimamente. |
| **Efeitos colaterais** | INSERT em payment_allocation; UPDATE payment_entry.unallocated_amount; possível INSERT em gl_entry (reclassificação de adiantamento, entry_set=advance_alloc_*); INSERT PLE por-alocação (INV-22) e UPDATE em sales_invoice/purchase_invoice via apply_payment_to_document; audit_log (allocate-payment). conn.commit(). |
| **Pré-condições** | Payment entry em 'submitted' com unallocated suficiente; voucher/fatura existente. |

### `apply-advance-to-invoice`

Alias de vocabulário (SAP B1) para allocate-payment: aplica um adiantamento a uma fatura.

| | |
|---|---|
| **Entradas** | Idêntico a allocate-payment: --payment-entry-id, --voucher-type, --voucher-id, --allocated-amount (todos obrigatórios). |
| **Saídas** | Idêntico a allocate-payment: status='created', allocation_id, document_cleared, remaining_unallocated. |
| **Regras** | Mapeia exatamente para a função allocate_payment (mesmas validações e ciclo); apenas o nome no dispatch difere. |
| **Efeitos colaterais** | Idêntico a allocate-payment: payment_allocation, payment_entry, gl_entry (reclass de adiantamento), PLE por-alocação, sales_invoice/purchase_invoice, audit_log (allocate-payment). conn.commit(). |
| **Pré-condições** | Mesmas de allocate-payment: pagamento 'submitted' com unallocated e fatura existente. |

## Adiantamentos

**Objetivo.** Consultar pagamentos com saldo não-alocado (adiantamentos em aberto) por parceiro.

### `get-unallocated-payments`

Lista pagamentos submetidos de um parceiro que ainda têm valor não-alocado (>0).

| | |
|---|---|
| **Entradas** | --party-type (obrigatório), --party-id (obrigatório); --company-id ou --company para resolver empresa. |
| **Saídas** | payments[] (id, naming_series, paid_amount, unallocated_amount, posting_date). |
| **Regras** | Filtra status='submitted' e unallocated_amount numérico >0; ordena por posting_date. company_id resolvido por id/nome. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Parceiro e empresa identificáveis. |

### `list-open-advances`

Alias de vocabulário (SAP B1) para get-unallocated-payments: lista adiantamentos em aberto.

| | |
|---|---|
| **Entradas** | Idêntico a get-unallocated-payments: --party-type, --party-id (obrigatórios), --company-id/--company. |
| **Saídas** | Idêntico a get-unallocated-payments: payments[] (id, naming_series, paid_amount, unallocated_amount, posting_date). |
| **Regras** | Mapeia exatamente para get_unallocated_payments; apenas o nome no dispatch difere. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Mesmas de get-unallocated-payments. |

## Razão de Pagamentos (PLE)

**Objetivo.** Manter e consultar o subledger payment_ledger_entry e os saldos em aberto por parceiro/voucher.

### `create-payment-ledger-entry`

Cria uma linha de payment_ledger_entry, usada cross-skill por selling/buying na submissão de faturas.

| | |
|---|---|
| **Entradas** | --voucher-type (obrigatório; canonicalizado), --voucher-id (obrigatório), --party-type (obrigatório; registrado), --party-id (obrigatório), --amount (obrigatório), --posting-date (obrigatório), --account-id (obrigatório); opcionais --against-voucher-type (canonicalizado), --against-voucher-id. |
| **Saídas** | status='created', ple_id. |
| **Regras** | voucher_type e against_voucher_type canonicalizados para snake_case; party_type deve estar registrado; amount arredondado via round_currency; currency gravada como 'USD'. |
| **Efeitos colaterais** | INSERT em payment_ledger_entry (1 linha); audit_log (create-payment-ledger-entry). conn.commit(). Nenhuma postagem em gl_entry. |
| **Pré-condições** | Conta, party_type registrado e party válidos. |

### `get-outstanding`

Retorna saldos em aberto de um parceiro agregados por voucher a partir do PLE.

| | |
|---|---|
| **Entradas** | --party-type (obrigatório), --party-id (obrigatório); filtros opcionais --voucher-type (canonicalizado), --voucher-id. |
| **Saídas** | outstanding (total), vouchers[] (voucher_type, voucher_id, outstanding_amount, posting_date). |
| **Regras** | Considera apenas PLE delinked=0; soma amount agrupado por voucher; descarta saldos líquidos zero (HAVING != 0); ordena por posting_date. voucher_type filtrado é canonicalizado. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Parceiro existente; PLE registradas. |

## Conciliação

**Objetivo.** Conciliar automaticamente (FIFO) pagamentos não-alocados contra faturas em aberto de um parceiro.

### `reconcile-payments`

Concilia em FIFO os pagamentos submetidos não-alocados de um parceiro contra suas faturas em aberto.

| | |
|---|---|
| **Entradas** | --party-type (obrigatório), --party-id (obrigatório), --company-id (obrigatório). |
| **Saídas** | matched[] (payment_id, voucher_id, allocated_amount), unmatched_payments (contagem), unmatched_invoices (contagem). |
| **Regras** | Pagamentos: status='submitted' e unallocated>0, ordenados FIFO (posting_date, created_at). Faturas: PLE delinked=0 de sales_invoice/purchase_invoice com saldo>0, FIFO por MIN(posting_date). Casa o menor entre saldo do pagamento e da fatura; cada match deve liquidar documento (False gera rollback+erro). Liquidação inválida aborta com rollback. |
| **Efeitos colaterais** | INSERT em payment_allocation por match; INSERT PLE por-alocação (INV-22) e UPDATE sales_invoice/purchase_invoice via _clear_invoice_allocation; UPDATE payment_entry.unallocated_amount de todos pagamentos afetados. conn.commit(). Não grava audit_log próprio. |
| **Pré-condições** | Parceiro com pagamentos submetidos não-alocados e faturas em aberto na empresa. |

## Conciliação Bancária

**Objetivo.** Comparar, em modo leitura, o saldo contábil de uma conta bancária com os pagamentos do período.

### `bank-reconciliation`

Compara o saldo do razão (GL) de uma conta bancária com os pagamentos submetidos do período (somente leitura).

| | |
|---|---|
| **Entradas** | --bank-account-id (obrigatório), --from-date (obrigatório), --to-date (obrigatório). |
| **Saídas** | bank_account (nome), from_date, to_date, gl_entries (contagem), gl_balance (debit-credit), payment_entries (contagem). |
| **Regras** | Erro se conta bancária não encontrada. gl_balance = soma(debit)-soma(credit) de gl_entry não cancelado no período; conta pagamentos submetidos que tocam a conta como paid_from ou paid_to no período. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Conta bancária existente; gl_entry e payment_entry no período. |

## Status

**Objetivo.** Resumir contagens por status e totais recebidos/pagos dos pagamentos de uma empresa.

### `status`

Retorna contagens de pagamentos por status e totais recebidos/pagos (submetidos) da empresa.

| | |
|---|---|
| **Entradas** | --company-id ou --company (nome) para resolver empresa. |
| **Saídas** | total, draft, submitted, cancelled (contagens), total_received, total_paid. |
| **Regras** | Agrupa contagens e soma paid_amount por status; total_received/total_paid somam paid_amount apenas de pagamentos 'submitted' por payment_type (receive/pay). company_id resolvido por id/nome. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa identificável por id ou nome. |

