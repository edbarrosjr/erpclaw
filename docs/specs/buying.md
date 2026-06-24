# Compras — `glue-buying`

> Spec funcional por ação. Gerada de `scripts/glue-buying/db_query.py`. 13 funcionalidades · 48 ações.

## Fornecedores

**Objetivo.** Cadastro, atualizacao, consulta, listagem e importacao em massa de fornecedores, incluindo resumo de saldo devedor.

### `add-supplier`

Cria um registro de fornecedor com status 'active'.

| | |
|---|---|
| **Entradas** | --name (obrigatorio); --company-id (obrigatorio); --supplier-type (default 'company', deve ser 'company'\|'individual'); --supplier-group; --payment-terms-id; --tax-id; --is-1099-vendor (int, default 0); --primary-address (JSON); --email; --phone; --custom-fields (JSON). |
| **Saídas** | supplier_id, name e quaisquer custom fields mesclados na resposta. |
| **Regras** | Valida existencia de company_id; supplier_type restrito a company/individual; valida payment_terms_id se informado; primary_address e parseado como JSON; erro de IntegrityError vira 'Supplier creation failed'; erro em custom field faz rollback. |
| **Efeitos colaterais** | INSERT em supplier (status='active'); grava custom fields; audit_log via audit('add-supplier'); commit. |
| **Pré-condições** | Company existente; payment_terms existente se informado. |

### `update-supplier`

Atualiza campos de um fornecedor existente.

| | |
|---|---|
| **Entradas** | --supplier-id (obrigatorio, aceita id ou name); --name; --payment-terms-id; --supplier-group; --supplier-type (company\|individual); --email; --phone. |
| **Saídas** | supplier_id, updated_fields (lista de campos alterados). |
| **Regras** | Resolve supplier por id OU name e normaliza para id; erro se nao encontrado; erro 'No fields to update' se nenhum campo passado; supplier_type restrito a company/individual. |
| **Efeitos colaterais** | UPDATE em supplier (campos + updated_at via dynamic_update); audit_log via audit('update-supplier'); commit. |
| **Pré-condições** | Fornecedor existente. |

### `get-supplier`

Retorna o fornecedor com resumo de saldo devedor agregado das faturas de compra.

| | |
|---|---|
| **Entradas** | --supplier-id (obrigatorio, aceita id ou name). |
| **Saídas** | Todos os campos do supplier, total_outstanding, outstanding_invoice_count, custom fields mesclados. |
| **Regras** | Resolve por id OU name; erro se nao encontrado; soma outstanding_amount de purchase_invoice em status submitted/overdue/partially_paid. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Fornecedor existente. |

### `list-suppliers`

Lista fornecedores paginados com filtros opcionais.

| | |
|---|---|
| **Entradas** | --company-id; --supplier-group; --search (filtra name/tax_id por LIKE); --limit (default 20); --offset (default 0). |
| **Saídas** | suppliers (lista), total_count, limit, offset, has_more. |
| **Regras** | Ordena por name; paginacao via limit/offset; has_more = offset+limit < total_count. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | nenhuma. |

### `import-suppliers`

Importa fornecedores em massa de um arquivo CSV, pulando duplicados por nome+empresa.

| | |
|---|---|
| **Entradas** | --csv-path (obrigatorio, deve ser .csv regular file); --company-id (obrigatorio). CSV: name, supplier_type, country, default_currency, email, phone, tax_id. |
| **Saídas** | imported, skipped, total_rows. |
| **Regras** | Resolve symlinks e exige extensao .csv e arquivo regular; valida CSV via validate_csv; erro se CSV vazio; pula linhas cujo (name, company_id) ja existe; gera naming_series por linha importada. |
| **Efeitos colaterais** | INSERT em supplier para cada linha nova (com naming_series); commit. Nao gera audit_log. |
| **Pré-condições** | Arquivo CSV valido; company informada. |

## Requisicoes de Material

**Objetivo.** Criacao em rascunho, submissao e listagem de requisicoes de material (compra/transferencia/manufatura).

### `add-material-request`

Cria uma requisicao de material em rascunho com seus itens.

| | |
|---|---|
| **Entradas** | --request-type (obrigatorio: purchase\|transfer\|manufacture; 'transfer' mapeia para 'material_transfer'); --items (obrigatorio, JSON array com item_id e qty); --company-id (obrigatorio). Cada item: item_id, qty, warehouse_id. |
| **Saídas** | material_request_id, request_type, item_count. |
| **Regras** | Valida tipo de requisicao e company; itens devem ter item_id e qty>0; aceita tambem material_transfer/material_issue internamente. |
| **Efeitos colaterais** | INSERT em material_request (status='draft') e material_request_item; audit_log via audit('add-material-request'); commit. |
| **Pré-condições** | Company existente. |

### `submit-material-request`

Submete uma requisicao de material atribuindo naming_series.

| | |
|---|---|
| **Entradas** | --material-request-id (obrigatorio). |
| **Saídas** | material_request_id, naming_series, status='submitted'. |
| **Regras** | Erro se nao encontrada; so submete se status='draft'; gera naming_series via get_next_name por company. |
| **Efeitos colaterais** | UPDATE material_request (status='submitted', naming_series, updated_at); audit_log via audit('submit-material-request'); commit. |
| **Pré-condições** | Requisicao em rascunho. |

### `list-material-requests`

Lista requisicoes de material paginadas com filtros.

| | |
|---|---|
| **Entradas** | --company-id; --request-type ('transfer' mapeia para 'material_transfer'); --mr-status; --limit (default 20); --offset (default 0). |
| **Saídas** | material_requests (lista), total_count, limit, offset, has_more. |
| **Regras** | Ordena por created_at desc; paginacao limit/offset. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | nenhuma. |

## Cotacoes e RFQ

**Objetivo.** Criacao/submissao de RFQs, registro de cotacoes de fornecedores e comparacao de propostas por item.

### `add-rfq`

Cria uma Solicitacao de Cotacao (RFQ) em rascunho com itens e fornecedores convidados.

| | |
|---|---|
| **Entradas** | --items (obrigatorio, JSON array: item_id, qty, uom, required_date); --suppliers (obrigatorio, JSON array de supplier IDs); --company-id (obrigatorio). |
| **Saídas** | rfq_id, item_count, supplier_count. |
| **Regras** | Valida company; valida que cada supplier informado existe; itens precisam item_id e qty>0; rfq_date = hoje. |
| **Efeitos colaterais** | INSERT em request_for_quotation (status='draft'), rfq_item e rfq_supplier; audit_log via audit('add-rfq'); commit. |
| **Pré-condições** | Company e fornecedores existentes. |

### `submit-rfq`

Submete a RFQ, marcando data de envio aos fornecedores.

| | |
|---|---|
| **Entradas** | --rfq-id (obrigatorio). |
| **Saídas** | rfq_id, naming_series, status='submitted'. |
| **Regras** | Erro se nao encontrada; so submete de 'draft'; gera naming_series; preenche sent_date em todos rfq_supplier. |
| **Efeitos colaterais** | UPDATE request_for_quotation (status, naming_series, updated_at) e rfq_supplier (sent_date); audit_log via audit('submit-rfq'); commit. |
| **Pré-condições** | RFQ em rascunho. |

### `list-rfqs`

Lista RFQs paginadas com filtros.

| | |
|---|---|
| **Entradas** | --company-id; --rfq-status; --limit (default 20); --offset (default 0). |
| **Saídas** | rfqs (lista), total_count, limit, offset, has_more. |
| **Regras** | Ordena por created_at desc; paginacao limit/offset. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | nenhuma. |

### `add-supplier-quotation`

Registra a cotacao de um fornecedor respondendo a uma RFQ.

| | |
|---|---|
| **Entradas** | --rfq-id (obrigatorio); --supplier-id (obrigatorio, id ou name); --items (obrigatorio, JSON: rfq_item_id, rate, lead_time_days). |
| **Saídas** | supplier_quotation_id, total_amount. |
| **Regras** | Valida RFQ e fornecedor; cada item precisa rfq_item_id e rate>0; qty vem do rfq_item; amount=qty*rate; soma total_amount; marca response_date/supplier_quotation_id no rfq_supplier; se todos fornecedores responderam, RFQ vira 'quotation_received'. |
| **Efeitos colaterais** | INSERT em supplier_quotation (status='draft') e supplier_quotation_item; UPDATE supplier_quotation (totais), rfq_supplier (response), e possivelmente request_for_quotation (status); audit_log via audit('add-supplier-quotation'); commit. |
| **Pré-condições** | RFQ existente; fornecedor existente; rfq_items existentes. |

### `list-supplier-quotations`

Lista cotacoes de fornecedores paginadas com filtros.

| | |
|---|---|
| **Entradas** | --rfq-id; --supplier-id; --limit (default 20); --offset (default 0). |
| **Saídas** | supplier_quotations (lista com supplier_name), total_count, limit, offset, has_more. |
| **Regras** | Join com supplier; ordena por created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | nenhuma. |

### `compare-supplier-quotations`

Compara lado a lado as cotacoes dos fornecedores para os mesmos itens da RFQ, destacando o menor preco.

| | |
|---|---|
| **Entradas** | --rfq-id (obrigatorio). |
| **Saídas** | rfq_id, comparison (por item: quotes, lowest_rate, lowest_supplier, flag is_lowest), supplier_count. |
| **Regras** | Valida RFQ; para cada rfq_item compara rate de cada cotacao; calcula menor rate e marca is_lowest. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | RFQ existente com cotacoes registradas. |

## Pedidos de Compra

**Objetivo.** Ciclo completo do pedido de compra: criar, atualizar, consultar, listar, submeter, cancelar e fechar.

### `add-purchase-order`

Cria um pedido de compra em rascunho com itens, descontos e impostos calculados.

| | |
|---|---|
| **Entradas** | --supplier-id (obrigatorio, id ou name); --items (obrigatorio, JSON: item_id, qty, rate, uom, discount_percentage, warehouse_id, required_date); --company-id (obrigatorio); --tax-template-id; --posting-date (default hoje). |
| **Saídas** | purchase_order_id, total_amount, tax_amount, grand_total. |
| **Regras** | Fornecedor deve estar 'active'; valida company; cada item exige item_id, qty>0 e rate>0; net_amount aplica discount_percentage; tax via _calculate_tax; grand_total=total+tax. |
| **Efeitos colaterais** | INSERT em purchase_order (status='draft') e purchase_order_item; audit_log via audit('add-purchase-order'); commit. |
| **Pré-condições** | Fornecedor ativo; company existente. |

### `update-purchase-order`

Substitui os itens de um PO em rascunho e recalcula totais.

| | |
|---|---|
| **Entradas** | --purchase-order-id (obrigatorio); --items (obrigatorio, JSON array). |
| **Saídas** | purchase_order_id, total_amount, grand_total. |
| **Regras** | So atualiza se status='draft' (sugere cancelar antes); apaga e reinsere todos os itens; recalcula tax pelo tax_template do PO; valida item_id/qty/rate por item. |
| **Efeitos colaterais** | DELETE/INSERT purchase_order_item; UPDATE purchase_order (totais, updated_at); audit_log via audit('update-purchase-order'); commit. |
| **Pré-condições** | PO em rascunho. |

### `get-purchase-order`

Retorna o PO com itens e status de recebimentos e faturas vinculados.

| | |
|---|---|
| **Entradas** | --purchase-order-id (obrigatorio). |
| **Saídas** | Campos do PO + items, purchase_receipts (id, naming, status, posting_date), purchase_invoices (com grand_total e outstanding). |
| **Regras** | Erro se PO nao encontrado; itens ordenados por linha. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | PO existente. |

### `list-purchase-orders`

Lista pedidos de compra paginados com filtros.

| | |
|---|---|
| **Entradas** | --company-id; --supplier-id; --po-status; --from-date / --to-date (filtra order_date); --limit (default 20); --offset (default 0). |
| **Saídas** | purchase_orders (com supplier_name), total_count, limit, offset, has_more. |
| **Regras** | Join com supplier; ordena por order_date desc, created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | nenhuma. |

### `submit-purchase-order`

Confirma um PO em rascunho, atribuindo naming_series e avisando sobre quantidade minima.

| | |
|---|---|
| **Entradas** | --purchase-order-id (obrigatorio). |
| **Saídas** | purchase_order_id, naming_series, status='confirmed', warnings (opcional: itens abaixo do min_order_qty). |
| **Regras** | So submete de 'draft'; verifica item_supplier.min_order_qty e gera avisos (nao bloqueia); gera naming_series. |
| **Efeitos colaterais** | UPDATE purchase_order (status='confirmed', naming_series, updated_at); audit_log via audit('submit-purchase-order'); commit. |
| **Pré-condições** | PO em rascunho. |

### `cancel-purchase-order`

Cancela um PO desde que nao tenha recebimentos ou faturas vinculados.

| | |
|---|---|
| **Entradas** | --purchase-order-id (obrigatorio). |
| **Saídas** | purchase_order_id, status='cancelled'. |
| **Regras** | Erro se ja cancelado; bloqueia se existirem purchase_receipt nao-cancelados ou purchase_invoice nao-cancelados vinculados. |
| **Efeitos colaterais** | UPDATE purchase_order (status='cancelled', updated_at); audit_log via audit('cancel-purchase-order'); commit. |
| **Pré-condições** | PO sem documentos filhos ativos. |

### `close-purchase-order`

Fecha um PO parcialmente recebido, impedindo novos recebimentos/faturas mas preservando documentos filhos.

| | |
|---|---|
| **Entradas** | --purchase-order-id (obrigatorio); --reason; --closed-by. |
| **Saídas** | purchase_order_id, doc_status='closed', close_reason, closed_by. |
| **Regras** | Erro se status estiver em draft/cancelled/closed. |
| **Efeitos colaterais** | UPDATE purchase_order (status='closed', close_reason, closed_by, updated_at); audit_log via audit('close-purchase-order'); commit. |
| **Pré-condições** | PO confirmado/parcialmente recebido ou faturado. |

## Recebimentos (GRN)

**Objetivo.** Geracao de recebimentos a partir de PO, consulta/listagem e submissao/cancelamento com postagens de estoque e GL.

### `create-purchase-receipt`

Cria um recebimento de compra (GRN) em rascunho a partir de um PO (total ou parcial).

| | |
|---|---|
| **Entradas** | --purchase-order-id (obrigatorio); --posting-date (default hoje); --items (JSON opcional para recebimento parcial: purchase_order_item_id, qty, warehouse_id, batch_id, serial_numbers). |
| **Saídas** | purchase_receipt_id, total_qty, item_count. |
| **Regras** | PO deve estar 'confirmed' ou 'partially_received' (erro se 'closed'); parcial valida qty contra remaining (ordered-received) aplicando receipt_tolerance_pct da empresa; total copia todos itens nao-recebidos; erro se nada a receber. |
| **Efeitos colaterais** | INSERT em purchase_receipt (status='draft') e purchase_receipt_item; audit_log via audit('create-purchase-receipt'); commit. Nao posta estoque/GL ainda. |
| **Pré-condições** | PO confirmado/parcialmente recebido. |

### `get-purchase-receipt`

Retorna um recebimento de compra com seus itens.

| | |
|---|---|
| **Entradas** | --purchase-receipt-id (obrigatorio). |
| **Saídas** | Campos do purchase_receipt + items (com item_code/item_name). |
| **Regras** | Erro se nao encontrado; itens ordenados por linha. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Recebimento existente. |

### `list-purchase-receipts`

Lista recebimentos de compra paginados com filtros.

| | |
|---|---|
| **Entradas** | --company-id; --supplier-id; --pr-status; --limit (default 20); --offset (default 0). |
| **Saídas** | purchase_receipts (com supplier_name), total_count, limit, offset, has_more. |
| **Regras** | Join com supplier; ordena por posting_date desc, created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | nenhuma. |

### `submit-purchase-receipt`

Submete o GRN gerando lancamentos de estoque (SLE) e GL de inventario perpetuo, e atualiza o PO.

| | |
|---|---|
| **Entradas** | --purchase-receipt-id (obrigatorio). |
| **Saídas** | purchase_receipt_id, naming_series, status='submitted', sle_entries_created, gl_entries_created. |
| **Regras** | So submete de 'draft'; verifica que PO vinculado esteja confirmed/partially_received/partially_invoiced; warehouse cai para default da empresa se ausente (erro se nenhum); SLE com require_rate=True (rate da linha do PO); atualiza received_qty dos itens do PO e recalcula status (partially/fully_received). |
| **Efeitos colaterais** | INSERT stock_ledger_entry (insert_sle_entries) e gl_entry (DR Stock In Hand / CR Stock Received Not Billed via create_perpetual_inventory_gl); UPDATE purchase_order_item.received_qty e purchase_order.status/per_received; UPDATE purchase_receipt (status, naming); audit_log via audit('submit-purchase-receipt'); commit. |
| **Pré-condições** | GRN em rascunho com itens; warehouse ou default da empresa; fiscal_year e cost_center disponiveis. |

### `cancel-purchase-receipt`

Cancela um GRN submetido, revertendo SLE/GL e reduzindo received_qty no PO.

| | |
|---|---|
| **Entradas** | --purchase-receipt-id (obrigatorio). |
| **Saídas** | purchase_receipt_id, status='cancelled', sle_reversals, gl_reversals. |
| **Regras** | So cancela se status='submitted'; reverte SLE e GL (GL com tolerancia a falha); reverte received_qty (com floor 0); recalcula status do PO; se tudo zerado volta PO para 'confirmed'. |
| **Efeitos colaterais** | Reversao em stock_ledger_entry (reverse_sle_entries) e gl_entry (reverse_gl_entries); UPDATE purchase_order_item.received_qty e purchase_order.status; UPDATE purchase_receipt (status='cancelled'); audit_log via audit('cancel-purchase-receipt'); commit. |
| **Pré-condições** | GRN submetido. |

## Faturas de Compra

**Objetivo.** Ciclo da fatura de compra: criar (de PO/GRN/avulsa ou CWIP), atualizar, consultar, listar, submeter (GL/AP/imposto/PLE e SLE opcional), cancelar e baixar outstanding.

### `create-purchase-invoice`

Cria uma fatura de compra em rascunho a partir de PO, GRN, avulsa ou capitalizada em CWIP.

| | |
|---|---|
| **Entradas** | --purchase-order-id e/ou --purchase-receipt-id; OU avulsa (--supplier-id, --company-id, --items obrigatorios); --posting-date (default hoje); --due-date; --tax-template-id; --cwip-asset-id (apenas avulsa). Itens avulsos: item_id, qty, rate, uom, expense_account_id, cost_center_id, project_id. |
| **Saídas** | purchase_invoice_id, total_amount, tax_amount, grand_total, update_stock. |
| **Regras** | De PO: copia itens nao-totalmente-faturados (qty-invoiced_qty), erro se PO 'closed', update_stock=0 se ja ha GRN submetido; de GRN: copia itens, update_stock=0; avulsa: update_stock=1 (default); --cwip-asset-id exige asset under_construction e proibe combinar com PO/GRN (update_stock=0); tax via _calculate_tax. |
| **Efeitos colaterais** | INSERT em purchase_invoice (status='draft', com update_stock/cwip_asset_id/outstanding=grand_total) e purchase_invoice_item; audit_log via audit('create-purchase-invoice'); commit. Sem GL/SLE nesta etapa. |
| **Pré-condições** | PO/GRN existentes conforme o caso; fornecedor existente; asset under_construction se CWIP. |

### `update-purchase-invoice`

Atualiza a data de vencimento e/ou os itens de uma fatura em rascunho.

| | |
|---|---|
| **Entradas** | --purchase-invoice-id (obrigatorio); --due-date; --items (JSON array). |
| **Saídas** | purchase_invoice_id, updated_fields. |
| **Regras** | So atualiza se status='draft' (sugere cancelar antes); ao trocar itens, apaga/reinsere e recalcula tax/grand_total/outstanding; valida item_id/qty/rate; erro se nenhum campo informado. |
| **Efeitos colaterais** | UPDATE purchase_invoice (due_date e/ou totais, updated_at); DELETE/INSERT purchase_invoice_item; audit_log via audit('update-purchase-invoice'); commit. |
| **Pré-condições** | Fatura em rascunho. |

### `get-purchase-invoice`

Retorna a fatura de compra com itens e lancamentos de pagamento (PLE).

| | |
|---|---|
| **Entradas** | --purchase-invoice-id (obrigatorio). |
| **Saídas** | Campos da purchase_invoice + items + payments (payment_ledger_entry contra esta fatura). |
| **Regras** | Erro se nao encontrada; itens ordenados por linha. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Fatura existente. |

### `list-purchase-invoices`

Lista faturas de compra paginadas com filtros.

| | |
|---|---|
| **Entradas** | --company-id; --supplier-id; --pi-status; --from-date / --to-date (filtra posting_date); --limit (default 20); --offset (default 0). |
| **Saídas** | purchase_invoices (com supplier_name), total_count, limit, offset, has_more. |
| **Regras** | Join com supplier; ordena por posting_date desc, created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | nenhuma. |

### `submit-purchase-invoice`

Submete a fatura postando GL (despesa/SRNB + imposto + AP), PLE e, se update_stock, SLE + GL de inventario; trata returns e CWIP.

| | |
|---|---|
| **Entradas** | --purchase-invoice-id (obrigatorio). |
| **Saídas** | purchase_invoice_id, naming_series, status='submitted', is_return, voucher_type, gl_entries_created, sle_entries_created, update_stock, (cwip_asset_id/cwip_accumulation_id se CWIP). |
| **Regras** | So submete de 'draft'; valida 3-way match (PO-GRN-Invoice) conforme three_way_match_policy da empresa (disabled/strict/tolerant) se vinculada a PO e nao for return; DR despesa OU SRNB/inventario (se ha GRN) OU CWIP account (se cwip_asset); DR input tax por linha de imposto; CR Trade Payables; returns invertem os lados e PLE negativo; CWIP nao pode ser return; atualiza invoiced_qty/status do PO. |
| **Efeitos colaterais** | INSERT gl_entry (insert_gl_entries, com entry_set='cogs' para estoque) e payment_ledger_entry; se update_stock: INSERT stock_ledger_entry + GL de inventario; se CWIP: record_cwip_accumulation; UPDATE purchase_order_item.invoiced_qty e purchase_order.status; UPDATE purchase_invoice (status, naming); audit_log via audit('submit-purchase-invoice' ou 'submit-debit-note'); commit. |
| **Pré-condições** | Fatura em rascunho com itens; payable account; fiscal_year/cost_center; asset under_construction se CWIP. |

### `cancel-purchase-invoice`

Cancela uma fatura submetida revertendo GL, PLE, SLE (se update_stock) e acumulacao CWIP.

| | |
|---|---|
| **Entradas** | --purchase-invoice-id (obrigatorio). |
| **Saídas** | purchase_invoice_id, status='cancelled', gl_reversals, sle_reversals. |
| **Regras** | So cancela se status em submitted/overdue/partially_paid; reverte GL (inclui legs de estoque/COGS); se cwip_asset reverte acumulacoes; reverte SLE se update_stock; marca PLE como delinked; reverte invoiced_qty no PO e recalcula status. |
| **Efeitos colaterais** | Reversao em gl_entry (reverse_gl_entries) e stock_ledger_entry; UPDATE payment_ledger_entry (delinked=1); reverse_cwip_accumulations se aplicavel; UPDATE purchase_order_item.invoiced_qty e purchase_order.status; UPDATE purchase_invoice (status='cancelled'); audit_log via audit('cancel-purchase-invoice'); commit. |
| **Pré-condições** | Fatura submetida/overdue/parcialmente paga. |

### `update-invoice-outstanding`

Cross-skill (chamado por glue-payments) para reduzir o outstanding de uma fatura ao aplicar um pagamento.

| | |
|---|---|
| **Entradas** | --purchase-invoice-id (obrigatorio); --amount (obrigatorio, >0). |
| **Saídas** | purchase_invoice_id, outstanding_amount (novo), status (novo). |
| **Regras** | Erro se fatura nao encontrada ou amount<=0; delega a apply_payment_to_document da lib payment_clearing (regra canonica unica); over-payment e REJEITADO (ValueError vira erro). |
| **Efeitos colaterais** | UPDATE purchase_invoice (outstanding_amount/status via lib payment_clearing); audit_log via audit('update-invoice-outstanding'); commit. |
| **Pré-condições** | Fatura existente. |

## Notas de Debito

**Objetivo.** Criacao de notas de debito (devolucoes) em rascunho contra faturas de compra existentes.

### `create-debit-note`

Cria uma nota de debito (devolucao) em rascunho contra uma fatura de compra, com quantidades/valores negativos.

| | |
|---|---|
| **Entradas** | --against-invoice-id (obrigatorio); --items (obrigatorio, JSON: item_id, qty, rate opcional); --posting-date (default hoje); --reason. |
| **Saídas** | debit_note_id, against_invoice_id, total_amount (negativo). |
| **Regras** | Fatura original deve estar em submitted/partially_paid/paid/overdue; rate ausente e buscado na fatura original; qty/amount sao negativados; herda supplier/company/update_stock da original; documento criado como purchase_invoice com is_return=1 e return_against; status='draft' (submissao posterior via submit-purchase-invoice). |
| **Efeitos colaterais** | INSERT em purchase_invoice (is_return=1, status='draft', valores negativos) e purchase_invoice_item; audit_log via audit('create-debit-note'); commit. Nao posta GL/PLE/SLE. |
| **Pré-condições** | Fatura de compra original submetida/paga existente. |

## Custos de Importacao

**Objetivo.** Alocacao de custos de importacao (frete, seguro etc.) sobre itens de recebimentos, ajustando rate e postando GL.

### `add-landed-cost-voucher`

Aloca encargos de importacao entre os itens de recebimentos e capitaliza no estoque via GL.

| | |
|---|---|
| **Entradas** | --purchase-receipt-ids (obrigatorio, JSON array); --charges (obrigatorio, JSON: description, amount, allocation_method 'qty'\|'value', expense_account_id); --company-id (obrigatorio). |
| **Saídas** | landed_cost_voucher_id, total_landed_cost, gl_entries_created. |
| **Regras** | Recebimentos devem existir e estar 'submitted'; cada charge amount>0; aloca por quantidade ou por valor (ultimo item absorve diferenca de arredondamento); calcula final_rate=original_rate+encargo por unidade; GL so se expense_account_id e conta de stock existirem. |
| **Efeitos colaterais** | INSERT em landed_cost_voucher (status='submitted'), landed_cost_charge e landed_cost_item; INSERT gl_entry (DR Stock In Hand / CR conta de despesa via insert_gl_entries); audit_log via audit('add-landed-cost-voucher'); commit. |
| **Pré-condições** | Recebimentos submetidos; conta de estoque da empresa para GL. |

## Blanket PO

**Objetivo.** Acordos-quadro (blanket orders) de compra: criar, ativar, consultar e listar.

### `add-blanket-po`

Cria um pedido de compra blanket (acordo-quadro) em rascunho com itens e periodo de validade.

| | |
|---|---|
| **Entradas** | --supplier-id (obrigatorio, id ou name); --items (obrigatorio, JSON: item_id, qty, rate, uom); --company-id (obrigatorio); --valid-from (obrigatorio); --valid-to (obrigatorio). |
| **Saídas** | blanket_order_id, supplier_id, total_qty, valid_from, valid_to. |
| **Regras** | Fornecedor deve estar 'active'; valida company; valid_to deve ser > valid_from; cada item exige item_id, qty>0, rate>0; blanket_order_type='buying'. |
| **Efeitos colaterais** | INSERT em blanket_order (status='draft', type='buying') e blanket_order_item; UPDATE blanket_order (total_qty); audit_log via audit('add-blanket-po'); commit. |
| **Pré-condições** | Fornecedor ativo; company existente. |

### `submit-blanket-po`

Ativa um blanket PO em rascunho.

| | |
|---|---|
| **Entradas** | --blanket-order-id (obrigatorio). |
| **Saídas** | blanket_order_id, doc_status='active'. |
| **Regras** | Erro se nao encontrado; so ativa de 'draft'; tipo deve ser 'buying'. |
| **Efeitos colaterais** | UPDATE blanket_order (status='active', updated_at); audit_log via audit('submit-blanket-po'); commit. |
| **Pré-condições** | Blanket PO de compra em rascunho. |

### `get-blanket-po`

Retorna um blanket PO com seus itens.

| | |
|---|---|
| **Entradas** | --blanket-order-id (obrigatorio). |
| **Saídas** | Campos do blanket_order + items. |
| **Regras** | Erro se nao encontrado. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Blanket PO existente. |

### `list-blanket-pos`

Lista blanket POs do tipo 'buying' paginados com filtros.

| | |
|---|---|
| **Entradas** | --company-id; --supplier-id; --blanket-status; --limit (default 20); --offset (default 0). |
| **Saídas** | blanket_orders (lista), total_count, limit, offset, has_more. |
| **Regras** | Sempre filtra blanket_order_type='buying'; ordena por created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | nenhuma. |

## Conversao p/ PO

**Objetivo.** Geracao de pedidos de compra a partir de blanket orders (drawdown) ou de pedidos de venda (back-to-back).

### `create-po-from-blanket`

Cria um PO em rascunho consumindo (drawdown) quantidades de um blanket PO ativo.

| | |
|---|---|
| **Entradas** | --blanket-order-id (obrigatorio); --items (obrigatorio, JSON: item_id, qty, rate opcional, uom, warehouse_id, required_date); --posting-date (default hoje); --tax-template-id. |
| **Saídas** | purchase_order_id, blanket_order_id, total_amount, grand_total. |
| **Regras** | Blanket deve estar 'active', tipo 'buying' e nao expirado (valid_to>=hoje); cada item deve pertencer ao blanket e qty<=remaining (quantity-ordered_qty); rate padrao vem do blanket; atualiza ordered_qty dos itens e total do blanket. |
| **Efeitos colaterais** | INSERT em purchase_order (status='draft') e purchase_order_item; UPDATE blanket_order_item.ordered_qty e blanket_order.ordered_qty; audit_log via audit('create-po-from-blanket'); commit. |
| **Pré-condições** | Blanket PO ativo e vigente. |

### `create-po-from-so`

Cria pedidos de compra (um por fornecedor) a partir de um pedido de venda, usando o fornecedor padrao de cada item.

| | |
|---|---|
| **Entradas** | --sales-order-id (obrigatorio); --posting-date (default hoje); --tax-template-id. |
| **Saídas** | sales_order_id, purchase_orders_created, purchase_orders (lista com supplier/grand_total/items_count), items_without_supplier. |
| **Regras** | SO deve estar em draft/confirmed; para cada item busca fornecedor padrao via item_supplier (menor priority); itens sem fornecedor vao para items_without_supplier; agrupa por fornecedor; pula fornecedores nao-ativos; erro se nenhum item tem fornecedor configurado. |
| **Efeitos colaterais** | INSERT em purchase_order (status='draft') e purchase_order_item (um PO por fornecedor); audit_log via audit('create-po-from-so'); commit. |
| **Pré-condições** | Sales order existente com itens; mapeamentos item_supplier configurados. |

## Contas Recorrentes

**Objetivo.** Templates de contas/faturas recorrentes de fornecedores e geracao automatica das faturas conforme frequencia.

### `add-recurring-bill-template`

Cria um template de fatura de compra recorrente em rascunho.

| | |
|---|---|
| **Entradas** | --supplier-id (obrigatorio, id ou name, ativo); --items (obrigatorio, JSON: item_id, qty, rate, uom); --frequency (obrigatorio: weekly\|monthly\|quarterly\|semi_annually\|annually); --start-date (obrigatorio); --company-id (obrigatorio); --end-date; --tax-template-id; --auto-submit (flag, default False). |
| **Saídas** | template_id, frequency, start_date, next_bill_date. |
| **Regras** | Frequencia deve estar em VALID_FREQUENCIES; fornecedor deve estar 'active'; valida company; cada item exige item_id; next_bill_date inicial = start_date; auto_submit gravado como 0/1. |
| **Efeitos colaterais** | INSERT em recurring_bill_template (status='draft') e recurring_bill_template_item; audit_log via audit('add-recurring-bill-template'); commit. |
| **Pré-condições** | Fornecedor ativo; company existente. |

### `list-recurring-bill-templates`

Lista templates de contas recorrentes paginados com filtros.

| | |
|---|---|
| **Entradas** | --company-id; --supplier-id; --template-status; --limit (default 20); --offset (default 0). |
| **Saídas** | recurring_bill_templates (lista), total_count, limit, offset, has_more. |
| **Regras** | Ordena por next_bill_date. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | nenhuma. |

### `generate-recurring-bills`

Cron: gera automaticamente faturas de compra a partir de templates ativos com vencimento ate a data de referencia.

| | |
|---|---|
| **Entradas** | --company-id (obrigatorio); --as-of-date (default hoje). |
| **Saídas** | bills_generated, templates_processed, templates_completed, bills (lista), errors (lista). |
| **Regras** | Seleciona templates 'active' com next_bill_date<=as_of_date e (end_date nulo ou >=as_of_date); due_date = next_date+30 dias; se auto_submit posta GL (DR despesa / CR payable) e status='submitted' com naming; avanca next_bill_date pela frequencia; marca template 'completed' se passar do end_date; erros por template sao coletados (com rollback do template em falha de GL). |
| **Efeitos colaterais** | INSERT em purchase_invoice (status draft ou submitted) e purchase_invoice_item; se auto_submit: INSERT gl_entry; UPDATE recurring_bill_template (last/next_bill_date, status); commit. Nao gera audit_log por fatura. |
| **Pré-condições** | Templates ativos com itens; contas payable/expense da empresa para auto_submit. |

## Politicas de Compra

**Objetivo.** Configuracao de politicas da empresa para tolerancia de recebimento (GRN) e 3-way match.

### `update-receipt-tolerance`

Atualiza o percentual de tolerancia de recebimento (GRN) de uma empresa.

| | |
|---|---|
| **Entradas** | --company-id (obrigatorio); --tolerance-pct (default '0'; 0=estrito). |
| **Saídas** | company_id, receipt_tolerance_pct. |
| **Regras** | Percentual nao pode ser negativo nem exceder 100; valida existencia da empresa. |
| **Efeitos colaterais** | UPDATE company (receipt_tolerance_pct, updated_at); audit_log via audit('update-receipt-tolerance'); commit. |
| **Pré-condições** | Company existente. |

### `update-three-way-match-policy`

Atualiza a politica de 3-way match (PO-GRN-Invoice) de uma empresa.

| | |
|---|---|
| **Entradas** | --company-id (obrigatorio); --policy (obrigatorio: strict\|tolerant\|disabled). |
| **Saídas** | company_id, three_way_match_policy. |
| **Regras** | Politica restrita a strict/tolerant/disabled; valida existencia da empresa. |
| **Efeitos colaterais** | UPDATE company (three_way_match_policy, updated_at); audit_log via audit('update-three-way-match-policy'); commit. |
| **Pré-condições** | Company existente. |

## Configuracoes de Item e Resumo

**Objetivo.** Acoes auxiliares de configuracao de UOM de compra por item e resumo geral do dominio de compras (acoes que nao se encaixam nos grupos do ciclo P2P).

### `set-item-purchase-uom`

Define a UOM de compra padrao e o fator de conversao para a UOM de estoque de um item.

| | |
|---|---|
| **Entradas** | --item-id (obrigatorio); --purchase-uom (obrigatorio); --conversion-factor (obrigatorio, >0). |
| **Saídas** | uom_conversion_id, item_id, purchase_uom, stock_uom, conversion_factor, action ('created'\|'updated'), message. |
| **Regras** | Valida item; conversion_factor>0; resolve IDs de UOM na tabela uom (cai para a string do nome se nao existir); cria ou atualiza a conversao from_uom(purchase)->to_uom(stock). |
| **Efeitos colaterais** | INSERT ou UPDATE em uom_conversion; audit_log via audit('set-item-purchase-uom'); commit. |
| **Pré-condições** | Item existente. |

### `status`

Retorna um resumo de compras da empresa (contagens e saldo devedor).

| | |
|---|---|
| **Entradas** | --company-id (opcional; usa a primeira empresa se omitido). |
| **Saídas** | suppliers (contagem), purchase_orders (contagem por status + total), purchase_invoices (contagem por status + total), total_outstanding. |
| **Regras** | Erro se nenhuma empresa existir; agrupa POs e PIs por status; total_outstanding soma faturas submitted/overdue/partially_paid. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Pelo menos uma empresa cadastrada. |

