# Compras (Procure-to-Pay) — `erpclaw-buying`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-buying/db_query.py`. 12 funcionalidades · 48 ações.

## Fornecedores

**Objetivo.** Cadastrar e manter o registro mestre de fornecedores e consultar sua posição em aberto (contas a pagar). Suporta importação em massa via CSV.

**Ações:**
- `add-supplier` — Cria fornecedor em status 'active' (tipo company/individual, grupo, termos de pagamento, tax_id, flag 1099, endereço, e-mail, telefone, custom fields).
- `update-supplier` — Atualiza campos do fornecedor (nome, termos, grupo, tipo, e-mail, telefone); aceita id ou nome.
- `get-supplier` — Retorna o fornecedor com resumo de saldo em aberto somando outstanding_amount de purchase_invoice (status submitted/overdue/partially_paid).
- `list-suppliers` — Lista paginada com filtro por company, supplier_group e busca textual (nome/tax_id).
- `import-suppliers` — Importa fornecedores em massa de CSV (.csv); pula duplicados por nome+empresa; gera naming_series.

| Campo | Detalhe |
|---|---|
| **Entradas** | --name, --company-id, --supplier-type (company\|individual), --supplier-group, --payment-terms-id, --tax-id, --is-1099-vendor, --primary-address (JSON), --email, --phone, --custom-fields; para listar: --search, --limit, --offset; para importar: --csv-path. |
| **Saídas** | supplier_id e nome (criação); updated_fields (update); registro completo + total_outstanding e outstanding_invoice_count (get); lista + total_count/has_more; imported/skipped/total_rows (import). |
| **Regras de negócio** | supplier_type deve ser 'company' ou 'individual'; valida existência de company e payment_terms; status nasce 'active'. import-suppliers exige extensão .csv, valida o CSV e ignora linhas com nome já existente na empresa. |
| **Efeitos colaterais** | Grava em supplier e custom_field_value; registra auditoria (add/update-supplier, import). Nenhuma postagem em GL/SLE/PLE. get/list são somente leitura. |
| **Pré-condições** | Empresa (company) existente; payment_terms opcional deve existir se informado. Tabelas company, account, item presentes (REQUIRED_TABLES). |

## Requisições de Material

**Objetivo.** Registrar necessidades internas de itens (compra, transferência, fabricação ou baixa) em rascunho e submetê-las para iniciar o ciclo de suprimentos.

**Ações:**
- `add-material-request` — Cria requisição em 'draft' com itens (item_id, qty, warehouse_id); normaliza request_type 'transfer' para 'material_transfer'.
- `submit-material-request` — Submete a requisição (draft -> submitted) e atribui naming_series sequencial.
- `list-material-requests` — Lista paginada filtrando por company, request_type e status.

| Campo | Detalhe |
|---|---|
| **Entradas** | --request-type (purchase\|transfer\|manufacture, internamente também material_issue), --items (JSON: item_id, qty, warehouse_id), --company-id; para submeter: --material-request-id; para listar: --mr-status, --limit, --offset. |
| **Saídas** | material_request_id, request_type e item_count (criação); naming_series e status='submitted' (submit); lista paginada. |
| **Regras de negócio** | request_type obrigatório e validado; itens em array não vazio, qty > 0 por item; só submete se status='draft'; naming_series gerado por empresa no submit. |
| **Efeitos colaterais** | Grava em material_request e material_request_item; auditoria (add/submit-material-request). Nenhuma postagem em GL/SLE/PLE. list é somente leitura. |
| **Pré-condições** | Empresa existente; itens referenciam item_id (não há validação rígida de existência do item nesta ação). |

## Cotações e RFQ

**Objetivo.** Conduzir o processo de cotação: criar RFQ para múltiplos fornecedores, registrar as respostas (supplier quotations) e comparar preços/prazos lado a lado.

**Ações:**
- `add-rfq` — Cria RFQ em 'draft' com itens (item_id, qty, uom, required_date) e lista de fornecedores convidados; valida cada fornecedor.
- `submit-rfq` — Submete RFQ (draft -> submitted), gera naming_series e marca sent_date nos rfq_supplier.
- `list-rfqs` — Lista RFQs filtrando por company e status.
- `add-supplier-quotation` — Registra a resposta de um fornecedor a um RFQ: cria supplier_quotation + itens (rate/lead_time), calcula totais e marca response_date.
- `list-supplier-quotations` — Lista cotações de fornecedores filtrando por rfq_id e supplier_id.
- `compare-supplier-quotations` — Compara cotações por item do RFQ, identificando menor preço (lowest_rate/lowest_supplier) e marcando is_lowest.

| Campo | Detalhe |
|---|---|
| **Entradas** | --items (JSON), --suppliers (JSON de IDs), --company-id (add-rfq); --rfq-id (submit/quotation/compare); --supplier-id e --items com rfq_item_id+rate+lead_time_days (add-supplier-quotation). |
| **Saídas** | rfq_id, item_count, supplier_count; supplier_quotation_id e total_amount; lista de cotações; estrutura comparison com quotes por item, lowest_rate, lowest_supplier e supplier_count. |
| **Regras de negócio** | Itens e fornecedores em arrays não vazios; qty>0 e rate>0; só submete RFQ em 'draft'. Na cotação, qty vem do rfq_item e amount=qty*rate; ao registrar resposta marca rfq_supplier; quando TODOS os fornecedores respondem, RFQ passa a 'quotation_received'. |
| **Efeitos colaterais** | Grava request_for_quotation, rfq_item, rfq_supplier, supplier_quotation, supplier_quotation_item; atualiza status do RFQ e datas de envio/resposta; auditoria. Nenhuma postagem em GL/SLE/PLE. list/compare são somente leitura. |
| **Pré-condições** | Empresa existente; fornecedores cadastrados; para cotação, RFQ e rfq_item correspondentes devem existir. |

## Pedidos de Compra

**Objetivo.** Criar, confirmar e gerenciar o ciclo de vida de pedidos de compra (PO), incluindo cálculo de impostos, controle de quantidades recebidas/faturadas e encerramento.

**Ações:**
- `add-purchase-order` — Cria PO em 'draft' com itens (qty, rate, desconto%), calcula net_amount, imposto via template e grand_total.
- `update-purchase-order` — Substitui os itens de um PO em 'draft' (delete+reinsert) e recalcula totais.
- `get-purchase-order` — Retorna PO com itens e documentos vinculados (recebimentos e faturas).
- `list-purchase-orders` — Lista POs com filtros por company, supplier, status e intervalo de datas.
- `submit-purchase-order` — Confirma PO (draft -> confirmed), gera naming_series e emite avisos (não bloqueia) de qty abaixo do min_order_qty do item_supplier.
- `cancel-purchase-order` — Cancela PO somente se não houver recebimentos/faturas não-canceladas vinculadas.
- `close-purchase-order` — Encerra PO parcialmente recebido (status 'closed') com motivo/responsável, preservando filhos e impedindo novos recebimentos/faturas.

| Campo | Detalhe |
|---|---|
| **Entradas** | --supplier-id, --items (JSON: item_id, qty, rate, discount_percentage, uom, warehouse_id, required_date), --company-id, --tax-template-id, --posting-date; --purchase-order-id; --reason/--closed-by (close); filtros de lista. |
| **Saídas** | purchase_order_id, total_amount, tax_amount, grand_total; naming_series/status (submit); status='cancelled'/'closed'; warnings de min_order_qty; PO completo com items/receipts/invoices (get). |
| **Regras de negócio** | supplier deve estar 'active'; qty>0 e rate>0; net_amount=amount*(1-desc/100); imposto por tax_template_line (on_net_total/on_previous_row_total/actual, add/deduct). Ciclo: draft -> confirmed -> (partially_received/fully_received, partially_invoiced/fully_invoiced) -> closed/cancelled. update/cancel só em estados permitidos. per_received/per_invoiced atualizados pelos GRN/faturas. |
| **Efeitos colaterais** | Grava em purchase_order/purchase_order_item; submit/cancel/close apenas mudam status e naming; auditoria em todas. Nenhuma postagem direta em GL/SLE/PLE (a contabilização ocorre no GRN e na fatura). get/list são somente leitura. |
| **Pré-condições** | Fornecedor ativo e empresa existentes; tax_template opcional; item_supplier necessário para avisos de min_order_qty. |

## Recebimentos (GRN)

**Objetivo.** Registrar a entrada física de mercadorias (Goods Receipt Note) a partir de um PO, total ou parcial, e contabilizar o estoque ao submeter.

**Ações:**
- `create-purchase-receipt` — Cria GRN em 'draft' a partir do PO (full = itens não recebidos; partial = via --items com purchase_order_item_id), aplicando tolerância de recebimento.
- `get-purchase-receipt` — Retorna o GRN com seus itens (com item_code/item_name).
- `list-purchase-receipts` — Lista GRNs filtrando por company, supplier e status.
- `submit-purchase-receipt` — Submete o GRN: cria SLE positivo no depósito e GL de inventário perpétuo; atualiza received_qty e status do PO.
- `cancel-purchase-receipt` — Cancela GRN submetido: reverte SLE e GL, reduz received_qty e reajusta status do PO.

| Campo | Detalhe |
|---|---|
| **Entradas** | --purchase-order-id, --posting-date, --items (JSON: purchase_order_item_id, qty, warehouse_id, batch_id, serial_numbers); --purchase-receipt-id (get/submit/cancel); filtros de lista. |
| **Saídas** | purchase_receipt_id, total_qty, item_count; sle_entries_created/gl_entries_created e naming_series/status (submit); sle_reversals/gl_reversals (cancel). |
| **Regras de negócio** | PO deve estar 'confirmed' ou 'partially_received' (não 'closed'); qty recebida limitada ao remanescente + receipt_tolerance_pct da empresa; só submete 'draft', só cancela 'submitted'. SLE exige rate positivo (require_rate=True, nunca custo $0). per_received recalcula status do PO (partially/fully_received). |
| **Efeitos colaterais** | submit: insere stock_ledger_entry (entrada positiva) e gl_entry perpétuo (DR Estoque / CR Stock Received Not Billed); atualiza purchase_order_item.received_qty e status do PO; auditoria. cancel: reverte SLE e GL, reduz received_qty e pode voltar PO para 'confirmed'. create/get/list não postam. |
| **Pré-condições** | PO confirmado; depósito por item ou default_warehouse_id da empresa; fiscal_year aberto e cost_center existentes para o GL; contas de estoque/SRNB configuradas. |

## Faturas de Compra

**Objetivo.** Registrar e contabilizar faturas de fornecedor (AP), com origem em PO, GRN ou avulsa, gerando GL (despesa/SRNB/imposto/AP), PLE e, se aplicável, movimentação de estoque.

**Ações:**
- `create-purchase-invoice` — Cria fatura em 'draft' a partir de PO (qty remanescente), de GRN ou avulsa; define update_stock e suporta capitalização CWIP (--cwip-asset-id).
- `update-purchase-invoice` — Atualiza due_date e/ou itens de fatura em 'draft', recalculando totais e imposto.
- `get-purchase-invoice` — Retorna a fatura com itens e payment_ledger_entry vinculados.
- `list-purchase-invoices` — Lista faturas filtrando por company, supplier, status e datas.
- `submit-purchase-invoice` — Submete a fatura: valida 3-way match, posta GL (despesa ou SRNB se GRN-linked, imposto de entrada, AP), cria PLE; se update_stock posta SLE + GL de estoque; trata CWIP.
- `cancel-purchase-invoice` — Cancela fatura submetida/overdue/partially_paid: reverte GL (incl. COGS), PLE (delinked), SLE e acumulações CWIP; reajusta invoiced_qty do PO.
- `update-invoice-outstanding` — Cross-skill (chamada por payments): aplica pagamento e reduz outstanding via payment_clearing (rejeita over-payment).

| Campo | Detalhe |
|---|---|
| **Entradas** | --supplier-id/--company-id/--items (avulsa), --purchase-order-id ou --purchase-receipt-id (origem), --posting-date, --due-date, --tax-template-id, --cwip-asset-id; --purchase-invoice-id (update/get/submit/cancel); --amount (outstanding). |
| **Saídas** | purchase_invoice_id, total/tax/grand_total, update_stock; naming_series/status e contagens gl_entries_created/sle_entries_created (submit); gl_reversals/sle_reversals (cancel); outstanding_amount/status (outstanding). |
| **Regras de negócio** | update_stock=1 por padrão (estoque perpétuo US); =0 quando há GRN vinculado ou CWIP. 3-way match (strict/tolerant/disabled) compara qty faturada acumulada vs recebida quando há PO. CWIP não combina com PO/GRN, não pode ser return, e capitaliza valor pré-imposto. Só submete 'draft'; só cancela submitted/overdue/partially_paid. invoiced_qty e status do PO atualizados (partially/fully_invoiced). |
| **Efeitos colaterais** | submit: insere gl_entry (DR despesa/SRNB/estoque + imposto de entrada / CR AP/payable por party=supplier), payment_ledger_entry (against o próprio invoice), e quando update_stock SLE + GL de COGS (entry_set='cogs'); registra acumulação CWIP. cancel: reverte GL/SLE, marca PLE delinked, reverte CWIP e invoiced_qty. update-invoice-outstanding altera outstanding/status. get/list somente leitura. |
| **Pré-condições** | Fornecedor e empresa existentes; contas payable/expense/SRNB/stock e imposto configuradas; fiscal_year aberto; para CWIP, asset 'under_construction' e conta CWIP resolvível. |

## Notas de Débito

**Objetivo.** Emitir devolução/ajuste a fornecedor (debit note) contra uma fatura de compra existente, reduzindo o passivo de contas a pagar.

**Ações:**
- `create-debit-note` — Cria a nota de débito como purchase_invoice com is_return=1 e quantidades/valores negativos, vinculada à fatura original (return_against).

| Campo | Detalhe |
|---|---|
| **Entradas** | --against-invoice-id, --items (JSON: item_id, qty, rate — rate herda da fatura original se omitido), --posting-date, --reason. |
| **Saídas** | debit_note_id, against_invoice_id e total_amount (negativo). |
| **Regras de negócio** | Fatura original deve estar submitted/partially_paid/paid/overdue; qty>0 por item (armazenada negativa); rate>0 (busca da fatura original quando não informada); herda supplier/update_stock/company da original; nasce em 'draft'. |
| **Efeitos colaterais** | Grava purchase_invoice (is_return=1) + purchase_invoice_item negativos; auditoria (create-debit-note). A contabilização efetiva (GL reverso despesa/SRNB, imposto e DR AP, e PLE negativo) ocorre ao chamar submit-purchase-invoice sobre esse documento (voucher_type='debit_note'). |
| **Pré-condições** | Fatura de compra original existente em status válido; itens com referência a item da fatura para herdar rate. |

## Custos de Importação

**Objetivo.** Distribuir custos adicionais (frete, seguro, taxas) sobre itens de recebimentos para compor o custo final (landed cost) e contabilizar a capitalização no estoque.

**Ações:**
- `add-landed-cost-voucher` — Cria o voucher já 'submitted', rateia cada encargo entre os itens dos GRNs por quantidade ou valor, calcula final_rate e posta GL.

| Campo | Detalhe |
|---|---|
| **Entradas** | --purchase-receipt-ids (JSON de GRNs submetidos), --charges (JSON: description, amount, allocation_method qty\|value, expense_account_id), --company-id. |
| **Saídas** | landed_cost_voucher_id, total_landed_cost e gl_entries_created. |
| **Regras de negócio** | GRNs devem estar 'submitted' e conter itens; amount de cada charge>0; rateio por qty ou value com ajuste do resíduo no último item; final_rate=original_rate + encargo/qty; voucher criado diretamente como 'submitted' (sem etapa de rascunho). |
| **Efeitos colaterais** | Grava landed_cost_voucher, landed_cost_charge e landed_cost_item; posta gl_entry por encargo (DR conta de Estoque / CR conta de despesa informada) quando expense_account_id presente; auditoria. (Não reescreve SLE existentes; registra apenas final_rate nos landed_cost_item.) |
| **Pré-condições** | Empresa existente; GRNs submetidos com itens; conta de estoque e conta de despesa do encargo configuradas; fiscal_year/cost_center para o GL. |

## Blanket PO (Pedido Guarda-Chuva)

**Objetivo.** Gerenciar acordos-quadro de compra com fornecedor (quantidade e preço acordados por período) dos quais se faz drawdown via POs.

**Ações:**
- `add-blanket-po` — Cria blanket order tipo 'buying' em 'draft' com itens (qty, rate) e janela de validade (valid_from/valid_to).
- `submit-blanket-po` — Ativa o acordo (draft -> active).
- `get-blanket-po` — Retorna o blanket order com seus itens.
- `list-blanket-pos` — Lista blanket orders de compra filtrando por company, supplier e status.

| Campo | Detalhe |
|---|---|
| **Entradas** | --supplier-id, --items (JSON: item_id, qty, rate, uom), --company-id, --valid-from, --valid-to; --blanket-order-id (submit/get); filtros de lista. |
| **Saídas** | blanket_order_id, supplier_id, total_qty, valid_from/valid_to; doc_status='active' (submit); registro + itens (get); lista paginada. |
| **Regras de negócio** | supplier 'active'; valid_to deve ser posterior a valid_from; qty>0 e rate>0; tipo fixo 'buying'; só ativa se 'draft'. ordered_qty acompanha o consumo do acordo. |
| **Efeitos colaterais** | Grava blanket_order e blanket_order_item; submit muda status para 'active'; auditoria. Nenhuma postagem em GL/SLE/PLE. get/list somente leitura. |
| **Pré-condições** | Fornecedor ativo e empresa existentes. |

## Conversão para PO

**Objetivo.** Gerar pedidos de compra automaticamente a partir de um blanket order (drawdown) ou de um pedido de venda (back-to-back SO -> PO por fornecedor).

**Ações:**
- `create-po-from-blanket` — Cria PO em 'draft' consumindo itens de um blanket ativo, respeitando a qty remanescente e herdando o rate acordado; atualiza ordered_qty do acordo.
- `create-po-from-so` — Cria um PO por fornecedor a partir dos itens de um sales order, resolvendo o fornecedor padrão de cada item via item_supplier (menor priority).

| Campo | Detalhe |
|---|---|
| **Entradas** | --blanket-order-id, --items (JSON: item_id, qty, rate?, warehouse_id), --posting-date, --tax-template-id (blanket); --sales-order-id, --posting-date, --tax-template-id (SO). |
| **Saídas** | purchase_order_id, blanket_order_id, total_amount, grand_total; ou sales_order_id, purchase_orders_created, lista de POs e items_without_supplier. |
| **Regras de negócio** | Blanket deve estar 'active', tipo 'buying' e não expirado; qty solicitada <= remanescente (quantity-ordered_qty); rate herda do acordo se omitido. SO deve estar 'draft'/'confirmed'; agrupa itens por fornecedor; ignora fornecedores não-ativos; reporta itens sem fornecedor configurado. POs criados em 'draft'. |
| **Efeitos colaterais** | Grava purchase_order/purchase_order_item; no blanket atualiza ordered_qty (item e total); auditoria (create-po-from-blanket / create-po-from-so). Nenhuma postagem em GL/SLE/PLE (POs nascem em draft). |
| **Pré-condições** | Blanket ativo dentro da validade; ou sales_order com itens e mapeamentos item_supplier para resolver fornecedores; fornecedores ativos. |

## Contas Recorrentes

**Objetivo.** Definir templates de faturas de compra recorrentes (aluguéis, assinaturas) e gerar automaticamente as faturas devidas conforme a frequência, com opção de auto-submissão contábil.

**Ações:**
- `add-recurring-bill-template` — Cria template em 'draft' com itens, frequência, start/end_date e flag auto_submit; next_bill_date inicia em start_date.
- `list-recurring-bill-templates` — Lista templates ordenados por next_bill_date, filtrando por company, supplier e status.
- `generate-recurring-bills` — Cron: gera purchase_invoice dos templates 'active' com next_bill_date<=as_of_date, avança datas e completa o template ao passar do end_date.

| Campo | Detalhe |
|---|---|
| **Entradas** | --supplier-id, --items (JSON), --frequency (weekly\|monthly\|quarterly\|semi_annually\|annually), --start-date, --end-date, --tax-template-id, --auto-submit, --company-id; --as-of-date (geração); filtros de lista. |
| **Saídas** | template_id, frequency, start_date, next_bill_date; lista de templates; bills_generated, templates_processed/completed, lista de bills e errors. |
| **Regras de negócio** | frequency validada; supplier 'active'; template nasce 'draft'; geração só processa status 'active' e dentro de end_date; due_date = posting + 30 dias; next_bill_date avança por frequência (clamp ao último dia do mês); template vira 'completed' quando próximo vencimento ultrapassa end_date. Erros por template são coletados sem abortar o lote. |
| **Efeitos colaterais** | add: grava recurring_bill_template/_item. generate: cria purchase_invoice/_item por template; se auto_submit, gera naming e posta gl_entry (DR despesa / CR AP por party=supplier) e marca 'submitted'; atualiza last_bill_date/next_bill_date e status do template; auditoria. list somente leitura. |
| **Pré-condições** | Fornecedor ativo e empresa existentes; para auto_submit, contas payable e expense da empresa configuradas e fiscal_year aberto. |

## Políticas de Compra

**Objetivo.** Configurar parâmetros de governança de compras por empresa (tolerância de recebimento e política de 3-way match) e definir UOM de compra de itens; expõe também um resumo geral.

**Ações:**
- `update-receipt-tolerance` — Define receipt_tolerance_pct da empresa (0-100), usado em GRN e no 3-way match tolerante.
- `update-three-way-match-policy` — Define a política three_way_match_policy da empresa: strict | tolerant | disabled.
- `set-item-purchase-uom` — Cria/atualiza um uom_conversion (purchase UOM -> stock UOM) com conversion_factor para um item.
- `status` — Resumo de compras da empresa: contagem de fornecedores, POs e faturas por status e total em aberto.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id e --tolerance-pct (tolerância); --company-id e --policy (match); --item-id, --purchase-uom, --conversion-factor (UOM); --company-id opcional (status, usa a primeira empresa se omitido). |
| **Saídas** | company_id + receipt_tolerance_pct; company_id + three_way_match_policy; uom_conversion_id/conversion_factor/action; resumo com suppliers, purchase_orders, purchase_invoices e total_outstanding. |
| **Regras de negócio** | tolerance_pct entre 0 e 100; policy restrita a strict/tolerant/disabled; conversion_factor>0; valida existência de company/item. A política e a tolerância são consumidas em create-purchase-receipt e em submit-purchase-invoice (3-way match). |
| **Efeitos colaterais** | update-receipt-tolerance e update-three-way-match-policy alteram colunas na tabela company; set-item-purchase-uom grava/atualiza uom_conversion; todas auditadas. status é somente leitura. Nenhuma postagem em GL/SLE/PLE. |
| **Pré-condições** | Empresa existente (e item existente para UOM). |

