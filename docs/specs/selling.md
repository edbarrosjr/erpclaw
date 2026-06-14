# Vendas (Order-to-Cash) — `erpclaw-selling`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-selling/db_query.py`. 14 funcionalidades · 60 ações.

## Clientes

**Objetivo.** Cadastrar e manter clientes (pessoa jurídica/física), seus termos de pagamento, limite e status de crédito, e consultar o saldo em aberto. Inclui importação em massa por CSV.

**Ações:**
- `add-customer` — Cria cliente com status 'active'; valida empresa e termos de pagamento; arredonda credit_limit.
- `update-customer` — Atualiza campos do cliente (nome, credit_limit, grupo, tipo, email, phone, termos); aceita id ou name.
- `get-customer` — Retorna o cliente mais o total em aberto (sales_invoice com status submitted/overdue/partially_paid e outstanding>0) e a contagem de faturas.
- `list-customers` — Lista paginada com filtros por empresa, grupo e busca textual (name/tax_id).
- `import-customers` — Importa clientes de CSV (colunas name, customer_type, territory, currency, email, phone); pula duplicados por (name, empresa); gera naming_series.

| Campo | Detalhe |
|---|---|
| **Entradas** | --name, --company-id, --customer-type (company\|individual), --customer-group, --payment-terms-id, --credit-limit, --tax-id, --exempt-from-sales-tax, --primary-address/contact, --email, --phone, --custom-fields; import: --csv-path; consultas: --customer-id, --search, --limit/--offset. |
| **Saídas** | customer_id e dados criados/atualizados; get inclui total_outstanding e outstanding_invoice_count; list inclui customers[], total_count, has_more; import retorna imported/skipped/total_rows. |
| **Regras de negócio** | customer_type deve ser company ou individual; valida existência de empresa e payment_terms; credit_limit arredondado a moeda. update aceita id OU name e exige ao menos um campo. import: exige .csv real, valida CSV e pula duplicado por (name, company_id). |
| **Efeitos colaterais** | INSERT/UPDATE em customer; campos custom via store_from_arg; registro de auditoria (audit) em add/update. import faz INSERT em lote. Nenhum lançamento GL/SLE/PLE. |
| **Pré-condições** | Empresa (company) deve existir; payment_terms_id, se informado, deve existir; tabelas company/account/item presentes (REQUIRED_TABLES). |

## Cotações

**Objetivo.** Criar e gerir cotações em rascunho, submetê-las (gerando naming series) e convertê-las em pedido de venda.

**Ações:**
- `add-quotation` — Cria cotação em 'draft' com itens, calcula total/imposto/grand_total; sem aplicar pricing rule.
- `update-quotation` — Atualiza cotação 'draft': valid_until e/ou substitui itens (delete+insert), recalcula totais.
- `get-quotation` — Retorna cabeçalho da cotação e seus itens com item_name.
- `list-quotations` — Lista paginada com filtros por empresa, cliente, status e intervalo de datas.
- `submit-quotation` — Transição draft->open; gera naming_series via get_next_name.
- `convert-quotation-to-so` — Cria sales_order 'draft' a partir da cotação (open ou draft); marca cotação como 'ordered' e grava converted_to.

| Campo | Detalhe |
|---|---|
| **Entradas** | --customer-id, --posting-date, --items (JSON), --company-id, --tax-template-id, --valid-till; consultas/transições: --quotation-id, --delivery-date (na conversão). |
| **Saídas** | quotation_id com total_amount/tax_amount/grand_total; submit retorna naming_series e status 'open'; convert retorna sales_order_id e status 'ordered'. |
| **Regras de negócio** | Ciclo: draft -> open (submit) -> ordered (convert). update só em 'draft'; submit só de 'draft'; convert só de 'open'/'draft'. Itens validados por _calculate_line_items (qty>0, item existe); imposto por template (on_net_total, actual, on_previous_row_total/amount, on_item_quantity, add/deduct). |
| **Efeitos colaterais** | INSERT/UPDATE/DELETE em quotation e quotation_item; convert cria sales_order + sales_order_item; auditoria em todas as ações. Nenhum GL/SLE/PLE. |
| **Pré-condições** | Cliente ativo e empresa existentes; itens cadastrados; tax_template_id (se usado) configurado. |

## Pedidos de Venda

**Objetivo.** Gerir o pedido de venda do rascunho à confirmação (com checagem de limite de crédito) e seu ciclo de vida (cancelar, fechar), incluindo acompanhamento de % entregue/faturado.

**Ações:**
- `add-sales-order` — Cria SO 'draft' com itens; aplica pricing rule (apply_pricing=True) e calcula totais/imposto.
- `update-sales-order` — Atualiza SO 'draft': delivery_date e/ou itens (recalcula com pricing).
- `get-sales-order` — Retorna SO com itens, notas de entrega não canceladas e faturas vinculadas.
- `list-sales-orders` — Lista paginada com filtros por empresa, cliente, status e datas; mostra per_delivered/per_invoiced.
- `submit-sales-order` — draft->confirmed; valida cliente ativo, itens com qty>0 e rate>0, e exposição de crédito vs credit_limit.
- `cancel-sales-order` — Cancela SO se não houver DN/fatura ativa vinculada.
- `close-sales-order` — Fecha SO parcialmente atendido (impede novos DN/faturas, preserva filhos); grava close_reason/closed_by.

| Campo | Detalhe |
|---|---|
| **Entradas** | --customer-id, --posting-date, --items, --company-id, --tax-template-id, --delivery-date; transições: --sales-order-id, --reason, --closed-by. |
| **Saídas** | sales_order_id com totais; submit retorna naming_series e status 'confirmed'; cancel/close retornam novo status. |
| **Regras de negócio** | Ciclo: draft -> confirmed (submit) -> partially/fully_delivered, partially/fully_invoiced -> closed/cancelled. submit checa limite: exposição = AR em aberto + SOs 'confirmed' (exceto este) + grand_total deste <= credit_limit (se >0). cancel só sem DN/fatura ativa; close bloqueado para draft/cancelled/closed. |
| **Efeitos colaterais** | INSERT/UPDATE/DELETE em sales_order e sales_order_item; submit/cancel/close apenas mudam status e geram auditoria. Nenhum GL/SLE/PLE (postagens ocorrem em DN e fatura). |
| **Pré-condições** | Cliente ativo e empresa; itens válidos; pricing_rule e tax_template opcionais. Para submit, credit_limit configurado se quiser bloqueio. |

## Emendas

**Objetivo.** Emendar um pedido de venda confirmado criando uma nova versão (linkada via amended_from) e cancelando a original, além de rastrear toda a cadeia de emendas.

**Ações:**
- `amend-sales-order` — Cancela o SO original (só sem DN/fatura ativos) e cria novo SO 'draft' com amended_from; itens vêm de --items ou são copiados do original.
- `get-amendment-history` — Reconstrói a cadeia de emendas (ancestrais via amended_from + descendentes) de um SO.

| Campo | Detalhe |
|---|---|
| **Entradas** | --sales-order-id; opcional --items (JSON com mudanças); get: --sales-order-id. |
| **Saídas** | new_sales_order_id, amended_from, original_status='cancelled' e novos totais; history retorna amendment_chain[] e chain_length. |
| **Regras de negócio** | Bloqueia emenda se SO está draft/cancelled/closed ou se houver qualquer DN ou fatura não cancelada vinculada. Novo SO recalcula com pricing rule e imposto; mantém customer/order_date/tax_template da original. |
| **Efeitos colaterais** | UPDATE no SO original (status='cancelled') + INSERT de novo sales_order/sales_order_item; dois registros de auditoria (cancelamento e criação). Nenhum GL/SLE/PLE. get é somente leitura. |
| **Pré-condições** | SO existente em status confirmado/parcial (não draft/cancelled/closed) e sem documentos filhos ativos. |

## Notas de Entrega

**Objetivo.** Emitir notas de entrega (totais ou parciais) a partir do pedido de venda e, na submissão, baixar estoque e lançar COGS; cancelar reverte os lançamentos.

**Ações:**
- `create-delivery-note` — Cria DN 'draft' do SO (confirmed/partially_delivered); entrega total (itens não entregues) ou parcial por --items, validando qty <= remanescente.
- `get-delivery-note` — Retorna DN com itens (item_name/item_code).
- `list-delivery-notes` — Lista paginada com filtros por empresa, cliente, status e datas.
- `submit-delivery-note` — draft->submitted; gera SLE de saída (qty negativa) e GL de COGS via inventário perpétuo; atualiza delivered_qty e status do SO.
- `cancel-delivery-note` — submitted->cancelled; reverte SLE e GL e devolve delivered_qty ao SO (se não houver fatura vinculada).

| Campo | Detalhe |
|---|---|
| **Entradas** | --sales-order-id, --posting-date, --items (parcial: item_id/sales_order_item_id, qty, warehouse_id, batch_id, serial_numbers), --warehouse-id (override); get/submit/cancel: --delivery-note-id. |
| **Saídas** | delivery_note_id, total_qty, item_count; submit retorna naming_series, sle_entries_created, gl_entries_created; cancel retorna contagem de reversões. |
| **Regras de negócio** | Ciclo: draft -> submitted -> cancelled. Itens de serviço são pulados no SLE. Exige warehouse (do item ou default da empresa) e o tipo deve ser 'stores' para despacho. Atualiza per_delivered do SO (fully/partially_delivered). cancel bloqueado se houver fatura ativa referenciando a DN. |
| **Efeitos colaterais** | submit: INSERT em stock_ledger_entry (saída), gl_entry de COGS (create_perpetual_inventory_gl), UPDATE serial_number para 'delivered', UPDATE delivered_qty/per_delivered/status do SO. cancel: reverse_sle_entries + reverse_gl_entries e devolução de delivered_qty (mínimo 0). Auditoria em ambas. |
| **Pré-condições** | SO confirmado/parcialmente entregue; armazém tipo 'stores' válido; ano fiscal aberto e cost center da empresa; conta COGS e conta de estoque configuradas. |

## Faturas de Venda

**Objetivo.** Criar faturas de venda (a partir de SO, DN ou avulsa), submetê-las gerando receita/AR/imposto no GL e PLE (e SLE/COGS opcional quando update_stock), e cancelá-las revertendo tudo.

**Ações:**
- `create-sales-invoice` — Cria fatura 'draft' do SO (itens não faturados), da DN (update_stock=0) ou avulsa; calcula imposto, due_date por payment_terms (ou +30 dias).
- `update-sales-invoice` — Atualiza fatura 'draft': due_date e/ou itens (recalcula totais e outstanding).
- `get-sales-invoice` — Retorna fatura com itens e payment_ledger_entry vinculados (sales_invoice e credit_note).
- `list-sales-invoices` — Lista paginada com filtros por empresa, cliente, status e datas; mostra outstanding e is_return.
- `submit-sales-invoice` — draft->submitted; gera GL (DR AR / CR Receita / CR Imposto), PLE, e SLE+COGS se update_stock; atualiza invoiced_qty/status do SO.
- `cancel-sales-invoice` — submitted/overdue/partially_paid -> cancelled; reverte GL, PLE (delinked) e SLE; zera outstanding e devolve invoiced_qty do SO.
- `update-invoice-outstanding` — Hook chamado por erpclaw-payments para abater pagamento via lib payment_clearing (rejeita over-payment).

| Campo | Detalhe |
|---|---|
| **Entradas** | --customer-id, --company-id, --items, --tax-template-id, --posting-date, --due-date, --sales-order-id, --delivery-note-id, --payment-terms-id; transições: --sales-invoice-id; pagamento: --amount. |
| **Saídas** | sales_invoice_id com totais, outstanding e update_stock; submit retorna naming_series, gl/sle_entries_created; update-outstanding retorna novo outstanding_amount e status. |
| **Regras de negócio** | Ciclo: draft -> submitted -> partially_paid/overdue/paid/cancelled. update_stock=1 por padrão (perpétuo US), 0 quando vem de DN ou SO já entregue. submit valida cliente ativo e aplica política de crédito (_enforce_credit_policy: bloqueia suspended/on_hold e excede credit_limit). Origem SO fatura só itens com remaining>0. update só em draft. cancel só de submitted/overdue/partially_paid. |
| **Efeitos colaterais** | submit: gl_entry (receita/AR/imposto, party=customer), payment_ledger_entry, e quando update_stock SLE de saída + gl_entry de COGS (entry_set='cogs'); UPDATE invoiced_qty/per_invoiced/status do SO. cancel: reverse_gl/sle, PLE delinked=1, status cancelled, devolução invoiced_qty. update-outstanding: UPDATE outstanding/status via lib. Auditoria em todas. |
| **Pré-condições** | Cliente ativo; contas de recebível, receita e imposto da empresa; ano fiscal aberto, cost center; conta COGS/estoque e armazém se update_stock; payment_terms para due_date. |

## Notas de Crédito/Estorno

**Objetivo.** Emitir notas de crédito (devolução) contra uma fatura submetida, gravadas como sales_invoice com is_return=1 e valores negativos, que revertem AR/receita ao serem submetidas.

**Ações:**
- `create-credit-note` — Cria nota de crédito 'draft' (is_return=1, return_against=fatura) com itens validados contra a fatura original e quantidades/valores negativos.
- `list-credit-notes` — Lista faturas com is_return=1, com nome da fatura original (return_against_name).

| Campo | Detalhe |
|---|---|
| **Entradas** | --against-invoice-id, --items (JSON: item_id, qty, rate opcional), --posting-date, --reason; list: --company-id, --customer-id, --status, datas. |
| **Saídas** | credit_note_id, against_invoice_id, grand_total (negativo) e is_return=true; list retorna credit_notes[] com totais. |
| **Regras de negócio** | Fatura original deve estar submitted/overdue/partially_paid/paid. Cada item deve existir na fatura original e qty de devolução <= qty original. Totais e imposto são negados. A submissão/cancelamento usa as MESMAS ações de fatura (submit/cancel-sales-invoice) com voucher_type 'credit_note' (DR/CR invertidos). |
| **Efeitos colaterais** | create: INSERT em sales_invoice (is_return=1) e sales_invoice_item com valores negativos; auditoria. Postagens reais (GL CR AR/DR Receita, PLE negativa, SLE de entrada/devolução) ocorrem no submit-sales-invoice. list é somente leitura. |
| **Pré-condições** | Fatura original existente e submetida (não draft/cancelled); itens correspondentes à fatura original; demais pré-condições de fatura para a submissão. |

## Crédito e Cobrança (Dunning)

**Objetivo.** Gerir política de crédito do cliente (limite, hold/suspend) e executar ciclos de cobrança escalonada (dunning) sobre faturas vencidas, com ações de email/hold/call/suspend.

**Ações:**
- `check-credit-limit` — Calcula crédito disponível: credit_limit - AR em aberto (faturas submitted, is_return=0); somente leitura.
- `place-customer-on-hold` — Define customer.credit_status (active|on_hold|suspended); grava auditoria com valor anterior.
- `add-dunning-level` — Configura nível de escalonamento (1-10): dias de atraso + ação (email|hold|call|suspend) + template.
- `run-dunning-cycle` — Acha faturas vencidas, casa cada cliente ao maior nível aplicável, aplica ação; para 'email' enfileira envio via erpclaw-alerts pós-commit. Idempotente por (cliente, nível, dia).
- `list-dunning-runs` — Lista histórico de dunning_run por cliente/empresa.

| Campo | Detalhe |
|---|---|
| **Entradas** | --customer-id, --credit-status, --reason; níveis: --company-id, --level, --days-overdue, --dunning-action, --template-id, --description; ciclo: --company-id, --run-date. |
| **Saídas** | check retorna credit_limit, outstanding_ar, available_credit, credit_status, limit_enforced; cycle retorna customers_processed, runs_created, actions{}, emails{sent,skipped}, run_ids. |
| **Regras de negócio** | credit_status: suspended/on_hold bloqueiam novas faturas (em submit-sales-invoice). Nível exige level 1-10, days_overdue>=0, ação válida. No ciclo, maior days_overdue<=days_late vence; pula se já existe run (cliente,nível) no dia; email sem template ou sem email do cliente é skip-with-note (não falha). |
| **Efeitos colaterais** | place-on-hold/run-cycle: UPDATE customer.credit_status (hold/suspend); add-level: INSERT dunning_level; run: INSERT dunning_run (status completed) e, pós-commit, subprocess para erpclaw-alerts send-email gravando generated_email_id. Auditoria em place/add. check/list somente leitura. Sem GL/SLE/PLE. |
| **Pré-condições** | Empresa existente; níveis de dunning configurados para o ciclo; faturas submetidas vencidas com outstanding>0; erpclaw-alerts instalado e template para envio de email. |

## Parceiros de Venda

**Objetivo.** Cadastrar parceiros de venda (representantes) com taxa de comissão, para uso/listagem no domínio de vendas.

**Ações:**
- `add-sales-partner` — Cria parceiro de venda com name e commission_rate (arredondada).
- `list-sales-partners` — Lista paginada de parceiros ordenada por nome.

| Campo | Detalhe |
|---|---|
| **Entradas** | --name, --commission-rate; list: --limit, --offset. |
| **Saídas** | sales_partner_id, name, commission_rate; list retorna sales_partners[], total_count, has_more. |
| **Regras de negócio** | name e commission_rate obrigatórios; commission_rate convertida para decimal e arredondada. Falha de integridade (duplicado) gera erro amigável. |
| **Efeitos colaterais** | INSERT em sales_partner; auditoria em add. list somente leitura. Nenhum GL/SLE/PLE; nenhum cálculo automático de comissão no código. |
| **Pré-condições** | Nenhuma além das tabelas base (não valida empresa). |

## Faturas Recorrentes

**Objetivo.** Definir templates de faturamento recorrente por cliente/frequência e gerar automaticamente (via cron) faturas submetidas nas datas devidas, avançando a próxima data.

**Ações:**
- `add-recurring-template` — Cria template 'draft' com cliente, frequência, start/end_date, itens e tax_template; next_invoice_date=start_date.
- `update-recurring-template` — Atualiza frequência, status (active|paused|cancelled) e/ou itens do template.
- `list-recurring-templates` — Lista templates por empresa/cliente/status ordenados por próxima data.
- `generate-recurring-invoices` — Cron: para templates 'active' com next_invoice_date<=as_of_date, cria e auto-submete a fatura, posta GL+PLE e avança datas.

| Campo | Detalhe |
|---|---|
| **Entradas** | --customer-id, --items, --frequency (weekly\|monthly\|quarterly\|semi_annually\|annually), --start-date, --end-date, --company-id, --tax-template-id, --payment-terms-id; update: --template-id, --template-status; gerar: --company-id, --as-of-date. |
| **Saídas** | template_id, frequency, next_invoice_date; generate retorna invoices_generated, templates_processed/completed, invoices[] e errors[]. |
| **Regras de negócio** | frequency restrita ao conjunto válido; template status active/paused/cancelled (só 'active' gera). generate só processa não-vencido por end_date; calcula due_date = data+30; avança next_invoice_date por _next_invoice_date (clamp de fim de mês) e marca 'completed' quando ultrapassa end_date. Erros por template são coletados sem abortar o lote (rollback parcial em falha de GL). |
| **Efeitos colaterais** | add/update: INSERT/UPDATE/DELETE em recurring_invoice_template(_item); auditoria. generate: cria sales_invoice+itens (status submitted, update_stock=0), gl_entry (AR/receita/imposto), payment_ledger_entry, gera naming e UPDATE de last/next_invoice_date e status do template. Sem SLE (update_stock=0). |
| **Pré-condições** | Cliente ativo e empresa; itens válidos; contas de recebível/receita configuradas para postagem na geração; ano fiscal e cost center para o GL. |

## Blanket Orders

**Objetivo.** Gerir acordos-quadro de venda (blanket order) com quantidades/valores acordados por período e gerar pedidos de venda que consomem (drawdown) o saldo do acordo.

**Ações:**
- `add-blanket-order` — Cria blanket order 'draft' (type 'selling') com validade e itens (qty>0, rate>0); calcula total_qty.
- `submit-blanket-order` — draft->active; valida tipo 'selling'.
- `get-blanket-order` — Retorna o acordo e seus itens.
- `list-blanket-orders` — Lista acordos do tipo 'selling' com filtros por empresa/cliente/status.
- `create-so-from-blanket` — Cria SO 'draft' consumindo o acordo 'active' (não expirado), validando qty<=remanescente; atualiza ordered_qty.

| Campo | Detalhe |
|---|---|
| **Entradas** | --customer-id, --items, --company-id, --valid-from, --valid-to; transições/uso: --blanket-order-id, --tax-template-id, --posting-date, --delivery-date. |
| **Saídas** | blanket_order_id, total_qty, validade; create-so retorna sales_order_id, total_amount, grand_total. |
| **Regras de negócio** | valid_to deve ser > valid_from; itens exigem qty>0 e rate>0. Ciclo: draft -> active (submit). create-so só de acordo 'active' e dentro da validade (valid_to>=hoje), com qty solicitada <= (quantity - ordered_qty) por item; recalcula ordered_qty total via decimal_sum. |
| **Efeitos colaterais** | INSERT/UPDATE em blanket_order(_item); create-so cria sales_order+itens e atualiza ordered_qty do item e do acordo. Auditoria em add/submit/create-so. Nenhum GL/SLE/PLE. |
| **Pré-condições** | Cliente ativo e empresa; itens válidos; acordo ativo e vigente para gerar SO. |

## Faturamento Intercompany

**Objetivo.** Espelhar uma fatura de venda de uma empresa como fatura de compra (mirror PI) em outra empresa do grupo, mapeando contas, e cancelar em cascata ambas.

**Ações:**
- `add-intercompany-account-map` — Mapeia conta da empresa origem para conta da empresa destino (valida pertencimento e duplicidade).
- `list-intercompany-account-maps` — Lista mapeamentos por par de empresas com nomes das contas.
- `create-intercompany-invoice` — Cria purchase_invoice 'draft' espelhando a SI submetida na empresa destino (supplier dado); marca a SI como is_intercompany.
- `list-intercompany-invoices` — Lista faturas intercompany (SI como vendedor + PI como comprador) da empresa.
- `cancel-intercompany-invoice` — Cancela a SI intercompany e cascateia para a PI espelho (reverte GL/SLE, delinka PLE; PI draft é apagada).

| Campo | Detalhe |
|---|---|
| **Entradas** | mapa: --company-id (origem), --target-company-id, --source-account-id, --target-account-id; espelho: --sales-invoice-id, --target-company-id, --supplier-id; cancel: --sales-invoice-id; list: --company-id. |
| **Saídas** | map_id; create retorna purchase_invoice_id, source/target_company_id, totais, items_mirrored; cancel retorna status e contagens de reversões de SI e PI. |
| **Regras de negócio** | Empresas origem/destino devem ser diferentes; contas devem pertencer às respectivas empresas; SI deve estar submetida e ainda não intercompany. Mirror copia datas/moeda/totais e mapeia conta de receita->despesa (ou default expense). Cancel exige SI is_intercompany; reverte SI e PI conforme status (PI 'draft' é deletada). |
| **Efeitos colaterais** | INSERT em intercompany_account_map; create: INSERT purchase_invoice(_item) na empresa destino + UPDATE sales_invoice (is_intercompany=1, intercompany_reference_id). cancel: reverse_gl_entries/reverse_sle_entries em SI e PI, payment_ledger_entry delinked=1, UPDATE status='cancelled' em ambas (ou DELETE da PI draft). Sem auditoria explícita nessas ações. |
| **Pré-condições** | Duas empresas distintas; supplier no destino representando a origem; SI submetida; contas (income/expense) e mapeamentos configurados. |

## Drop Ship/Romaneio

**Objetivo.** Gerar pedido de compra com envio direto (drop-ship) ao cliente a partir de itens marcados no SO, e emitir romaneios de embalagem (packing slip) vinculados à nota de entrega.

**Ações:**
- `create-drop-ship-order` — Cria purchase_order 'draft' para o supplier com delivery_address=endereço do cliente, a partir dos itens do SO com is_drop_ship=1 e remanescente>0; linka aos itens do SO.
- `add-packing-slip` — Cria packing_slip vinculado a uma DN, validando que qty_packed acumulada não exceda a qty do item da DN.
- `get-packing-slip` — Retorna o romaneio com seus itens (item_code/item_name).
- `list-packing-slips` — Lista romaneios por DN e/ou empresa.

| Campo | Detalhe |
|---|---|
| **Entradas** | drop-ship: --sales-order-id, --supplier-id, --posting-date; packing: --delivery-note-id, --items (delivery_note_item_id, qty_packed), --notes; get/list: --packing-slip-id, --delivery-note-id, --company-id. |
| **Saídas** | purchase_order_id com delivery_address, total_amount e item_count; packing retorna packing_slip_id e item_count. |
| **Regras de negócio** | drop-ship exige SO confirmed/partially_delivered e itens is_drop_ship=1 com remanescente (quantity-delivered_qty)>0; usa endereço primário do cliente. packing: qty_packed>0 e (qty_packed + já embalado) <= qty da DN por item. |
| **Efeitos colaterais** | create-drop-ship: INSERT em purchase_order/purchase_order_item (status draft) ligados aos itens do SO; auditoria. add-packing-slip: INSERT em packing_slip/packing_slip_item; auditoria. get/list somente leitura. Nenhum GL/SLE/PLE. |
| **Pré-condições** | SO confirmado com itens marcados is_drop_ship e supplier existente (drop-ship); DN existente com itens (packing); cliente com primary_address para o endereço de entrega. |

## Status

**Objetivo.** Fornecer um panorama consolidado do domínio de vendas para uma empresa: contagens por status e total a receber em aberto.

**Ações:**
- `status` — Resumo da empresa: nº de clientes, cotações/SOs/faturas agrupadas por status e total em aberto.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id (opcional; se ausente usa a primeira empresa encontrada). |
| **Saídas** | customers (contagem), quotations{}, sales_orders{}, sales_invoices{} por status e total_outstanding. |
| **Regras de negócio** | Se nenhuma empresa for informada, usa a primeira do banco; erro amigável se não houver empresa. total_outstanding soma faturas submitted/overdue/partially_paid com outstanding>0. |
| **Efeitos colaterais** | Nenhum (somente leitura) — apenas SELECTs agregados (Count/group by, decimal_sum). |
| **Pré-condições** | Ao menos uma empresa cadastrada; tabelas de cliente/cotação/SO/fatura existentes. |

