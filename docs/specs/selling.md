# Vendas (Order-to-Cash) — `glue-selling`

> Spec funcional por ação. Gerada de `scripts/glue-selling/db_query.py`. 14 funcionalidades · 60 ações.

## Clientes

**Objetivo.** Cadastrar, consultar, listar e importar clientes da empresa, incluindo limite de crédito.

### `add-customer`

Cria um registro de cliente no status 'active'.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --company-id (obrigatório); --customer-type (default 'company', um de company\|individual); --customer-group; --payment-terms-id; --credit-limit (default 0); --tax-id; --exempt-from-sales-tax; --primary-address; --primary-contact; --email; --phone; --custom-fields (JSON). |
| **Saídas** | customer_id, name, customer_type (mais quaisquer custom fields mesclados). |
| **Regras** | Valida existência de company_id; valida customer_type contra company\|individual; valida payment_terms_id se informado; credit_limit normalizado para currency; falha de IntegrityError -> erro de duplicidade; rollback se erro de custom field. |
| **Efeitos colaterais** | INSERT em customer (status='active'); persiste custom fields; audit_log via audit(); commit. |
| **Pré-condições** | Empresa existente; payment_terms existente se informado. |

### `update-customer`

Atualiza campos de um cliente existente (resolvido por id ou name).

| | |
|---|---|
| **Entradas** | --customer-id (obrigatório, aceita id ou name); campos opcionais: --name, --credit-limit, --payment-terms-id, --customer-group, --customer-type, --email, --phone. |
| **Saídas** | customer_id, updated_fields (lista). |
| **Regras** | Cliente deve existir; valida customer_type se informado; erro 'No fields to update' se nada fornecido; seta updated_at. |
| **Efeitos colaterais** | UPDATE dynamic em customer; audit_log; commit. |
| **Pré-condições** | Cliente existente. |

### `get-customer`

Retorna um cliente com resumo de faturas em aberto (outstanding).

| | |
|---|---|
| **Entradas** | --customer-id (obrigatório, aceita id ou name). |
| **Saídas** | Todos os campos do cliente + total_outstanding + outstanding_invoice_count (mais custom fields mesclados). |
| **Regras** | Cliente deve existir; total_outstanding soma outstanding_amount de sales_invoice em status submitted/overdue/partially_paid com saldo>0. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Cliente existente. |

### `list-customers`

Lista clientes com filtros e paginação.

| | |
|---|---|
| **Entradas** | --company-id; --customer-group; --search (em name/tax_id); --limit (default 20); --offset (default 0). |
| **Saídas** | customers (lista), total_count, limit, offset, has_more. |
| **Regras** | Filtros opcionais combinados via AND; ordena por name; conta total separadamente. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `import-customers`

Importa clientes em lote a partir de um arquivo CSV.

| | |
|---|---|
| **Entradas** | --csv-path (obrigatório, deve terminar em .csv); --company-id (obrigatório). Colunas CSV: name, customer_type, territory, default_currency, email, phone, tax_id. |
| **Saídas** | imported, skipped, total_rows. |
| **Regras** | Valida que path é arquivo .csv real; valida CSV via validate_csv; pula linhas com name duplicado na empresa; gera naming_series para cada novo cliente. |
| **Efeitos colaterais** | INSERT em customer por linha nova (com naming_series); commit. Não grava audit_log. |
| **Pré-condições** | Arquivo CSV válido existente; empresa existente. |

## Cotações

**Objetivo.** Criar, editar, consultar, listar, submeter e converter cotações em pedidos de venda.

### `add-quotation`

Cria uma cotação no status 'draft' com itens e impostos calculados.

| | |
|---|---|
| **Entradas** | --customer-id (obrigatório); --posting-date (obrigatório); --items (obrigatório, JSON array); --company-id (obrigatório); --valid-till; --tax-template-id. |
| **Saídas** | quotation_id, total_amount, tax_amount, grand_total. |
| **Regras** | Cliente deve estar 'active'; empresa deve existir; cada item exige item_id, qty>0; aplica discount_percentage por linha; calcula imposto via tax template; status inicial 'draft' (sem naming_series). |
| **Efeitos colaterais** | INSERT em quotation (status='draft') e quotation_item; audit_log; commit. |
| **Pré-condições** | Cliente ativo e empresa existentes; itens válidos. |

### `update-quotation`

Atualiza valid_until e/ou itens de uma cotação em rascunho.

| | |
|---|---|
| **Entradas** | --quotation-id (obrigatório); --valid-till; --items (JSON). |
| **Saídas** | quotation_id, updated_fields. |
| **Regras** | Cotação deve existir e estar 'draft'; se --items, deleta itens antigos e reinsere recalculando total/tax/grand_total; erro se nada a atualizar. |
| **Efeitos colaterais** | UPDATE quotation; DELETE+INSERT quotation_item quando itens informados; audit_log; commit. |
| **Pré-condições** | Cotação em status 'draft'. |

### `get-quotation`

Retorna uma cotação com suas linhas de item.

| | |
|---|---|
| **Entradas** | --quotation-id (obrigatório). |
| **Saídas** | Campos da quotation + items (lista com item_name). |
| **Regras** | Cotação deve existir. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Cotação existente. |

### `list-quotations`

Lista cotações com filtros e paginação.

| | |
|---|---|
| **Entradas** | --company-id; --customer-id; --status; --from-date; --to-date; --limit (default 20); --offset (default 0). |
| **Saídas** | quotations (lista, com customer_name), total_count, limit, offset, has_more. |
| **Regras** | Filtros combinados por AND sobre quotation_date; ordena por quotation_date e created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `submit-quotation`

Submete uma cotação: draft -> open, gerando naming_series.

| | |
|---|---|
| **Entradas** | --quotation-id (obrigatório). |
| **Saídas** | quotation_id, naming_series, status ('open'). |
| **Regras** | Cotação deve estar 'draft'; gera naming_series via get_next_name; sem postagens contábeis. |
| **Efeitos colaterais** | UPDATE quotation (status='open', naming_series); audit_log; commit. |
| **Pré-condições** | Cotação em status 'draft'. |

### `convert-quotation-to-so`

Cria um pedido de venda (draft) a partir de uma cotação e marca-a como 'ordered'.

| | |
|---|---|
| **Entradas** | --quotation-id (obrigatório); --delivery-date. |
| **Saídas** | quotation_id, sales_order_id, status ('ordered'). |
| **Regras** | Cotação deve estar 'open' ou 'draft' e ter itens; copia itens para sales_order_item; SO criado em 'draft'; atualiza quotation.status='ordered' e converted_to. |
| **Efeitos colaterais** | INSERT sales_order (status='draft') e sales_order_item; UPDATE quotation (status='ordered', converted_to); audit_log; commit. |
| **Pré-condições** | Cotação em 'open'/'draft' com itens. |

## Pedidos de Venda

**Objetivo.** Criar, editar, consultar, listar, confirmar, cancelar e fechar pedidos de venda com checagem de limite de crédito.

### `add-sales-order`

Cria um pedido de venda no status 'draft' (com aplicação de pricing rules).

| | |
|---|---|
| **Entradas** | --customer-id (obrigatório); --posting-date (obrigatório, vira order_date); --items (obrigatório, JSON); --company-id (obrigatório); --delivery-date; --tax-template-id. |
| **Saídas** | sales_order_id, total_amount, tax_amount, grand_total. |
| **Regras** | Cliente deve estar 'active'; empresa deve existir; aplica pricing rules (apply_pricing=True) por item; qty>0; calcula imposto; status inicial 'draft'. |
| **Efeitos colaterais** | INSERT sales_order (status='draft') e sales_order_item; audit_log; commit. |
| **Pré-condições** | Cliente ativo e empresa existentes. |

### `update-sales-order`

Atualiza delivery_date e/ou itens de um pedido em rascunho.

| | |
|---|---|
| **Entradas** | --sales-order-id (obrigatório); --delivery-date; --items (JSON). |
| **Saídas** | sales_order_id, updated_fields. |
| **Regras** | SO deve existir e estar 'draft'; se --items, deleta e reinsere itens (com pricing) recalculando totais; erro se nada a atualizar. |
| **Efeitos colaterais** | UPDATE sales_order; DELETE+INSERT sales_order_item quando itens informados; audit_log; commit. |
| **Pré-condições** | Pedido em status 'draft'. |

### `get-sales-order`

Retorna um pedido com itens e resumo de entregas/faturas vinculadas.

| | |
|---|---|
| **Entradas** | --sales-order-id (obrigatório). |
| **Saídas** | Campos do SO + items + delivery_notes (não-cancelados) + sales_invoices (não-cancelados). |
| **Regras** | SO deve existir. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Pedido existente. |

### `list-sales-orders`

Lista pedidos de venda com filtros e paginação.

| | |
|---|---|
| **Entradas** | --company-id; --customer-id; --status; --from-date; --to-date; --limit (default 20); --offset (default 0). |
| **Saídas** | sales_orders (lista, com customer_name, per_delivered, per_invoiced), total_count, limit, offset, has_more. |
| **Regras** | Filtros por AND sobre order_date; ordena por order_date/created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `submit-sales-order`

Confirma um pedido (draft -> confirmed) com checagem de limite de crédito.

| | |
|---|---|
| **Entradas** | --sales-order-id (obrigatório). |
| **Saídas** | sales_order_id, naming_series, status ('confirmed'). |
| **Regras** | SO deve estar 'draft'; cliente deve estar 'active'; itens com qty>0 e rate>0; se credit_limit>0, exposição (outstanding AR + pedidos confirmed não-faturados + este grand_total) não pode exceder o limite, senão erro; gera naming_series. |
| **Efeitos colaterais** | UPDATE sales_order (status='confirmed', naming_series); audit_log; commit. Sem GL/SLE/PLE. |
| **Pré-condições** | Pedido em 'draft' com itens válidos; cliente ativo. |

### `cancel-sales-order`

Cancela um pedido somente se não houver entregas/faturas ativas vinculadas.

| | |
|---|---|
| **Entradas** | --sales-order-id (obrigatório). |
| **Saídas** | sales_order_id, status ('cancelled'). |
| **Regras** | Erro se já cancelado; erro se houver delivery_note ou sales_invoice não-cancelados vinculados. |
| **Efeitos colaterais** | UPDATE sales_order (status='cancelled'); audit_log; commit. |
| **Pré-condições** | Pedido sem documentos-filhos ativos. |

### `close-sales-order`

Fecha um pedido parcialmente atendido, impedindo novas DNs/faturas mas preservando filhos existentes.

| | |
|---|---|
| **Entradas** | --sales-order-id (obrigatório); --reason; --closed-by. |
| **Saídas** | sales_order_id, doc_status ('closed'), close_reason, closed_by. |
| **Regras** | Erro se status for draft/cancelled/closed; grava motivo e responsável. |
| **Efeitos colaterais** | UPDATE sales_order (status='closed', close_reason, closed_by); audit_log; commit. |
| **Pré-condições** | Pedido em status que não seja draft/cancelled/closed. |

## Emendas

**Objetivo.** Emendar pedidos de venda criando uma nova versão vinculada e rastrear a cadeia de emendas.

### `amend-sales-order`

Cancela o pedido original (sem filhos ativos) e cria um novo SO 'draft' vinculado via amended_from.

| | |
|---|---|
| **Entradas** | --sales-order-id (obrigatório); --items (JSON opcional; se omitido, copia itens do original). |
| **Saídas** | new_sales_order_id, amended_from, original_status ('cancelled'), total_amount, tax_amount, grand_total. |
| **Regras** | SO não pode ser draft/cancelled/closed; bloqueia se houver delivery_note ou sales_invoice ativos; recalcula totais (com pricing) e impostos; novo SO em 'draft'. |
| **Efeitos colaterais** | UPDATE sales_order original (status='cancelled'); INSERT novo sales_order (amended_from) e sales_order_item; dois audit_log (cancelamento e criação); commit. |
| **Pré-condições** | Pedido amendável sem documentos-filhos ativos. |

### `get-amendment-history`

Rastreia a cadeia completa de emendas de um pedido (ancestrais e descendentes).

| | |
|---|---|
| **Entradas** | --sales-order-id (obrigatório). |
| **Saídas** | sales_order_id, amendment_chain (lista de {sales_order_id, status, amended_from, grand_total}), chain_length. |
| **Regras** | SO deve existir; caminha para trás via amended_from até a raiz e para frente via descendentes. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Pedido existente. |

## Notas de Entrega

**Objetivo.** Criar, consultar, listar, submeter (com postagens de estoque/COGS) e cancelar notas de entrega.

### `create-delivery-note`

Cria uma nota de entrega (draft) a partir de um pedido de venda, total ou parcial.

| | |
|---|---|
| **Entradas** | --sales-order-id (obrigatório); --posting-date (default hoje); --items (JSON para entrega parcial; omitido = entrega tudo pendente); --warehouse-id (override para todos os itens). |
| **Saídas** | delivery_note_id, sales_order_id, total_qty, item_count. |
| **Regras** | SO deve estar 'confirmed' ou 'partially_delivered' (erro se 'closed'); em parcial, qty>0 e <= remaining por item; erro se nada a entregar; DN criada em 'draft'. |
| **Efeitos colaterais** | INSERT delivery_note (status='draft') e delivery_note_item; audit_log; commit. Sem postagens contábeis ainda. |
| **Pré-condições** | Pedido confirmado/parcialmente entregue com saldo a entregar. |

### `get-delivery-note`

Retorna uma nota de entrega com seus itens.

| | |
|---|---|
| **Entradas** | --delivery-note-id (obrigatório). |
| **Saídas** | Campos da DN + items (com item_name, item_code). |
| **Regras** | DN deve existir. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nota de entrega existente. |

### `list-delivery-notes`

Lista notas de entrega com filtros e paginação.

| | |
|---|---|
| **Entradas** | --company-id; --customer-id; --status; --from-date; --to-date; --limit (default 20); --offset (default 0). |
| **Saídas** | delivery_notes (lista, com customer_name, total_qty), total_count, limit, offset, has_more. |
| **Regras** | Filtros por AND sobre posting_date; ordena por posting_date/created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `submit-delivery-note`

Submete uma DN: cria SLE (saída de estoque) e GL de COGS, atualizando o SO.

| | |
|---|---|
| **Entradas** | --delivery-note-id (obrigatório). |
| **Saídas** | delivery_note_id, naming_series, status ('submitted'), sle_entries_created, gl_entries_created. |
| **Regras** | DN deve estar 'draft'; SO vinculado não pode estar cancelado; itens de serviço são pulados; resolve warehouse (item/default da empresa); só permite despachar de warehouse tipo 'stores'; gera SLE negativos e GL de COGS via lib; atualiza delivered_qty e status do SO. |
| **Efeitos colaterais** | INSERT stock_ledger_entry (negativos) e gl_entry (COGS); UPDATE serial_number p/ 'delivered'; UPDATE delivery_note (status='submitted', naming_series); UPDATE sales_order_item.delivered_qty e recálculo de per_delivered/status do SO; audit_log; commit. |
| **Pré-condições** | DN em 'draft' com itens; warehouse 'stores' válido; SO não cancelado. |

### `cancel-delivery-note`

Cancela uma DN submetida: reverte SLE + GL e reverte delivered_qty do SO.

| | |
|---|---|
| **Entradas** | --delivery-note-id (obrigatório). |
| **Saídas** | delivery_note_id, status ('cancelled'), sle_reversals, gl_reversals. |
| **Regras** | DN deve estar 'submitted'; erro se houver faturas ativas referenciando a DN; reverte SLE e GL via lib; recalcula status do SO (pode voltar a 'confirmed'). |
| **Efeitos colaterais** | INSERT entradas reversoras em stock_ledger_entry e gl_entry; UPDATE delivery_note (status='cancelled'); decrementa sales_order_item.delivered_qty (mínimo 0) e recalcula status do SO; audit_log; commit. |
| **Pré-condições** | DN 'submitted' sem faturas ativas vinculadas. |

## Faturas de Venda

**Objetivo.** Criar (de SO/DN/avulsa), editar, consultar, listar, submeter (com GL/PLE/SLE), cancelar e atualizar saldo de faturas de venda.

### `create-sales-invoice`

Cria uma fatura de venda (draft) a partir de SO, DN ou avulsa.

| | |
|---|---|
| **Entradas** | --sales-order-id OU --delivery-note-id OU (avulsa: --customer-id + --items + --company-id); --posting-date (default hoje); --tax-template-id; --due-date; --payment-terms-id. |
| **Saídas** | sales_invoice_id, total_amount, tax_amount, grand_total, update_stock. |
| **Regras** | De SO: status valido (confirmed/partially_delivered/fully_delivered/partially_invoiced), só itens não-faturados; se SO tem DN submetida, update_stock=0. De DN: DN deve estar 'submitted', update_stock=0. Avulsa: cliente ativo, itens válidos, update_stock=1 (default). Calcula due_date por payment terms ou +30 dias. |
| **Efeitos colaterais** | INSERT sales_invoice (status='draft', outstanding=grand_total) e sales_invoice_item; audit_log; commit. Sem GL/PLE ainda. |
| **Pré-condições** | SO/DN em status válido, ou cliente ativo para avulsa. |

### `update-sales-invoice`

Atualiza due_date e/ou itens de uma fatura em rascunho.

| | |
|---|---|
| **Entradas** | --sales-invoice-id (obrigatório); --due-date; --items (JSON). |
| **Saídas** | sales_invoice_id, updated_fields. |
| **Regras** | Fatura deve existir e estar 'draft'; se --items, deleta e reinsere itens recalculando total/tax/grand_total/outstanding; erro se nada a atualizar. |
| **Efeitos colaterais** | UPDATE sales_invoice; DELETE+INSERT sales_invoice_item quando itens informados; audit_log; commit. |
| **Pré-condições** | Fatura em status 'draft'. |

### `get-sales-invoice`

Retorna uma fatura com itens e lançamentos de pagamento (PLE).

| | |
|---|---|
| **Entradas** | --sales-invoice-id (obrigatório). |
| **Saídas** | Campos da fatura + items + payments (PLE de tipo sales_invoice/credit_note). |
| **Regras** | Fatura deve existir. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Fatura existente. |

### `list-sales-invoices`

Lista faturas de venda com filtros e paginação.

| | |
|---|---|
| **Entradas** | --company-id; --customer-id; --status; --from-date; --to-date; --limit (default 20); --offset (default 0). |
| **Saídas** | sales_invoices (lista, com customer_name, outstanding_amount, is_return), total_count, limit, offset, has_more. |
| **Regras** | Filtros por AND sobre posting_date; ordena por posting_date/created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `submit-sales-invoice`

Submete uma fatura: posta GL de receita + PLE (e opcionalmente SLE/COGS se update_stock).

| | |
|---|---|
| **Entradas** | --sales-invoice-id (obrigatório). |
| **Saídas** | sales_invoice_id, naming_series, status ('submitted'), gl_entries_created, sle_entries_created, update_stock. |
| **Regras** | Fatura deve estar 'draft'; cliente deve estar 'active'; aplica política de crédito (_enforce_credit_policy: bloqueia suspended/on_hold e excesso de credit_limit); DR Receivable / CR Receita / CR Imposto (invertido para credit_note); se update_stock cria SLE e GL de COGS; gera naming_series; atualiza invoiced_qty/status do SO. |
| **Efeitos colaterais** | INSERT gl_entry (receita + COGS), payment_ledger_entry, e stock_ledger_entry se update_stock; UPDATE sales_invoice (status='submitted', naming_series); UPDATE sales_order_item.invoiced_qty e status do SO; audit_log; commit. |
| **Pré-condições** | Fatura em 'draft' com itens; cliente ativo dentro da política de crédito; contas receivable/income configuradas. |

### `cancel-sales-invoice`

Cancela uma fatura: reverte GL + PLE (e SLE se update_stock).

| | |
|---|---|
| **Entradas** | --sales-invoice-id (obrigatório). |
| **Saídas** | sales_invoice_id, status ('cancelled'), gl_reversals, sle_reversals. |
| **Regras** | Fatura deve estar 'submitted', 'overdue' ou 'partially_paid'; reverte GL (incl. COGS) e SLE via lib; marca PLE como delinked; zera outstanding; reverte invoiced_qty do SO. |
| **Efeitos colaterais** | INSERT entradas reversoras em gl_entry e stock_ledger_entry; UPDATE payment_ledger_entry (delinked=1); UPDATE sales_invoice (status='cancelled', outstanding=0); decrementa sales_order_item.invoiced_qty e recalcula status do SO; audit_log; commit. |
| **Pré-condições** | Fatura em status submitted/overdue/partially_paid. |

### `update-invoice-outstanding`

Atualiza o saldo em aberto de uma fatura quando um pagamento é alocado (chamado por glue-payments).

| | |
|---|---|
| **Entradas** | --sales-invoice-id (obrigatório); --amount (obrigatório, >0). |
| **Saídas** | sales_invoice_id, outstanding_amount, status. |
| **Regras** | Fatura deve estar submitted/overdue/partially_paid; amount>0; delega cálculo/escrita à lib payment_clearing.apply_payment_to_document (rejeita over-payment). |
| **Efeitos colaterais** | UPDATE sales_invoice (outstanding_amount e status via lib compartilhada); audit_log; commit. |
| **Pré-condições** | Fatura clearable (submitted/overdue/partially_paid). |

## Notas de Crédito/Estorno

**Objetivo.** Criar e listar notas de crédito (faturas de devolução com valores negativos) contra faturas originais.

### `create-credit-note`

Cria uma nota de crédito (fatura is_return=1, valores negativos) contra uma fatura original.

| | |
|---|---|
| **Entradas** | --against-invoice-id (obrigatório); --items (obrigatório, JSON); --posting-date (default hoje); --reason. |
| **Saídas** | credit_note_id, against_invoice_id, grand_total, is_return (True). |
| **Regras** | Fatura original deve estar submitted/overdue/partially_paid/paid; cada item deve existir na fatura original e qty de retorno <= qty original; quantidades/valores armazenados negativos; nota de crédito criada em 'draft' com return_against. |
| **Efeitos colaterais** | INSERT sales_invoice (is_return=1, status='draft', return_against) e sales_invoice_item (negativos); audit_log; commit. Postagens contábeis só no submit-sales-invoice. |
| **Pré-condições** | Fatura original em status válido com itens correspondentes. |

### `list-credit-notes`

Lista notas de crédito (faturas com is_return=1) com filtros e paginação.

| | |
|---|---|
| **Entradas** | --company-id; --customer-id; --status; --from-date; --to-date; --limit (default 20); --offset (default 0). |
| **Saídas** | credit_notes (lista, com customer_name e return_against_name), total_count, limit, offset, has_more. |
| **Regras** | Sempre filtra is_return=1; demais filtros por AND sobre posting_date. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Crédito e Cobrança (Dunning)

**Objetivo.** Gerir limite/status de crédito do cliente e executar ciclos de cobrança escalonada (dunning).

### `check-credit-limit`

Calcula o crédito disponível de um cliente (somente leitura).

| | |
|---|---|
| **Entradas** | --customer-id (obrigatório). |
| **Saídas** | customer_id, name, credit_limit, credit_status, outstanding_ar, available_credit, limit_enforced. |
| **Regras** | Cliente deve existir; outstanding_ar soma outstanding_amount de faturas submitted is_return=0; available_credit = limit - outstanding se limit>0, senão None. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Cliente existente. |

### `place-customer-on-hold`

Define o credit_status do cliente para on_hold/suspended (ou active para liberar).

| | |
|---|---|
| **Entradas** | --customer-id (obrigatório); --credit-status (default 'on_hold', um de active\|on_hold\|suspended); --reason. |
| **Saídas** | customer_id, credit_status (novo), previous. |
| **Regras** | Cliente deve existir; valida credit_status; preserva valor anterior para auditoria. |
| **Efeitos colaterais** | UPDATE customer (credit_status, updated_at); commit; audit_log com old/new values e descrição (reason). |
| **Pré-condições** | Cliente existente. |

### `add-dunning-level`

Configura um nível de escalonamento de cobrança (ação a tomar em N dias de atraso).

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --level (obrigatório, inteiro 1-10); --days-overdue (obrigatório, >=0); --dunning-action (obrigatório, um de email\|hold\|call\|suspend); --template-id; --description. |
| **Saídas** | id, company_id, level, days_overdue, action. |
| **Regras** | Valida faixa de level e days_overdue; valida dunning-action; IntegrityError -> nível duplicado para a empresa. |
| **Efeitos colaterais** | INSERT dunning_level; commit; audit_log. |
| **Pré-condições** | Empresa existente. |

### `run-dunning-cycle`

Encontra faturas vencidas, casa cada cliente ao maior nível aplicável e executa a ação configurada (incl. enfileirar e-mail).

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --run-date (default hoje); --db-path (para subprocess de e-mail). |
| **Saídas** | run_date, company_id, customers_processed, runs_created, actions (contagem por tipo), emails (sent/skipped), run_ids. |
| **Regras** | Sem níveis configurados retorna mensagem; busca faturas submitted is_return=0 com outstanding>0 e due_date<hoje; maior nível por cliente vence; idempotente por (cliente, nível, dia) - pula duplicatas; 'hold'/'suspend' alteram credit_status; 'call' apenas registra; 'email' enfileira após o commit via ACTION send-email do glue-alerts; e-mail/template ausente é skip-with-note. |
| **Efeitos colaterais** | INSERT dunning_run (status='completed'); UPDATE customer.credit_status para hold/suspend; subprocess para glue-alerts send-email (escreve outbox no módulo de alertas); UPDATE dunning_run.generated_email_id/notes; audit não emitido aqui; dois commits (run e pós-e-mail). |
| **Pré-condições** | Empresa com níveis de dunning configurados; glue-alerts disponível para envios de e-mail. |

### `list-dunning-runs`

Lista o histórico de execuções de dunning, opcionalmente filtrado por cliente/empresa.

| | |
|---|---|
| **Entradas** | --customer-id; --company-id; --limit. |
| **Saídas** | runs (lista de dunning_run). |
| **Regras** | Filtros opcionais combinados; ordena por run_date e created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Parceiros de Venda

**Objetivo.** Cadastrar e listar parceiros de venda com taxa de comissão.

### `add-sales-partner`

Cria um parceiro de venda com taxa de comissão.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --commission-rate (obrigatório). |
| **Saídas** | sales_partner_id, name, commission_rate. |
| **Regras** | Nome e commission-rate obrigatórios; rate normalizado para currency; IntegrityError -> erro de duplicidade. |
| **Efeitos colaterais** | INSERT sales_partner; audit_log; commit. |
| **Pré-condições** | Nenhuma. |

### `list-sales-partners`

Lista parceiros de venda com paginação.

| | |
|---|---|
| **Entradas** | --limit (default 20); --offset (default 0). |
| **Saídas** | sales_partners (lista), total_count, limit, offset, has_more. |
| **Regras** | Ordena por name; conta total separadamente. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Faturas Recorrentes

**Objetivo.** Criar, editar, listar templates de fatura recorrente e gerar automaticamente faturas das templates vencidas.

### `add-recurring-template`

Cria uma template de fatura recorrente no status 'draft'.

| | |
|---|---|
| **Entradas** | --customer-id (obrigatório); --items (obrigatório, JSON); --frequency (obrigatório, um de weekly\|monthly\|quarterly\|semi_annually\|annually); --start-date (obrigatório); --company-id (obrigatório); --end-date; --tax-template-id; --payment-terms-id. |
| **Saídas** | template_id, frequency, start_date, next_invoice_date (=start_date). |
| **Regras** | Valida frequency; cliente deve estar 'active'; empresa deve existir; itens não-vazios com item_id; next_invoice_date inicial = start_date. |
| **Efeitos colaterais** | INSERT recurring_invoice_template (status='draft') e recurring_invoice_template_item; audit_log; commit. |
| **Pré-condições** | Cliente ativo e empresa existentes. |

### `update-recurring-template`

Atualiza frequency, status e/ou itens de uma template recorrente.

| | |
|---|---|
| **Entradas** | --template-id (obrigatório); --frequency; --template-status (active\|paused\|cancelled via --status? na verdade dest template_status); --items (JSON). |
| **Saídas** | template_id, updated_fields. |
| **Regras** | Template deve existir; valida frequency e template_status; se --items deleta e reinsere; erro se nada a atualizar. |
| **Efeitos colaterais** | UPDATE recurring_invoice_template; DELETE+INSERT recurring_invoice_template_item quando itens informados; audit_log; commit. |
| **Pré-condições** | Template existente. |

### `list-recurring-templates`

Lista templates de fatura recorrente com filtros e paginação.

| | |
|---|---|
| **Entradas** | --company-id; --customer-id; --template-status; --limit (default 20); --offset (default 0). |
| **Saídas** | recurring_templates (lista), total_count, limit, offset, has_more. |
| **Regras** | Filtros por AND; ordena por next_invoice_date. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `generate-recurring-invoices`

Cron: gera e auto-submete faturas das templates ativas vencidas até a data de referência.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --as-of-date (default hoje). |
| **Saídas** | invoices_generated (contagem), templates_processed, templates_completed, invoices (lista), errors (lista). |
| **Regras** | Seleciona templates status='active', next_invoice_date<=as_of_date e não expiradas; por template cria fatura draft, posta GL+PLE, gera naming, marca submitted; avança next_invoice_date conforme frequency; marca 'completed' se passar end_date; erros por template não abortam o lote (rollback isolado). |
| **Efeitos colaterais** | INSERT sales_invoice (status='submitted', update_stock=0) e sales_invoice_item; INSERT gl_entry (receita+imposto) e payment_ledger_entry; UPDATE recurring_invoice_template (last/next_invoice_date, possivelmente status='completed'); commit. Não grava audit_log. |
| **Pré-condições** | Empresa existente com templates ativos vencidos. |

## Blanket Orders

**Objetivo.** Criar, ativar, consultar, listar acordos-quadro (blanket orders) de venda e gerar pedidos com drawdown contra eles.

### `add-blanket-order`

Cria um blanket order de venda (acordo-quadro) no status 'draft'.

| | |
|---|---|
| **Entradas** | --customer-id (obrigatório); --items (obrigatório, JSON); --company-id (obrigatório); --valid-from (obrigatório); --valid-to (obrigatório). |
| **Saídas** | blanket_order_id, customer_id, total_qty, valid_from, valid_to. |
| **Regras** | Cliente deve estar 'active'; empresa deve existir; valid_to deve ser posterior a valid_from; cada item exige qty>0 e rate>0; blanket_order_type='selling'. |
| **Efeitos colaterais** | INSERT blanket_order (type='selling', status='draft') e blanket_order_item; UPDATE blanket_order.total_qty; audit_log; commit. |
| **Pré-condições** | Cliente ativo e empresa existentes. |

### `submit-blanket-order`

Ativa um blanket order de venda (draft -> active).

| | |
|---|---|
| **Entradas** | --blanket-order-id (obrigatório). |
| **Saídas** | blanket_order_id, doc_status ('active'). |
| **Regras** | Blanket order deve estar 'draft' e ser do tipo 'selling'. |
| **Efeitos colaterais** | UPDATE blanket_order (status='active'); audit_log; commit. |
| **Pré-condições** | Blanket order 'draft' do tipo selling. |

### `get-blanket-order`

Retorna um blanket order de venda com seus itens.

| | |
|---|---|
| **Entradas** | --blanket-order-id (obrigatório). |
| **Saídas** | Campos do blanket_order + items. |
| **Regras** | Blanket order deve existir. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Blanket order existente. |

### `list-blanket-orders`

Lista blanket orders de venda com filtros e paginação.

| | |
|---|---|
| **Entradas** | --company-id; --customer-id; --status; --limit (default 20); --offset (default 0). |
| **Saídas** | blanket_orders (lista), total_count, limit, offset, has_more. |
| **Regras** | Sempre filtra blanket_order_type='selling'; demais filtros por AND; ordena por created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `create-so-from-blanket`

Cria um pedido de venda (draft) fazendo drawdown de um blanket order ativo.

| | |
|---|---|
| **Entradas** | --blanket-order-id (obrigatório); --items (obrigatório, JSON); --posting-date (default hoje); --delivery-date; --tax-template-id. |
| **Saídas** | sales_order_id, blanket_order_id, total_amount, grand_total. |
| **Regras** | Blanket deve estar 'active', tipo 'selling' e não expirado; cada item deve estar no blanket e qty<=quantidade remanescente (quantity - ordered_qty); rate do item ou do blanket; SO criado em 'draft'. |
| **Efeitos colaterais** | INSERT sales_order (status='draft') e sales_order_item; UPDATE blanket_order_item.ordered_qty e blanket_order.ordered_qty; audit_log; commit. |
| **Pré-condições** | Blanket order ativo, não expirado, com saldo remanescente. |

## Faturamento Intercompany

**Objetivo.** Mapear contas entre empresas e espelhar/cancelar faturas intercompany (SI no vendedor -> PI no comprador).

### `add-intercompany-account-map`

Adiciona um mapeamento de conta da empresa origem para a conta da empresa destino.

| | |
|---|---|
| **Entradas** | --company-id (origem, obrigatório); --target-company-id (obrigatório); --source-account-id (obrigatório); --target-account-id (obrigatório). |
| **Saídas** | map_id. |
| **Regras** | Origem e destino devem ser empresas diferentes e existentes; cada conta deve pertencer à sua empresa; rejeita mapeamento duplicado para o par e conta de origem. |
| **Efeitos colaterais** | INSERT intercompany_account_map; commit. Não grava audit_log. |
| **Pré-condições** | Duas empresas distintas e suas contas existentes. |

### `list-intercompany-account-maps`

Lista mapeamentos de contas intercompany para um par de empresas.

| | |
|---|---|
| **Entradas** | --company-id (origem, obrigatório); --target-company-id. |
| **Saídas** | mappings (lista com nomes das contas origem/destino), total. |
| **Regras** | Origem obrigatória; filtra por destino se informado; junta com account para trazer nomes. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa de origem existente. |

### `create-intercompany-invoice`

Cria uma fatura de compra espelho (draft) na empresa destino a partir de uma fatura de venda.

| | |
|---|---|
| **Entradas** | --sales-invoice-id (obrigatório); --target-company-id (obrigatório); --supplier-id (obrigatório, fornecedor na empresa destino). |
| **Saídas** | purchase_invoice_id, sales_invoice_id, source_company_id, target_company_id, total_amount, grand_total, items_mirrored. |
| **Regras** | SI deve estar submitted/partially_paid/paid/overdue; origem != destino; SI não pode já ser intercompany; supplier deve pertencer à empresa destino; resolve conta de despesa via mapeamento (income origem -> expense destino) ou conta de despesa default. |
| **Efeitos colaterais** | INSERT purchase_invoice (is_intercompany=1, status='draft', intercompany_reference_id=SI) e purchase_invoice_item; UPDATE sales_invoice (is_intercompany=1, intercompany_reference_id=PI); commit. Não grava audit_log. |
| **Pré-condições** | SI submetida não-intercompany; empresa destino e supplier compatíveis existentes. |

### `list-intercompany-invoices`

Lista todas as faturas intercompany de uma empresa (como vendedora e compradora).

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --limit (default 20); --offset (default 0). |
| **Saídas** | invoices (SI com direction='sales' + PI com direction='purchase'), total. |
| **Regras** | Une sales_invoice is_intercompany=1 (como vendedor) e purchase_invoice is_intercompany=1 (como comprador); ordena por posting_date desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa existente. |

### `cancel-intercompany-invoice`

Cancela uma fatura de venda intercompany e cascateia o cancelamento para a fatura de compra espelho.

| | |
|---|---|
| **Entradas** | --sales-invoice-id (obrigatório). |
| **Saídas** | sales_invoice_id, purchase_invoice_id, si_status, si_gl_reversals, si_sle_reversals, pi_gl_reversals, pi_sle_reversals. |
| **Regras** | SI deve ser intercompany (is_intercompany=1); se SI submitted/overdue/partially_paid reverte GL/SLE e delinka PLE; PI espelho submetida é revertida de forma análoga, PI em draft é deletada; status já cancelado é no-op. |
| **Efeitos colaterais** | INSERT reversões em gl_entry e stock_ledger_entry (SI e PI); UPDATE payment_ledger_entry (delinked=1); UPDATE sales_invoice e purchase_invoice (status='cancelled', outstanding=0) OU DELETE purchase_invoice/itens se draft; commit. Não grava audit_log. |
| **Pré-condições** | SI intercompany existente com PI espelho referenciada. |

## Drop Ship/Romaneio

**Objetivo.** Gerar pedidos de compra por drop-ship a partir de itens do SO e gerir romaneios (packing slips) ligados a notas de entrega.

### `create-drop-ship-order`

Cria um pedido de compra (draft) a partir dos itens drop-ship de um pedido de venda.

| | |
|---|---|
| **Entradas** | --sales-order-id (obrigatório); --supplier-id (obrigatório); --posting-date (default hoje). |
| **Saídas** | purchase_order_id, sales_order_id, supplier_id, delivery_address, total_amount, item_count, message. |
| **Regras** | SO deve estar 'confirmed' ou 'partially_delivered'; supplier deve existir; usa só itens com is_drop_ship=1 e quantidade remanescente>0; PO usa delivery_address = endereço primário do cliente; PO criado em 'draft'. |
| **Efeitos colaterais** | INSERT purchase_order (status='draft', delivery_address) e purchase_order_item (vinculados aos itens do SO); audit_log; commit. |
| **Pré-condições** | SO confirmado/parcialmente entregue com itens drop-ship pendentes; supplier existente. |

### `add-packing-slip`

Cria um romaneio (packing slip) vinculado a uma nota de entrega.

| | |
|---|---|
| **Entradas** | --delivery-note-id (obrigatório); --items (obrigatório, JSON: [{delivery_note_item_id, qty_packed}]); --posting-date (default hoje); --notes/--reason. |
| **Saídas** | packing_slip_id, delivery_note_id, item_count, message. |
| **Regras** | DN deve existir; cada item deve referenciar um delivery_note_item da DN; qty_packed>0; soma de qty_packed (incluindo packings anteriores) não pode exceder a qty da linha da DN. |
| **Efeitos colaterais** | INSERT packing_slip e packing_slip_item; audit_log; commit. |
| **Pré-condições** | Nota de entrega existente com itens correspondentes. |

### `get-packing-slip`

Retorna um romaneio com seus itens.

| | |
|---|---|
| **Entradas** | --packing-slip-id (obrigatório). |
| **Saídas** | Campos do packing_slip + items (com item_code, item_name). |
| **Regras** | Packing slip deve existir. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Romaneio existente. |

### `list-packing-slips`

Lista romaneios com filtros opcionais.

| | |
|---|---|
| **Entradas** | --delivery-note-id; --company-id; --limit (default 20); --offset (default 0). |
| **Saídas** | packing_slips (lista), count. |
| **Regras** | Filtros opcionais; ordena por created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Status

**Objetivo.** Fornecer um resumo do domínio de vendas para uma empresa.

### `status`

Retorna um resumo de vendas (contagens por status e total em aberto) para uma empresa.

| | |
|---|---|
| **Entradas** | --company-id (opcional; se omitido usa a primeira empresa encontrada). |
| **Saídas** | customers (contagem), quotations (por status), sales_orders (por status), sales_invoices (por status), total_outstanding. |
| **Regras** | Se nenhuma empresa informada nem existente, erro; agrega contagens via group by status; total_outstanding soma faturas submitted/overdue/partially_paid com saldo>0. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Pelo menos uma empresa existente. |

