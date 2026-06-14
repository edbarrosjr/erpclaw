# Pagamentos — `erpclaw-payments`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-payments/db_query.py`. 9 funcionalidades · 17 ações.

## Cadastro

**Objetivo.** Criar e editar lançamentos de pagamento (payment_entry) em rascunho — recebimentos, pagamentos e transferências internas — com suas alocações a faturas.

**Ações:**
- `add-payment` — Cria um novo payment_entry em status 'draft', opcionalmente já com alocações.
- `update-payment` — Edita valor pago, número de referência e/ou alocações de um pagamento ainda em rascunho.

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --company-id, --payment-type (receive\|pay\|internal_transfer), --posting-date, --party-type, --party-id, --paid-from-account, --paid-to-account, --paid-amount, --payment-currency (USD), --exchange-rate (1), --reference-number, --reference-date, --allocations (JSON). update: --payment-entry-id e os campos a alterar (--paid-amount, --reference-number, --allocations). |
| **Saídas** | add: {status:'created', payment_entry_id, naming_series}. update: {status:'updated', payment_entry_id, updated_fields}. |
| **Regras de negócio** | payment_type deve ser receive/pay/internal_transfer; party_type/party_id obrigatórios exceto em internal_transfer e o party_type deve estar registrado em party_type_registry. paid_amount > 0. received_amount = paid_amount * exchange_rate. Contas paid_from/paid_to validadas como não-grupo (grupo é auto-resolvido para único filho-folha ou gera erro). unallocated_amount inicia igual ao paid_amount e é recalculado quando há alocações. update só permitido em status 'draft'; em update --allocations substitui todas as alocações (delete + reinsert). |
| **Efeitos colaterais** | Insere/atualiza linha em payment_entry e linhas em payment_allocation (recalculando unallocated_amount). Grava auditoria (audit) para add-payment e update-payment. NÃO posta GL nem PLE nesta fase (apenas no submit). Faz conn.commit(). |
| **Pré-condições** | Empresa (company) existente; contas (account) paid_from e paid_to existentes e não-grupo; party_type registrado em party_type_registry; tabelas company e account presentes (REQUIRED_TABLES). |

## Listagem

**Objetivo.** Consultar pagamentos individualmente ou em lista filtrada/paginada, e localizar pagamentos com saldo não alocado por parte.

**Ações:**
- `get-payment` — Retorna um payment_entry completo com suas alocações.
- `list-payments` — Lista paginada de pagamentos da empresa com filtros e nome da parte resolvido.
- `get-unallocated-payments` — Lista pagamentos submitted de uma parte que ainda têm saldo não alocado (>0).
- `list-open-advances` — Alias (vocabulário SAP-B1) de get-unallocated-payments; lista adiantamentos em aberto.

| Campo | Detalhe |
|---|---|
| **Entradas** | get: --payment-entry-id. list: --company-id/--company (nome), filtros --payment-type, --party-type, --party-id, --status, --from-date, --to-date, --limit (20), --offset (0). get-unallocated/list-open-advances: --party-type, --party-id, --company-id/--company. |
| **Saídas** | get: objeto do pagamento + array allocations (id, voucher_type, voucher_id, allocated_amount, exchange_gain_loss). list: {payments[], total_count, limit, offset, has_more}, cada item com party_name resolvido. get-unallocated: {payments[]} com id, naming_series, paid_amount, unallocated_amount, posting_date. |
| **Regras de negócio** | list ordena por posting_date desc e created_at desc; resolve party_name por subconsulta CASE em customer/supplier/employee. get-unallocated filtra status='submitted' e unallocated_amount (CAST NUMERIC) > 0, ordenado por posting_date. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Empresa resolvível (por id ou nome); tabela payment_entry presente. |

## Ciclo de Vida

**Objetivo.** Conduzir o pagamento pelo fluxo rascunho → submetido → cancelado, postando e revertendo a contabilidade, além de excluir rascunhos.

**Ações:**
- `submit-payment` — Submete um draft: posta GL, cria PLE, aplica desconto por pagamento antecipado e limpa faturas alocadas.
- `cancel-payment` — Cancela um pagamento submitted: reverte GL, reverte PLE e desfaz a baixa das faturas.
- `delete-payment` — Exclui fisicamente um pagamento ainda em rascunho (com suas alocações e deduções).

| Campo | Detalhe |
|---|---|
| **Entradas** | Todas usam --payment-entry-id. |
| **Saídas** | submit: {status:'submitted', payment_entry_id, gl_entries_created, documents_cleared, outstanding_updated} (+ early_payment_discount e/ou exchange_gain_loss quando aplicável). cancel: {status:'cancelled', payment_entry_id, reversed:true}. delete: {status:'deleted', deleted:true}. |
| **Regras de negócio** | submit exige status 'draft'; revalida contas não-grupo (auto-resolve folha). Monta GL conforme tipo: receive DR paid_to(banco)/CR paid_from(receber); pay DR paid_to(pagar)/CR paid_from(banco); internal_transfer DR/CR banco↔banco. Calcula desconto antecipado se a fatura tem payment_terms com discount_percentage/discount_days e o pagamento ocorre dentro da janela (reduz valor no banco, conta de desconto absorve). Guarda contra falso sucesso: se há alocações de fatura mas nenhuma é baixada, faz rollback e erro. Branch de FX (gain/loss) está dormente (regra: moeda da fatura = moeda do pagamento, rate=1). cancel exige status 'submitted'. delete só em 'draft'. |
| **Efeitos colaterais** | submit: valida e insere gl_entry (insert_gl_entries via validate_gl_entries 12 passos), insere payment_ledger_entry de nível-parte (-paid_amount) e PLE por alocação (INV-22), aplica baixa em sales_invoice/purchase_invoice (apply_payment_to_document: outstanding/status), pode rotear porção de adiantamento a sub-conta (advance_account_id), muda status para 'submitted', auditoria. cancel: reverse_gl_entries, marca PLE como delinked e cria PLE de reversão, reverse_payment_on_document restaura outstanding/status das faturas, status 'cancelled', auditoria. delete: DELETE em payment_allocation, payment_deduction e payment_entry, auditoria. Todas fazem commit (rollback em falha). |
| **Pré-condições** | Pagamento existente no status correto; contas válidas; para submit com alocações, faturas com moeda igual à do pagamento; conta de desconto ('Sales/Purchase Discounts') e cost center default existentes para aplicar desconto; sub-conta de adiantamento configurada na company para rotear advance. |

## Alocação a Faturas

**Objetivo.** Vincular o saldo não alocado de um pagamento já submetido a uma fatura específica, baixando o documento e registrando a baixa no razão de pagamentos.

**Ações:**
- `allocate-payment` — Aloca um valor de um pagamento submitted a um voucher (sales_invoice/purchase_invoice), limpando o documento.

| Campo | Detalhe |
|---|---|
| **Entradas** | --payment-entry-id, --voucher-type (canonizado, ex.: 'Sales Invoice' → sales_invoice), --voucher-id, --allocated-amount. |
| **Saídas** | {status:'created', allocation_id, document_cleared (bool), remaining_unallocated}. |
| **Regras de negócio** | Pagamento deve estar 'submitted'. allocated_amount > 0 e não pode exceder o unallocated_amount atual. Recalcula unallocated após inserir alocação. Para voucher de tipo fatura, deve efetivamente baixar o documento — caso contrário rollback e erro (guarda contra falso sucesso). Se o adiantamento foi roteado a sub-conta no submit (advance_account_id), aplica reclassificação GL: receive DR Advance-from-Customer/CR AR; pay DR AP/CR Advance-to-Supplier (entry_set próprio, GL imutável). |
| **Efeitos colaterais** | Insere linha em payment_allocation, recalcula unallocated_amount, baixa a fatura (apply_payment_to_document: outstanding/status) e posta PLE por alocação (INV-22). Quando há advance_account_id, valida e insere gl_entry de reclassificação. Auditoria. commit (rollback em falha). |
| **Pré-condições** | Pagamento existente e 'submitted' com saldo não alocado suficiente; fatura-alvo existente e em estado que aceite baixa; para reclassificação, advance_account_id previamente gravado no submit. |

## Adiantamentos

**Objetivo.** Tratar a porção não alocada de um pagamento como adiantamento (advance) — listando os em aberto e aplicando-os a faturas com reclassificação contábil da sub-conta de adiantamento para a conta de controle AR/AP.

**Ações:**
- `list-open-advances` — Alias de get-unallocated-payments: lista adiantamentos (pagamentos com saldo) em aberto da parte.
- `apply-advance-to-invoice` — Alias de allocate-payment: aplica um adiantamento a uma fatura, reclassificando a sub-conta de adiantamento para AR/AP.

| Campo | Detalhe |
|---|---|
| **Entradas** | list-open-advances: --party-type, --party-id, --company-id/--company. apply-advance-to-invoice: --payment-entry-id, --voucher-type, --voucher-id, --allocated-amount. |
| **Saídas** | list-open-advances: {payments[]} (mesma de get-unallocated-payments). apply-advance-to-invoice: {status:'created', allocation_id, document_cleared, remaining_unallocated} (mesma de allocate-payment). |
| **Regras de negócio** | São aliases de vocabulário SAP-B1 com a MESMA semântica das ações originais. O roteamento de adiantamento só ocorre se a company tem advance_from_customer_account_id (receive) ou advance_to_supplier_account_id (pay) configurada; no submit a porção unallocated > 0 é movida para a sub-conta e advance_account_id é gravado. Na aplicação, reclassifica esse valor de volta para a conta de controle AR/AP. |
| **Efeitos colaterais** | list-open-advances: nenhum (somente leitura). apply-advance-to-invoice: idêntico a allocate-payment — payment_allocation, recálculo de unallocated, baixa da fatura (apply_payment_to_document), PLE por alocação, gl_entry de reclassificação quando há advance_account_id, auditoria e commit. |
| **Pré-condições** | Pagamento submetido com saldo (adiantamento) e, para roteamento/reclassificação, sub-contas de adiantamento configuradas na company; fatura-alvo existente. |

## Razão de Pagamentos (PLE)

**Objetivo.** Manter o payment_ledger_entry — subrazão que rastreia o outstanding por parte e por voucher — e consultar saldos em aberto. Usado em integração cross-skill por selling/buying na submissão de faturas.

**Ações:**
- `create-payment-ledger-entry` — Cria uma linha de PLE; chamada cross-skill por selling/buying no submit da fatura (+grand_total).
- `get-outstanding` — Agrega e retorna o saldo em aberto de uma parte a partir das linhas de PLE não delinkadas.

| Campo | Detalhe |
|---|---|
| **Entradas** | create-PLE: --voucher-type, --voucher-id, --party-type, --party-id, --amount, --posting-date, --account-id, --against-voucher-type, --against-voucher-id. get-outstanding: --party-type, --party-id, opcionais --voucher-type, --voucher-id. |
| **Saídas** | create-PLE: {status:'created', ple_id}. get-outstanding: {outstanding (total), vouchers[]} com voucher_type, voucher_id, outstanding_amount, posting_date. |
| **Regras de negócio** | party_type deve estar registrado em party_type_registry. voucher_type e against_voucher_type são canonizados na fronteira de escrita (label 'Sales Invoice' → sales_invoice) para o netting bater. amount arredondado a moeda; currency fixada em 'USD' na create. get-outstanding soma amount por (voucher_type, voucher_id) filtrando delinked=0, com HAVING sum != 0, ordenado por posting_date; aceita filtro por voucher (também canonizado). |
| **Efeitos colaterais** | create-payment-ledger-entry: insere linha em payment_ledger_entry, auditoria e commit. get-outstanding: nenhum (somente leitura). |
| **Pré-condições** | party_type registrado; conta (account-id) existente; para get-outstanding, existir PLE da parte. Tabela payment_ledger_entry presente. |

## Conciliação

**Objetivo.** Conciliar automaticamente pagamentos não alocados de uma parte contra suas faturas em aberto usando algoritmo FIFO.

**Ações:**
- `reconcile-payments` — Casa em FIFO pagamentos com saldo contra faturas em aberto (PLE), criando alocações e baixando documentos.

| Campo | Detalhe |
|---|---|
| **Entradas** | --party-type, --party-id, --company-id. |
| **Saídas** | {matched[] (payment_id, voucher_id, allocated_amount), unmatched_payments, unmatched_invoices}. |
| **Regras de negócio** | Busca pagamentos status='submitted' com unallocated>0 (FIFO por posting_date, created_at) e faturas em aberto via PLE (sum>0, somente sales_invoice/purchase_invoice, FIFO por MIN(posting_date)). Casa o menor entre saldo do pagamento e saldo da fatura, avançando índices. Como só casa faturas, toda alocação DEVE baixar um documento; um cleared=False faz rollback e erro (proteção contra drift de voucher_type). Recalcula unallocated de todos os pagamentos afetados ao final. |
| **Efeitos colaterais** | Insere linhas em payment_allocation, baixa cada fatura casada (apply_payment_to_document: outstanding/status) e posta PLE por alocação (INV-22), recalcula unallocated_amount dos pagamentos. commit (rollback em falha). Não grava auditoria explícita. |
| **Pré-condições** | Existirem pagamentos submetidos com saldo e faturas em aberto da mesma parte/empresa; PLE das faturas previamente criado (no submit das faturas). |

## Conciliação Bancária

**Objetivo.** Comparar, em modo leitura, o saldo contábil (GL) de uma conta bancária com a movimentação de pagamentos em um período, sem alterar dados.

**Ações:**
- `bank-reconciliation` — Calcula saldo GL da conta bancária no período e conta pagamentos que a tocam (paid_from/paid_to).

| Campo | Detalhe |
|---|---|
| **Entradas** | --bank-account-id, --from-date, --to-date. |
| **Saídas** | {bank_account (nome), from_date, to_date, gl_entries (contagem), gl_balance (débito - crédito), payment_entries (contagem)}. |
| **Regras de negócio** | Conta bancária deve existir. gl_balance = soma(débito) - soma(crédito) sobre gl_entry da conta no período com is_cancelled=0. payment_entries conta payment_entry status='submitted' no período onde paid_from_account OU paid_to_account é a conta. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Conta (account) bancária existente; intervalo de datas informado; tabela gl_entry e payment_entry presentes. |

## Status

**Objetivo.** Apresentar um resumo de contagens de pagamentos por status e totais recebidos/pagos da empresa.

**Ações:**
- `status` — Conta pagamentos por status e soma paid_amount dos submitted por tipo (received/paid).

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id ou --company (nome). |
| **Saídas** | {total, draft, submitted, cancelled, total_received, total_paid}. |
| **Regras de negócio** | Agrupa payment_entry por status para contagens. Soma paid_amount apenas dos status='submitted' agrupado por payment_type: 'receive' → total_received, 'pay' → total_paid. Valores monetários arredondados. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Empresa resolvível (id ou nome); tabela payment_entry presente. |

