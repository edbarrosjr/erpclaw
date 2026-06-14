# Estoque — `erpclaw-inventory`

> Spec funcional por ação. Gerada de `scripts/erpclaw-inventory/db_query.py`. 14 funcionalidades · 44 ações.

## Itens

**Objetivo.** CRUD e resolução de itens (catálogo de produtos) e seus saldos consolidados.

### `add-item`

Cria um novo item no catálogo.

| | |
|---|---|
| **Entradas** | --item-code (obrigatório); --item-name (obrigatório); --item-type (default 'stock', valores stock\|non_stock\|service); --valuation-method (default 'moving_average', valores moving_average\|fifo); --item-group (id ou nome); --stock-uom (default 'Nos'); --has-batch (default 0); --has-serial (default 0); --standard-rate (default 0); --custom-fields (JSON). |
| **Saídas** | item_id, item_code, item_name e campos custom mesclados via merge_into_response. |
| **Regras** | Valida item_type e valuation_method contra listas; se --item-group informado resolve id por id/nome ou erra; is_stock_item=1 só para type 'stock'; arredonda standard_rate; IntegrityError vira erro de duplicidade. Erro de custom field faz rollback. |
| **Efeitos colaterais** | INSERT em item (status='active'); grava custom fields (store_from_arg); audit_log via audit('add-item'); commit. |
| **Pré-condições** | Tabela company existe (REQUIRED_TABLES); item_group referenciado deve existir se informado. |

### `update-item`

Atualiza campos editáveis de um item existente.

| | |
|---|---|
| **Entradas** | --item-id (obrigatório); campos opcionais: --item-name, --reorder-level, --reorder-qty, --standard-rate, --status (active\|disabled). |
| **Saídas** | item_id, updated_fields (lista dos campos alterados). |
| **Regras** | Erra se item não existe; bloqueia update de item 'disabled' a menos que --status=active; valida status em (active,disabled); erra se nenhum campo a atualizar; arredonda standard_rate; seta updated_at. |
| **Efeitos colaterais** | UPDATE dinâmico em item; audit_log via audit('update-item'); commit. |
| **Pré-condições** | Item deve existir. |

### `get-item`

Retorna o item com resumo de estoque por depósito e totais.

| | |
|---|---|
| **Entradas** | --item-id (obrigatório). |
| **Saídas** | Campos do item + stock_balances (por warehouse: id, name, qty, valuation_rate, stock_value) + total_qty + total_stock_value + custom fields. |
| **Regras** | Erra se item não existe; agrega saldos dos warehouses distintos com SLE não cancelado via get_stock_balance, incluindo só linhas com qty ou valor != 0. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Item deve existir. |

### `list-items`

Lista itens com filtros e paginação.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --warehouse-id (itens com estoque no depósito), --company-id (via item_group.company_id), --item-group, --item-type, --search (item_name/item_code LIKE); --limit (default 20); --offset (default 0). |
| **Saídas** | items[], total_count, limit, offset, has_more. |
| **Regras** | Conta total e retorna página ordenada por item_name; filtro de warehouse usa subquery de SLE não cancelado. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma além de tabelas base. |

### `resolve-item`

Resolve uma frase livre/plural do usuário em candidatos de item ranqueados.

| | |
|---|---|
| **Entradas** | --name (obrigatório, dest=name). |
| **Saídas** | query, matched, single_match, multiple_matches, match_type (exact\|singular\|substring\|tokens\|null), candidates[]. |
| **Regras** | Cascata determinística de 4 tiers (exato, singularizado, substring LIKE, token-AND), para no primeiro tier com >=1 resultado; comparação case-insensitive via fn.Lower; limite 10 candidatos. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `import-items`

Importa itens em massa a partir de um arquivo CSV.

| | |
|---|---|
| **Entradas** | --csv-path (obrigatório). |
| **Saídas** | imported, skipped, total_rows. |
| **Regras** | Path precisa ser .csv e arquivo regular; valida CSV via validate_csv e parseia via parse_csv_rows; pula item_code duplicado (globalmente único); resolve group por nome se existir; uom default 'Nos', valuation_method default 'moving_average'. |
| **Efeitos colaterais** | INSERT em item (status='active') por linha nova; commit. NÃO grava audit_log. |
| **Pré-condições** | Arquivo CSV válido existente no caminho informado. |

## Grupos de Itens

**Objetivo.** Criação e listagem de grupos de itens (hierarquia de categorização).

### `add-item-group`

Cria um grupo de itens, opcionalmente sob um grupo pai.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --parent-id (opcional); --company-id (opcional). |
| **Saídas** | item_group_id, name. |
| **Regras** | Erra se --parent-id informado e pai não existe; IntegrityError vira erro 'já existe' (por nome/empresa). |
| **Efeitos colaterais** | INSERT em item_group; audit_log via audit('add-item-group'); commit. |
| **Pré-condições** | Grupo pai deve existir se informado. |

### `list-item-groups`

Lista grupos de itens com filtros e paginação.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --company-id, --parent-id; --limit (default 20); --offset (default 0). |
| **Saídas** | item_groups[], total_count, limit, offset, has_more. |
| **Regras** | Conta e pagina ordenando por name. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Depósitos

**Objetivo.** Cadastro, atualização e listagem de depósitos (warehouses) por empresa.

### `add-warehouse`

Cria um depósito vinculado a uma empresa.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --company-id (obrigatório); --warehouse-type (default 'stores', valores stores\|production\|transit\|rejected); --parent-id (opcional); --account-id (opcional); --is-group (default 0). |
| **Saídas** | warehouse_id, name. |
| **Regras** | Erra se company, parent_id ou account_id informados não existem; valida warehouse_type contra lista. |
| **Efeitos colaterais** | INSERT em warehouse; audit_log via audit('add-warehouse'); commit. |
| **Pré-condições** | Empresa existe; conta/depósito pai existem se informados. |

### `update-warehouse`

Atualiza nome e/ou conta contábil de um depósito.

| | |
|---|---|
| **Entradas** | --warehouse-id (obrigatório, aceita id ou nome); --name e/ou --account-id (opcionais). |
| **Saídas** | warehouse_id, updated_fields. |
| **Regras** | Resolve depósito por id ou nome ou erra; valida account_id existente; erra se nenhum campo a atualizar; seta updated_at. |
| **Efeitos colaterais** | UPDATE dinâmico em warehouse; audit_log via audit('update-warehouse'); commit. |
| **Pré-condições** | Depósito existe; conta existe se account_id informado. |

### `list-warehouses`

Lista depósitos de uma empresa com filtros e paginação.

| | |
|---|---|
| **Entradas** | --company-id ou --company (nome) (um requerido via resolve_company_id); filtros opcionais --parent-id, --warehouse-type; --limit (default 20); --offset (default 0). |
| **Saídas** | warehouses[], total_count, limit, offset, has_more. |
| **Regras** | Resolve company_id por id ou nome; conta e pagina ordenando por name. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível por id ou nome. |

## Movimentações

**Objetivo.** Ciclo de vida de stock entries (recebimento, baixa, transferência, manufatura) em rascunho/submit/cancel.

### `add-stock-entry`

Cria uma movimentação de estoque em rascunho com seus itens.

| | |
|---|---|
| **Entradas** | --entry-type (obrigatório, receive\|issue\|transfer\|manufacture); --company-id (obrigatório); --posting-date (obrigatório); --items (obrigatório, JSON array com item_id, qty, rate, from_warehouse_id, to_warehouse_id, batch_id, serial_numbers). |
| **Saídas** | stock_entry_id, naming_series, total_incoming_value, total_outgoing_value, value_difference. |
| **Regras** | Valida entry_type e company; cada item exige item_id válido e qty>0; rate<=0 cai para standard_rate; usa default_warehouse da empresa se faltar from/to; valida warehouse exigido por tipo (receipt exige to, issue exige from, transfer exige ambos, manufacture exige um); calcula totais incoming/outgoing e value_difference. |
| **Efeitos colaterais** | INSERT em stock_entry (status='draft', naming_series via get_next_name) e em stock_entry_item; audit_log via audit('add-stock-entry'); commit. NÃO posta SLE/GL. |
| **Pré-condições** | Empresa existe; itens referenciados existem. |

### `get-stock-entry`

Retorna uma stock entry com seus itens.

| | |
|---|---|
| **Entradas** | --stock-entry-id (obrigatório). |
| **Saídas** | Campos da stock_entry + items[] (com item_code/item_name). |
| **Regras** | Erra se não existe; itens ordenados por line_order. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Stock entry existe. |

### `list-stock-entries`

Lista movimentações com filtros e paginação.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --company-id, --entry-type (mapeado), --status-filter (dest se_status), --from-date, --to-date; --limit (default 20); --offset (default 0). |
| **Saídas** | stock_entries[], total_count, limit, offset, has_more. |
| **Regras** | Conta e pagina ordenando por posting_date desc e created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `submit-stock-entry`

Submete uma stock entry rascunho, postando SLE e GL de inventário perpétuo.

| | |
|---|---|
| **Entradas** | --stock-entry-id (obrigatório). |
| **Saídas** | stock_entry_id, sle_entries_created, gl_entries_created. |
| **Regras** | Erra se não existe ou status != 'draft'; erra se sem itens; constrói SLE por tipo (receipt +qty com require_rate; issue -qty; transfer -from/+to; manufacture +to/-from); resolve fiscal_year e cost_center; falha de SLE/GL aborta com erro. |
| **Efeitos colaterais** | INSERT em stock_ledger_entry (insert_sle_entries) e gl_entry (create_perpetual_inventory_gl + insert_gl_entries); UPDATE stock_entry status='submitted'; audit_log via audit('submit-stock-entry'); commit. |
| **Pré-condições** | Stock entry em status 'draft' com itens; fiscal year e contas de inventário configurados. |

### `cancel-stock-entry`

Cancela uma stock entry submetida, revertendo SLE e GL.

| | |
|---|---|
| **Entradas** | --stock-entry-id (obrigatório). |
| **Saídas** | stock_entry_id, reversed, sle_reversals, gl_reversals. |
| **Regras** | Erra se não existe ou status != 'submitted'; reverte SLE (obrigatório) e GL (tolera ausência de GL); usa posting_date original. |
| **Efeitos colaterais** | INSERT de SLE de reversão (reverse_sle_entries) e GL de reversão (reverse_gl_entries); UPDATE stock_entry status='cancelled'; audit_log via audit('cancel-stock-entry'); commit. |
| **Pré-condições** | Stock entry em status 'submitted'. |

## Razão de Estoque (SLE)

**Objetivo.** Gateway cross-skill para selling/buying criarem e reverterem lançamentos no razão de estoque.

### `create-stock-ledger-entries`

Cross-skill: cria lançamentos de SLE para um voucher externo.

| | |
|---|---|
| **Entradas** | --voucher-type (obrigatório, canonicalizado para snake_case); --voucher-id (obrigatório); --posting-date (obrigatório); --entries (obrigatório, JSON array); --company-id (obrigatório). |
| **Saídas** | sle_ids[], count. |
| **Regras** | Canonicaliza voucher_type via canonical_voucher_type (FINDING-006); --entries deve ser array não vazio; injeta fiscal_year em cada entry; falha de SLE aborta com erro. |
| **Efeitos colaterais** | INSERT em stock_ledger_entry (insert_sle_entries); audit_log via audit('create-stock-ledger-entries'); commit. |
| **Pré-condições** | Empresa e itens/warehouses dos entries existentes; chamado por selling/buying. |

### `reverse-stock-ledger-entries`

Cross-skill: reverte os lançamentos de SLE de um voucher externo.

| | |
|---|---|
| **Entradas** | --voucher-type (obrigatório, canonicalizado); --voucher-id (obrigatório); --posting-date (obrigatório). |
| **Saídas** | reversal_ids[], count. |
| **Regras** | Canonicaliza voucher_type para casar com SLE armazenados; falha de reversão aborta com erro. |
| **Efeitos colaterais** | INSERT de SLE de reversão (reverse_sle_entries); audit_log via audit('reverse-stock-ledger-entries'); commit. |
| **Pré-condições** | Existirem SLE não cancelados sob o voucher informado. |

## Saldos e Relatórios

**Objetivo.** Consultas de saldo por item/depósito, relatórios de estoque/razão, status e checagem de ponto de reposição.

### `get-stock-balance`

Retorna saldo, taxa de valoração e valor de um item em um depósito.

| | |
|---|---|
| **Entradas** | --item-id (obrigatório); --warehouse-id (obrigatório). |
| **Saídas** | item_id, warehouse_id, qty, valuation_rate, stock_value. |
| **Regras** | Delega a get_stock_balance (soma de SLE não cancelado). |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Item e depósito informados. |

### `stock-balance-report`

Resumo de saldo de todos os itens de uma empresa (com alias 'stock-balance').

| | |
|---|---|
| **Entradas** | --company-id ou --company (nome) (via resolve_company_id); filtro opcional --warehouse-id. |
| **Saídas** | report[] (item, warehouse, qty, valuation_rate, stock_value), total_stock_value, row_count. |
| **Regras** | SQL raw com decimal_sum e subquery correlacionada de valuation_rate mais recente; só linhas com saldo != 0; ignora SLE cancelado. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível por id ou nome. |

### `stock-ledger-report`

Relatório detalhado de lançamentos no razão de estoque.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --item-id, --warehouse-id, --from-date, --to-date; --limit (default 100); --offset (default 0). |
| **Saídas** | entries[] (campos da SLE + item_code/item_name/warehouse_name), count. |
| **Regras** | Apenas SLE não cancelado, ordenado por posting_date desc e created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

### `status`

Resumo de inventário (itens, depósitos, stock entries por status e valor total) de uma empresa.

| | |
|---|---|
| **Entradas** | --company-id ou --company (nome) (via resolve_company_id). |
| **Saídas** | items, warehouses, stock_entries{draft,submitted,cancelled,total}, total_stock_value. |
| **Regras** | Conta itens (global), depósitos da empresa, stock entries agrupadas por status; soma stock_value_difference de SLE não cancelado via decimal_sum. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível por id ou nome. |

### `check-reorder`

Lista itens cujo estoque atual está no nível de reposição ou abaixo.

| | |
|---|---|
| **Entradas** | --company-id ou --company (nome) (via resolve_company_id). |
| **Saídas** | items_below_reorder, items[] (item, current_stock, reorder_level, reorder_qty, shortfall). |
| **Regras** | Considera só itens ativos com reorder_level definido (não vazio/!=0); soma estoque por todos depósitos da empresa via decimal_sum em SLE não cancelado; inclui item se current_stock <= reorder_level com shortfall calculado. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível; itens com reorder_level configurado. |

## Lotes

**Objetivo.** Cadastro e listagem de lotes (batches) por item, com saldos por depósito.

### `add-batch`

Cria um lote vinculado a um item.

| | |
|---|---|
| **Entradas** | --item-id (obrigatório); --batch-name (obrigatório); --manufacturing-date (opcional); --expiry-date (opcional). |
| **Saídas** | batch_id, batch_name. |
| **Regras** | Erra se item não existe; IntegrityError vira erro de duplicidade/inválido. |
| **Efeitos colaterais** | INSERT em batch; audit_log via audit('add-batch'); commit. |
| **Pré-condições** | Item existe. |

### `list-batches`

Lista lotes, opcionalmente filtrando por item e por estoque em um depósito.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --item-id, --warehouse-id; --limit (default 20); --offset (default 0). |
| **Saídas** | batches[], total_count, limit, offset, has_more. |
| **Regras** | Com --warehouse-id usa SQL raw com decimal_sum (HAVING saldo>0) sobre SLE não cancelado; sem warehouse lista direto da tabela batch ordenado por batch_name. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Números de Série

**Objetivo.** Registro e listagem de números de série de itens, com status de ciclo de vida.

### `add-serial-number`

Registra um número de série para um item.

| | |
|---|---|
| **Entradas** | --item-id (obrigatório); --serial-no (obrigatório); --warehouse-id (opcional); --batch-id (opcional). |
| **Saídas** | serial_number_id, serial_no. |
| **Regras** | Erra se item não existe; status inicial 'active'; IntegrityError vira erro de duplicidade. |
| **Efeitos colaterais** | INSERT em serial_number (status='active'); audit_log via audit('add-serial-number'); commit. |
| **Pré-condições** | Item existe. |

### `list-serial-numbers`

Lista números de série com filtros e paginação.

| | |
|---|---|
| **Entradas** | Filtros opcionais: --item-id, --warehouse-id, --serial-status (dest sn_status, valores active\|delivered\|returned\|scrapped); --limit (default 20); --offset (default 0). |
| **Saídas** | serial_numbers[] (com item_code/item_name), total_count, limit, offset, has_more. |
| **Regras** | Valida sn_status contra VALID_SERIAL_STATUSES quando informado; ordena por serial_no. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Preços e Regras

**Objetivo.** Listas de preço, preços por item (com faixas/validade) e regras de precificação/desconto.

### `add-price-list`

Cria uma lista de preços (compra e/ou venda).

| | |
|---|---|
| **Entradas** | --name (obrigatório); --currency (default 'USD'); --is-buying (default 0); --is-selling (default 0). |
| **Saídas** | price_list_id, name. |
| **Regras** | IntegrityError vira erro de duplicidade. |
| **Efeitos colaterais** | INSERT em price_list; audit_log via audit('add-price-list'); commit. |
| **Pré-condições** | Nenhuma. |

### `add-item-price`

Define um preço para um item em uma lista de preços.

| | |
|---|---|
| **Entradas** | --item-id (obrigatório); --price-list-id (obrigatório); --rate (obrigatório); --min-qty (default 0); --valid-from (opcional); --valid-to (opcional). |
| **Saídas** | item_price_id, rate. |
| **Regras** | Erra se item ou price_list não existem; arredonda rate. |
| **Efeitos colaterais** | INSERT em item_price; audit_log via audit('add-item-price'); commit. |
| **Pré-condições** | Item e price_list existem. |

### `get-item-price`

Obtém o preço aplicável de um item em uma lista de preços para uma quantidade.

| | |
|---|---|
| **Entradas** | --item-id (obrigatório); --price-list-id (obrigatório); --qty (default 1). |
| **Saídas** | Campos do item_price selecionado. |
| **Regras** | Busca melhor faixa válida por data e min_qty<=qty (ordem min_qty desc); fallback para preço mais recente ignorando data/qty; erra se nenhum preço encontrado. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Existir item_price para item/lista. |

### `add-pricing-rule`

Cria uma regra de precificação/desconto por entidade.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --applies-to (obrigatório, item\|item_group\|customer\|customer_group); --company-id (obrigatório); opcionais: --entity-id, --discount-percentage, --pricing-rule-rate (dest pr_rate), --min-qty, --max-qty, --valid-from, --valid-to, --priority (default 0). |
| **Saídas** | pricing_rule_id, name. |
| **Regras** | Valida applies_to contra valores permitidos; priority default 0. |
| **Efeitos colaterais** | INSERT em pricing_rule; audit_log via audit('add-pricing-rule'); commit. |
| **Pré-condições** | Empresa informada. |

## Reconciliação

**Objetivo.** Reconciliação de estoque (contagem física) com ciclo rascunho/submit que ajusta SLE e GL pelas diferenças.

### `add-stock-reconciliation`

Cria uma reconciliação de estoque (contagem física) em rascunho.

| | |
|---|---|
| **Entradas** | --posting-date (obrigatório); --items (obrigatório, JSON array com item_id, warehouse_id, qty, valuation_rate); --company-id (obrigatório). |
| **Saídas** | stock_reconciliation_id, naming_series, difference_amount, item_count. |
| **Regras** | Valida company; cada item exige item_id e warehouse_id; busca saldo atual via get_stock_balance; calcula quantity_difference e amount_difference (contado vs atual) e soma total. |
| **Efeitos colaterais** | INSERT em stock_reconciliation (status='draft', naming via get_next_name) e stock_reconciliation_item; audit_log via audit('add-stock-reconciliation'); commit. NÃO posta SLE/GL. |
| **Pré-condições** | Empresa existe; itens e depósitos referenciados existem. |

### `submit-stock-reconciliation`

Submete a reconciliação, postando SLE e GL para as diferenças de quantidade/valor.

| | |
|---|---|
| **Entradas** | --stock-reconciliation-id (obrigatório). |
| **Saídas** | stock_reconciliation_id, sle_entries_created, gl_entries_created. |
| **Regras** | Erra se não existe ou status != 'draft'; erra se sem itens; cria SLE só para itens com quantity_difference != 0 (incoming_rate=valuation_rate se diff>0, senão 0); resolve fiscal_year, cost_center e conta stock_adjustment como contra; falha de SLE/GL aborta. |
| **Efeitos colaterais** | INSERT em stock_ledger_entry e gl_entry (create_perpetual_inventory_gl); UPDATE stock_reconciliation status='submitted'; audit_log via audit('submit-stock-reconciliation'); commit. |
| **Pré-condições** | Reconciliação em status 'draft' com itens; contas de inventário/ajuste configuradas. |

## Revaloração

**Objetivo.** Revaloração de estoque (mudança de taxa sem alterar quantidade) com postagem imediata e ciclo submit/cancel.

### `revalue-stock`

Revaloriza o estoque de um item em um depósito alterando a taxa, sem mudar a quantidade.

| | |
|---|---|
| **Entradas** | --item-id (obrigatório); --warehouse-id (obrigatório); --new-rate (obrigatório, >=0); --posting-date (obrigatório); --reason (opcional). |
| **Saídas** | revaluation_id, naming_series, item_id, item_name, warehouse, current_qty, old_rate, new_rate, adjustment_amount, gl_entries_created. |
| **Regras** | Valida new_rate numérico e não negativo; item deve existir e ser is_stock_item; warehouse deve existir; erra se qty<=0 ou se new_rate igual ao atual; calcula ajuste = novo_valor - valor_atual; GL: ajuste>0 DR Stock-in-Hand/CR Stock-Adjustment, ajuste<0 inverso; ação one-step (sem rascunho), grava status='submitted'. |
| **Efeitos colaterais** | INSERT em stock_ledger_entry (actual_qty=0, com stock_value_difference), gl_entry (insert_gl_entries) e stock_revaluation (status='submitted'); audit_log via audit('revalue-stock'); commit. |
| **Pré-condições** | Item de estoque com saldo>0 no depósito; contas stock e stock_adjustment configuradas para gerar GL. |

### `list-stock-revaluations`

Lista revalorações de estoque de uma empresa.

| | |
|---|---|
| **Entradas** | --company-id ou --company (nome) (via resolve_company_id); --limit (default 20); --offset (default 0). |
| **Saídas** | revaluations[] (com item_code/item_name/warehouse_name), total_count, limit, offset, has_more. |
| **Regras** | Ordena por created_at desc; conta total da empresa. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível por id ou nome. |

### `get-stock-revaluation`

Retorna detalhes de uma revaloração incluindo seus SLE e GL.

| | |
|---|---|
| **Entradas** | --revaluation-id (obrigatório). |
| **Saídas** | Campos da stock_revaluation + item/warehouse + sle_entries[] + gl_entries[]. |
| **Regras** | Erra se não existe; busca SLE e GL pelo voucher_type='stock_revaluation' e voucher_id. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Revaloração existe. |

### `cancel-stock-revaluation`

Cancela uma revaloração submetida, revertendo SLE e GL.

| | |
|---|---|
| **Entradas** | --revaluation-id (obrigatório). |
| **Saídas** | revaluation_id, cancelled, item_id, warehouse_id. |
| **Regras** | Erra se não existe ou status != 'submitted'; reverte SLE e GL (ambos obrigatórios, falha aborta). |
| **Efeitos colaterais** | INSERT de SLE de reversão (reverse_sle_entries) e GL de reversão (reverse_gl_entries); UPDATE stock_revaluation status='cancelled'; audit_log via audit('cancel-stock-revaluation'); commit. |
| **Pré-condições** | Revaloração em status 'submitted'. |

## Reposição/Projeção

**Objetivo.** Cálculo de quantidade projetada considerando estoque atual, pedidos de compra pendentes e vendas reservadas.

### `get-projected-qty`

Calcula a quantidade projetada de um item em um depósito (atual + a receber - reservado).

| | |
|---|---|
| **Entradas** | --item-id (obrigatório); --warehouse-id (obrigatório). |
| **Saídas** | item_id, item_code, item_name, warehouse_id, actual_qty, ordered_qty, reserved_qty, projected_qty. |
| **Regras** | Erra se item ou warehouse não existem; actual_qty via get_stock_balance; ordered_qty soma (quantity-received_qty) de itens de PO confirmados/parcialmente recebidos; reserved_qty soma (quantity-delivered_qty) de itens de SO confirmados/parcialmente entregues; projected = actual + ordered - reserved. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Item e depósito existem; tabelas purchase_order(_item) e sales_order(_item) presentes. |

## Variantes

**Objetivo.** Definição de atributos de template e geração de variantes de item (single ou produto cartesiano).

### `add-item-attribute`

Adiciona uma definição de atributo a um item template, marcando-o como template.

| | |
|---|---|
| **Entradas** | --item-id (obrigatório); --attribute-name (obrigatório); --attribute-values (obrigatório, JSON array). |
| **Saídas** | attribute_id, item_id, attribute_name, values. |
| **Regras** | Erra se item não existe ou é variante (variant_of setado); values deve ser array não vazio; erra se atributo já existe no item. |
| **Efeitos colaterais** | INSERT em item_attribute; UPDATE item has_variants=1 e updated_at; audit_log via audit('add-item-attribute'); commit. |
| **Pré-condições** | Item existe e não é variante. |

### `create-item-variant`

Cria uma única variante de item a partir de um template com valores de atributo específicos.

| | |
|---|---|
| **Entradas** | --template-item-id (obrigatório); --attributes (obrigatório, JSON object). |
| **Saídas** | variant_id, item_code, item_name, template_item_id, attributes. |
| **Regras** | Erra se template não existe ou não tem has_variants; valida cada attr_name e valor contra definições do template; gera item_code/name por sufixo de valores; erra se variante duplicada. |
| **Efeitos colaterais** | INSERT em item (variant_of=template, status='active') e em item_attribute por atributo; audit_log via audit('create-item-variant'); commit. |
| **Pré-condições** | Item template com atributos definidos (has_variants=1). |

### `generate-item-variants`

Gera todas as variantes possíveis de um template (produto cartesiano dos atributos).

| | |
|---|---|
| **Entradas** | --template-item-id (obrigatório). |
| **Saídas** | template_item_id, created, skipped, skipped_codes[], variants[]. |
| **Regras** | Erra se template não existe ou não é template ou sem atributos; erra se algum atributo sem valores; itertools.product das combinações; pula variantes cujo item_code já existe. |
| **Efeitos colaterais** | INSERT em item (variant_of, status='active') e item_attribute para cada combinação nova; commit. NÃO grava audit_log. |
| **Pré-condições** | Template com has_variants=1 e atributos com valores. |

### `list-item-variants`

Lista todas as variantes de um item template com seus atributos.

| | |
|---|---|
| **Entradas** | --template-item-id (obrigatório). |
| **Saídas** | template_item_id, count, variants[] (variant_id, item_code, item_name, status, standard_rate, attributes). |
| **Regras** | Erra se template não existe; busca itens com variant_of=template e seus item_attribute. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Item template existe. |

## Fornecedores de Item

**Objetivo.** Vínculo entre itens e fornecedores com quantidade mínima de pedido, lead time e prioridade.

### `add-item-supplier`

Vincula um item a um fornecedor com qty mínima de pedido e lead time.

| | |
|---|---|
| **Entradas** | --item-id (obrigatório); --supplier-id (obrigatório); --min-order-qty (default 0); --lead-time-days (opcional); --priority (default 0). |
| **Saídas** | item_supplier_id, item_id, supplier_id, min_order_qty, lead_time_days, priority. |
| **Regras** | Erra se item ou supplier não existem; arredonda min_order_qty; IntegrityError vira erro 'link já existe'. |
| **Efeitos colaterais** | INSERT em item_supplier; audit_log via audit('add-item-supplier'); commit. |
| **Pré-condições** | Item e fornecedor existem; tabela supplier presente. |

### `list-item-suppliers`

Lista fornecedores de um item ou itens de um fornecedor.

| | |
|---|---|
| **Entradas** | Pelo menos um de --item-id ou --supplier-id (obrigatório). |
| **Saídas** | count, item_suppliers[] (com item_code/item_name/supplier_name). |
| **Regras** | Erra se nenhum dos dois filtros informado; ordena por priority. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabelas item_supplier, item e supplier presentes. |

