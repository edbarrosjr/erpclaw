# Estoque — `erpclaw-inventory`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-inventory/db_query.py`. 14 funcionalidades · 44 ações.

## Itens

**Objetivo.** Cadastrar e manter os itens do catálogo (produtos estocáveis, não estocáveis e serviços), incluindo importação em massa por CSV e resolução por nome solto. É a base para todas as movimentações de estoque, preços e compras/vendas.

**Ações:**
- `add-item` — Cria um novo item com código, nome, grupo, tipo, UOM, método de valoração, flags de lote/série e preço padrão.
- `update-item` — Atualiza nome, nível/qtd de reposição, preço padrão e status (active/disabled) de um item existente.
- `get-item` — Retorna o item com resumo de saldos de estoque por depósito e totais de qtd/valor.
- `list-items` — Lista/filtra itens por grupo, tipo, busca textual, empresa (via grupo) ou depósito com estoque, paginado.
- `resolve-item` — Resolve uma frase solta/plural do usuário em candidatos rankeados via cascata determinística de 4 tiers (somente leitura).
- `import-items` — Importa itens em massa de um CSV (item_code globalmente único), pulando duplicados.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-item: --item-code, --item-name (obrigatórios), --item-type (stock\|non_stock\|service), --valuation-method (moving_average\|fifo), --item-group, --stock-uom, --has-batch, --has-serial, --standard-rate, --custom-fields. update-item: --item-id + campos opcionais. get-item: --item-id. list-items: --item-group, --item-type, --search, --company-id, --warehouse-id, --limit/--offset. resolve-item: --name. import-items: --csv-path. |
| **Saídas** | add-item: item_id, item_code, item_name (+ custom fields). get-item: dados do item, stock_balances[] por depósito, total_qty, total_stock_value. list-items: items[], total_count, paginação. resolve-item: matched, single/multiple_match, match_type, candidates[]. import-items: imported, skipped, total_rows. |
| **Regras de negócio** | item_type deve estar em (stock\|non_stock\|service) e valuation_method em (moving_average\|fifo); is_stock_item=1 só para tipo stock. item_group é normalizado de nome para id e deve existir. standard_rate é arredondado para moeda. Item disabled não pode ser atualizado a menos que se reative (--status active). resolve-item é determinístico: 4 tiers (exato case-insensitive, singularizado, substring LIKE, token-AND) parando no primeiro com resultado. import-items: item_code é globalmente único, valuation_method default moving_average, duplicados são pulados. |
| **Efeitos colaterais** | Escrita na tabela item (insert/update). Grava custom fields (add-item). Grava trilha de auditoria (audit) em add-item/update-item. import-items insere itens mas NÃO grava auditoria por linha. resolve-item, get-item e list-items são somente leitura. Nenhuma postagem em GL ou SLE. |
| **Pré-condições** | Banco com tabela company existente. Para vincular grupo, o item_group deve existir. Para import-items, arquivo .csv válido e legível; grupos referenciados devem existir (senão item fica sem grupo). |

## Grupos de Itens

**Objetivo.** Organizar itens em uma hierarquia de grupos (item_group) opcionalmente por empresa e com grupo pai. Usado para classificação e filtros de itens e regras de preço.

**Ações:**
- `add-item-group` — Cria um grupo de itens com nome, empresa opcional e grupo pai opcional.
- `list-item-groups` — Lista grupos filtrando por empresa e/ou grupo pai, paginado.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-item-group: --name (obrigatório), --company-id, --parent-id. list-item-groups: --company-id, --parent-id, --limit/--offset. |
| **Saídas** | add-item-group: item_group_id, name. list-item-groups: item_groups[], total_count, limit, offset, has_more. |
| **Regras de negócio** | Nome é obrigatório. Se --parent-id informado, o grupo pai deve existir. Nome único (por empresa quando company_id presente) — violação de integridade retorna erro de duplicado. |
| **Efeitos colaterais** | Insert na tabela item_group e trilha de auditoria em add-item-group. list-item-groups é somente leitura. Nenhuma postagem em GL/SLE. |
| **Pré-condições** | Banco com tabela company. Grupo pai (se informado) deve existir. |

## Depósitos

**Objetivo.** Cadastrar e manter depósitos (warehouses) por empresa, com tipo, hierarquia (pai) e conta contábil de estoque vinculada. Depósitos são onde quantidades e valores de estoque residem.

**Ações:**
- `add-warehouse` — Cria um depósito com nome, empresa, tipo, pai opcional, conta contábil opcional e flag is_group.
- `update-warehouse` — Atualiza nome e/ou conta contábil de um depósito (resolvido por id ou nome).
- `list-warehouses` — Lista depósitos de uma empresa filtrando por pai e/ou tipo, paginado.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-warehouse: --warehouse-name/--name e --company-id (obrigatórios), --warehouse-type (stores\|production\|transit\|rejected), --parent-id, --account-id, --is-group. update-warehouse: --warehouse-id (id ou nome) + --name/--account-id. list-warehouses: --company-id/--company, --parent-id, --warehouse-type. |
| **Saídas** | add-warehouse: warehouse_id, name. update-warehouse: warehouse_id, updated_fields. list-warehouses: warehouses[], total_count, paginação. |
| **Regras de negócio** | warehouse_type deve estar em (stores\|production\|transit\|rejected), default stores. Empresa deve existir. Pai e conta (se informados) devem existir. update-warehouse resolve o alvo por id OU nome e normaliza para id; exige ao menos um campo a atualizar; valida account_id se informado. |
| **Efeitos colaterais** | Insert/update na tabela warehouse e trilha de auditoria em add-warehouse/update-warehouse. list-warehouses é somente leitura. Nenhuma postagem em GL/SLE. |
| **Pré-condições** | Empresa (--company-id) existente. account_id (se informado) deve referenciar conta existente — usado depois como conta de Estoque (Stock-in-Hand) nas postagens GL. |

## Movimentações

**Objetivo.** Registrar entradas de estoque (stock_entry) nos tipos recebimento, saída, transferência e fabricação, com ciclo de vida rascunho -> submetido -> cancelado. No submit, gera SLE e postagens GL; no cancel, reverte ambos.

**Ações:**
- `add-stock-entry` — Cria uma entrada de estoque em rascunho com itens, quantidades, depósitos origem/destino e taxas.
- `get-stock-entry` — Retorna a entrada de estoque com suas linhas de item.
- `list-stock-entries` — Lista entradas filtrando por empresa, tipo, status e intervalo de datas, paginado.
- `submit-stock-entry` — Submete um rascunho: posta SLE (razão de estoque) e GL de inventário perpétuo, muda status para submitted.
- `cancel-stock-entry` — Cancela uma entrada submetida: reverte SLE e GL e muda status para cancelled.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-stock-entry: --entry-type (receive\|issue\|transfer\|manufacture), --company-id, --posting-date, --items (JSON array com item_id, qty, rate, from/to_warehouse_id, batch_id, serial_numbers) — todos obrigatórios. submit/cancel/get-stock-entry: --stock-entry-id. list-stock-entries: --company-id, --entry-type, --status-filter, --from-date/--to-date. |
| **Saídas** | add-stock-entry: stock_entry_id, naming_series, total_incoming_value, total_outgoing_value, value_difference. submit: sle_entries_created, gl_entries_created. cancel: reversed, sle_reversals, gl_reversals. get: cabeçalho + items[]. |
| **Regras de negócio** | entry-type mapeado para material_receipt/issue/transfer/manufacture. Empresa deve existir; items array não vazio; cada item deve existir e qty>0; rate<=0 cai para standard_rate do item. Depósitos validados por tipo (receipt exige to; issue exige from; transfer exige ambos; manufacture exige from ou to), com fallback para default_warehouse_id da empresa. SLE: receipt +qty no destino (require_rate=True, não permite valorar a 0), issue -qty na origem, transfer -origem/+destino, manufacture +FG destino/-MP origem. Submit só de draft; cancel só de submitted. |
| **Efeitos colaterais** | add-stock-entry: insert em stock_entry (status draft) e stock_entry_item, mais auditoria. submit-stock-entry: insere stock_ledger_entry via insert_sle_entries, gera gl_entry via create_perpetual_inventory_gl/insert_gl_entries, muda status para submitted, auditoria. cancel-stock-entry: reverte SLE (reverse_sle_entries) e GL (reverse_gl_entries), muda status para cancelled, auditoria. get/list são somente leitura. |
| **Pré-condições** | Empresa existente; itens válidos; depósitos (per-item ou default da empresa) definidos. Para GL no submit: fiscal_year aberto cobrindo a posting_date, cost_center não-grupo da empresa e contas de estoque configuradas (caso contrário a postagem GL pode falhar/ser pulada). |

## Razão de Estoque (SLE)

**Objetivo.** Gateway transversal para outras skills (selling/buying) criarem e reverterem entradas no razão de estoque (stock_ledger_entry) para seus vouchers (ex.: Delivery Note, Purchase Receipt), canonizando o voucher_type.

**Ações:**
- `create-stock-ledger-entries` — Cria entradas SLE para um voucher externo (chamado por selling/buying), atribuindo fiscal_year.
- `reverse-stock-ledger-entries` — Reverte as entradas SLE de um voucher externo (ex.: cancelamento de nota).

| Campo | Detalhe |
|---|---|
| **Entradas** | create: --voucher-type, --voucher-id, --posting-date, --company-id, --entries (JSON array). reverse: --voucher-type, --voucher-id, --posting-date. |
| **Saídas** | create: sle_ids[], count. reverse: reversal_ids[], count. |
| **Regras de negócio** | voucher_type é canonicalizado para snake_case na fronteira (FINDING-006) para não quebrar filtros downstream. entries deve ser array não vazio. fiscal_year é derivado da posting_date e injetado em cada entrada. A lógica de valoração/saldo fica em insert_sle_entries/reverse_sle_entries da lib compartilhada. |
| **Efeitos colaterais** | create: insere linhas em stock_ledger_entry e grava auditoria. reverse: insere linhas de reversão em stock_ledger_entry e grava auditoria. NÃO posta GL diretamente (a skill chamadora cuida do GL). Sem mudança de status de documento próprio. |
| **Pré-condições** | Empresa existente; posting_date dentro de fiscal_year aberto (senão fiscal_year fica nulo). Voucher de origem (gerenciado por outra skill) já criado. |

## Saldos e Relatórios

**Objetivo.** Consultar saldos de estoque por item/depósito, relatórios de saldo por empresa, detalhamento do razão de estoque e um resumo geral do estoque da empresa. Tudo somente leitura.

**Ações:**
- `get-stock-balance` — Retorna qtd, taxa de valoração e valor de estoque de um item em um depósito.
- `stock-balance-report` — Resumo de saldos de todos os itens (com saldo != 0) de uma empresa, opcionalmente por depósito (alias: stock-balance).
- `stock-ledger-report` — Lista detalhada de entradas do razão de estoque (não canceladas) com filtros de item, depósito e datas.
- `status` — Resumo do estoque da empresa: contagem de itens, depósitos, entradas por status e valor total de estoque.

| Campo | Detalhe |
|---|---|
| **Entradas** | get-stock-balance: --item-id, --warehouse-id (obrigatórios). stock-balance-report: --company-id/--company, --warehouse-id. stock-ledger-report: --item-id, --warehouse-id, --from-date/--to-date, --limit/--offset. status: --company-id/--company. |
| **Saídas** | get-stock-balance: qty, valuation_rate, stock_value. stock-balance-report: report[] por item/depósito, total_stock_value, row_count. stock-ledger-report: entries[], count. status: items, warehouses, stock_entries{draft/submitted/cancelled/total}, total_stock_value. |
| **Regras de negócio** | Saldos consideram apenas SLE com is_cancelled=0. stock-balance-report agrega via decimal_sum e usa a valuation_rate do SLE mais recente (correlated subquery), filtrando saldos != 0. status soma stock_value_difference dos SLE não cancelados (joined a warehouse da empresa) para o valor total. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Empresa existente (relatórios por empresa). Item/depósito existentes para get-stock-balance. SLE já postados para haver saldos. |

## Lotes

**Objetivo.** Cadastrar lotes (batch) por item com datas de fabricação e validade, e listar lotes, inclusive filtrando por lotes que possuem saldo positivo em um depósito.

**Ações:**
- `add-batch` — Cria um lote vinculado a um item com datas opcionais de fabricação e validade.
- `list-batches` — Lista lotes por item; com --warehouse-id filtra apenas lotes com saldo > 0 naquele depósito.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-batch: --item-id, --batch-name (obrigatórios), --manufacturing-date, --expiry-date. list-batches: --item-id, --warehouse-id, --limit/--offset. |
| **Saídas** | add-batch: batch_id, batch_name. list-batches: batches[], total_count, paginação. |
| **Regras de negócio** | Item deve existir. batch_name é validado por integridade (duplicado retorna erro). list-batches com warehouse usa decimal_sum sobre SLE não cancelados e HAVING saldo > 0 para mostrar só lotes com estoque. |
| **Efeitos colaterais** | add-batch: insert na tabela batch e auditoria. list-batches é somente leitura. Nenhuma postagem GL/SLE. |
| **Pré-condições** | Item existente. O batch_id é então referenciável nas linhas de stock_entry e nos SLE. |

## Números de Série

**Objetivo.** Registrar números de série (serial_number) por item, com depósito, lote e status (active/delivered/returned/scrapped), e listá-los com filtros.

**Ações:**
- `add-serial-number` — Registra um número de série para um item, opcionalmente com depósito e lote, status inicial active.
- `list-serial-numbers` — Lista números de série filtrando por item, depósito e status, paginado.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-serial-number: --item-id, --serial-no (obrigatórios), --warehouse-id, --batch-id. list-serial-numbers: --item-id, --warehouse-id, --serial-status, --limit/--offset. |
| **Saídas** | add-serial-number: serial_number_id, serial_no. list-serial-numbers: serial_numbers[] (com item_code/name), total_count, paginação. |
| **Regras de negócio** | Item deve existir; serial_no validado por integridade (duplicado retorna erro); status inicial fixado em 'active'. Em list, --serial-status deve estar em (active\|delivered\|returned\|scrapped). |
| **Efeitos colaterais** | add-serial-number: insert na tabela serial_number e auditoria. list-serial-numbers é somente leitura. Nenhuma postagem GL/SLE; o status do serial não é alterado por essas ações (apenas registrado). |
| **Pré-condições** | Item existente. Depósito/lote (se informados) já cadastrados. |

## Preços e Regras

**Objetivo.** Gerenciar listas de preço, preços de item por lista (com faixas de quantidade e validade), consulta do preço aplicável e regras de precificação/desconto por item, grupo, cliente ou grupo de cliente.

**Ações:**
- `add-price-list` — Cria uma lista de preços com moeda e flags de compra/venda.
- `add-item-price` — Define o preço de um item em uma lista, com min_qty e validade opcionais.
- `get-item-price` — Retorna o preço aplicável de um item numa lista para uma quantidade/data, com fallback (somente leitura).
- `add-pricing-rule` — Cria uma regra de preço/desconto aplicável a item, grupo, cliente ou grupo de cliente.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-price-list: --name, --currency, --is-buying, --is-selling. add-item-price: --item-id, --price-list-id, --rate (obrigatórios), --min-qty, --valid-from/--valid-to. get-item-price: --item-id, --price-list-id, --qty. add-pricing-rule: --name, --applies-to (item\|item_group\|customer\|customer_group), --company-id (obrigatórios), --entity-id, --discount-percentage, --pricing-rule-rate, --min-qty/--max-qty, --valid-from/--valid-to, --priority. |
| **Saídas** | add-price-list: price_list_id, name. add-item-price: item_price_id, rate. get-item-price: linha do item_price aplicável. add-pricing-rule: pricing_rule_id, name. |
| **Regras de negócio** | currency default USD. add-item-price valida item e price_list e arredonda rate. get-item-price escolhe a faixa mais específica (min_qty <= qty, dentro da validade, ordenando min_qty DESC); se nada casar, faz fallback para o preço mais recente do item na lista; se nenhum, erro. add-pricing-rule: applies_to restrito ao enum; priority default 0. |
| **Efeitos colaterais** | Inserts em price_list, item_price e pricing_rule com auditoria (add-price-list, add-item-price, add-pricing-rule). get-item-price é somente leitura. Nenhuma postagem GL/SLE. |
| **Pré-condições** | Para add-item-price: item e price_list existentes. Para add-pricing-rule: empresa existente; entity_id deve referenciar a entidade do applies_to. |

## Reconciliação

**Objetivo.** Registrar uma reconciliação de estoque (contagem física) por depósito, calculando diferenças de quantidade e valor, com ciclo rascunho -> submetido; no submit posta SLE e GL apenas para as diferenças.

**Ações:**
- `add-stock-reconciliation` — Cria uma reconciliação em rascunho calculando diferenças entre saldo atual e contado por item/depósito.
- `submit-stock-reconciliation` — Submete a reconciliação: posta SLE das diferenças de qtd e GL de ajuste de valor, muda status para submitted.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-stock-reconciliation: --posting-date, --items (JSON array com item_id, warehouse_id, qty, valuation_rate), --company-id — todos obrigatórios. submit-stock-reconciliation: --stock-reconciliation-id. |
| **Saídas** | add: stock_reconciliation_id, naming_series, difference_amount, item_count. submit: sle_entries_created, gl_entries_created. |
| **Regras de negócio** | Empresa deve existir; cada linha exige item_id e warehouse_id. Calcula qty_diff = contado - atual e amount_diff = valor contado - valor atual (usando saldo/valoração corrente). No submit (só de draft), gera SLE apenas para linhas com qty_diff != 0 (incoming_rate = valoração se diferença positiva, senão 0) e GL de ajuste usando a conta account_type='stock_adjustment' da empresa como contra. |
| **Efeitos colaterais** | add-stock-reconciliation: insert em stock_reconciliation (draft) e stock_reconciliation_item, auditoria. submit-stock-reconciliation: insere stock_ledger_entry (insert_sle_entries) e gl_entry (create_perpetual_inventory_gl/insert_gl_entries) para as diferenças, muda status para submitted, auditoria. (Não há ação de cancelar reconciliação neste arquivo.) |
| **Pré-condições** | Empresa existente; itens/depósitos válidos com saldo conhecido. Para o GL: fiscal_year aberto, cost_center e conta de ajuste de estoque (stock_adjustment) configurada na empresa. |

## Revaloração

**Objetivo.** Revalorar o estoque de um item em um depósito alterando a taxa de valoração sem mexer na quantidade, em uma ação imediata (sem rascunho); registra SLE, GL de ajuste e um documento stock_revaluation. Permite listar, consultar e cancelar.

**Ações:**
- `revalue-stock` — Revalora um item/depósito para uma nova taxa, postando SLE (qty=0) e GL do ajuste; posta imediatamente como submitted.
- `list-stock-revaluations` — Lista revalorações de uma empresa, paginado.
- `get-stock-revaluation` — Retorna uma revaloração com suas entradas SLE e GL associadas.
- `cancel-stock-revaluation` — Cancela uma revaloração submetida revertendo SLE e GL e mudando status para cancelled.

| Campo | Detalhe |
|---|---|
| **Entradas** | revalue-stock: --item-id, --warehouse-id, --new-rate, --posting-date (obrigatórios), --reason. list-stock-revaluations: --company-id/--company, --limit/--offset. get/cancel-stock-revaluation: --revaluation-id. |
| **Saídas** | revalue-stock: revaluation_id, naming_series, old/new_rate, adjustment_amount, gl_entries_created. list: revaluations[], total_count. get: documento + sle_entries[] + gl_entries[]. cancel: cancelled=True. |
| **Regras de negócio** | new_rate deve ser não-negativo e diferente do atual; item deve ser stock item; depósito deve existir e fornece company_id; exige saldo (current_qty>0). ajuste = (qty*new_rate) - valor_atual. GL: se ajuste>0 DR Estoque/CR Stock Adjustment; se <0 inverso (usa conta do depósito ou account_type='stock'/'stock_adjustment' da empresa). cancel só de status submitted. |
| **Efeitos colaterais** | revalue-stock: insere stock_ledger_entry (actual_qty=0, registrando nova valoração e stock_value_difference), gl_entry de ajuste, e documento stock_revaluation (status submitted); auditoria. cancel-stock-revaluation: reverte SLE e GL, muda status para cancelled, auditoria. list/get são somente leitura. |
| **Pré-condições** | Item stock e depósito existentes com saldo > 0. Contas de estoque/ajuste configuradas e (para GL) fiscal_year aberto e cost_center da empresa. |

## Reposição/Projeção

**Objetivo.** Apoiar planejamento de compras: identificar itens com estoque no/abaixo do nível de reposição e calcular a quantidade projetada de um item em um depósito (saldo + pedidos de compra pendentes - reservas de venda). Somente leitura.

**Ações:**
- `check-reorder` — Lista itens ativos cujo estoque corrente (na empresa) está no ou abaixo do reorder_level, com shortfall e reorder_qty.
- `get-projected-qty` — Calcula projected_qty = actual_qty + ordered_qty (PO aberto) - reserved_qty (SO confirmado) para item/depósito.

| Campo | Detalhe |
|---|---|
| **Entradas** | check-reorder: --company-id/--company. get-projected-qty: --item-id, --warehouse-id (obrigatórios). |
| **Saídas** | check-reorder: items_below_reorder, items[] (current_stock, reorder_level, reorder_qty, shortfall). get-projected-qty: actual_qty, ordered_qty, reserved_qty, projected_qty. |
| **Regras de negócio** | check-reorder considera só itens com reorder_level definido (não nulo/vazio/'0') e status active; soma actual_qty de SLE não cancelados da empresa. get-projected-qty: ordered_qty = soma de (quantity - received_qty) de purchase_order_item de POs em status confirmed/partially_received; reserved_qty = soma de (quantity - delivered_qty) de sales_order_item de SOs confirmed/partially_delivered; pega linhas do depósito ou sem depósito (NULL). |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Empresa existente; itens com reorder_level configurado (check-reorder). Para get-projected-qty: item e depósito existentes; tabelas purchase_order(_item) e sales_order(_item) populadas pelas skills de compras/vendas. |

## Variantes

**Objetivo.** Gerenciar itens com variantes: definir atributos no item template (marcando-o como template), criar variantes individuais ou gerar todas as combinações (produto cartesiano) e listar as variantes existentes.

**Ações:**
- `add-item-attribute` — Adiciona um atributo (nome + valores JSON) ao item template e marca has_variants=1.
- `create-item-variant` — Cria uma variante a partir do template com valores específicos de atributos (JSON object).
- `generate-item-variants` — Gera todas as variantes possíveis (produto cartesiano dos atributos do template), pulando as já existentes.
- `list-item-variants` — Lista todas as variantes de um template com seus atributos.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-item-attribute: --item-id, --attribute-name, --attribute-values (JSON array). create-item-variant: --template-item-id, --attributes (JSON object). generate/list-item-variants: --template-item-id. |
| **Saídas** | add-item-attribute: attribute_id, values. create-item-variant: variant_id, item_code, item_name, attributes. generate-item-variants: created, skipped, skipped_codes, variants[]. list-item-variants: count, variants[] com atributos. |
| **Regras de negócio** | add-item-attribute exige item existente, não variante (variant_of nulo), valores array não vazio, nome de atributo único no item; marca o item como template (has_variants=1). create/generate exigem template com has_variants=1; valores de atributo devem constar na definição do template. Código da variante = item_code-Val1-Val2 e nome = nome (Val1-Val2); variantes duplicadas são puladas/rejeitadas. Variante herda grupo, tipo, UOM, valoração, flags e standard_rate do template e grava variant_of. |
| **Efeitos colaterais** | Insert em item_attribute e update em item (has_variants=1) em add-item-attribute; insert de novos itens (variantes) + item_attribute em create/generate. Auditoria em add-item-attribute e create-item-variant (generate NÃO grava auditoria). list é somente leitura. Nenhuma postagem GL/SLE. |
| **Pré-condições** | Item template existente. Para criar variantes: atributos definidos no template (add-item-attribute) com valores. |

## Fornecedores de Item

**Objetivo.** Vincular itens a fornecedores com quantidade mínima de pedido, prazo de entrega (lead time) e prioridade, apoiando reposição e compras; e listar esses vínculos por item ou por fornecedor.

**Ações:**
- `add-item-supplier` — Cria um vínculo item-fornecedor com min_order_qty, lead_time_days e priority.
- `list-item-suppliers` — Lista fornecedores de um item ou itens de um fornecedor (ordenados por prioridade).

| Campo | Detalhe |
|---|---|
| **Entradas** | add-item-supplier: --item-id, --supplier-id (obrigatórios), --min-order-qty, --lead-time-days, --priority. list-item-suppliers: --item-id e/ou --supplier-id (ao menos um obrigatório). |
| **Saídas** | add-item-supplier: item_supplier_id, item_id, supplier_id, min_order_qty, lead_time_days, priority. list-item-suppliers: count, item_suppliers[] (com item_code/name e supplier_name). |
| **Regras de negócio** | Item e fornecedor devem existir. min_order_qty arredondado (default 0); priority default 0. Vínculo item-fornecedor duplicado é rejeitado por integridade. list exige ao menos um filtro (--item-id ou --supplier-id). |
| **Efeitos colaterais** | Insert na tabela item_supplier e auditoria em add-item-supplier. list-item-suppliers é somente leitura. Nenhuma postagem GL/SLE. |
| **Pré-condições** | Item e fornecedor (tabela supplier, da skill de compras) já cadastrados. |

