# Impostos — `glue-tax`

> Spec funcional por ação. Gerada de `scripts/glue-tax/db_query.py`. 9 funcionalidades · 18 ações.

## Modelos

**Objetivo.** Gerenciar modelos de imposto (tax_template) e suas linhas de alíquota (CRUD completo).

### `add-tax-template`

Cria um modelo de imposto com suas linhas de alíquota para uma empresa.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --tax-type (obrigatório: sales\|purchase\|both); --company-id (obrigatório); --lines JSON array (obrigatório, cada linha exige tax_account_id e rate; opcionais charge_type [def on_net_total], add_deduct [def add], row_order [def índice], included_in_print_rate, description); --is-default (flag, default None). |
| **Saídas** | status='created', tax_template_id, name, line_count. |
| **Regras** | Valida tax_type contra VALID_TAX_TYPES; verifica que a empresa existe; valida cada linha (rate decimal, charge_type em VALID_CHARGE_TYPES, add_deduct em add/deduct) e que cada tax_account_id existe; se --is-default, zera is_default de outros templates do mesmo company com tax_type igual ou 'both'. Sem ciclo submit/cancel. |
| **Efeitos colaterais** | INSERT em tax_template e tax_template_line; possível UPDATE is_default=0 em tax_template; grava audit_log via audit(); commit. |
| **Pré-condições** | Empresa existente e contas (account) das linhas existentes. |

### `update-tax-template`

Atualiza nome, flag de padrão e/ou substitui as linhas de um modelo existente.

| | |
|---|---|
| **Entradas** | --tax-template-id (obrigatório); --name (opcional); --is-default (flag, default None); --lines JSON array (opcional; substitui todas as linhas). |
| **Saídas** | status='updated', tax_template_id, updated_fields (lista). |
| **Regras** | Erro se template não existe; se is_default=true zera is_default dos demais templates do mesmo company/tax_type(ou both) exceto o próprio; se --lines informado, revalida linhas e contas, apaga linhas antigas e reinsere; erro 'No fields to update' se nada mudou; seta updated_at via dynamic_update. |
| **Efeitos colaterais** | UPDATE em tax_template (campos + updated_at); possível UPDATE is_default=0 nos demais; DELETE+INSERT em tax_template_line se --lines; grava audit_log; commit. |
| **Pré-condições** | Modelo existente; contas das novas linhas existentes. |

### `get-tax-template`

Retorna um modelo de imposto com suas linhas e nomes das contas.

| | |
|---|---|
| **Entradas** | --tax-template-id (obrigatório). |
| **Saídas** | Campos do tax_template (star) mais lines[] (linhas com account_name, ordenadas por row_order). |
| **Regras** | Erro se template não encontrado. Somente leitura. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Modelo existente. |

### `list-tax-templates`

Lista modelos de imposto de uma empresa com paginação.

| | |
|---|---|
| **Entradas** | --company-id ou --company (nome) resolvidos por resolve_company_id; --tax-type (opcional, filtra por tax_type igual ou 'both'); --limit (def 20); --offset (def 0). |
| **Saídas** | templates[], total_count, limit, offset, has_more. |
| **Regras** | Resolve company; aplica filtro opcional de tax_type; ordena por name. Somente leitura. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível. |

### `delete-tax-template`

Exclui um modelo de imposto e suas linhas se não estiver referenciado.

| | |
|---|---|
| **Entradas** | --tax-template-id (obrigatório). |
| **Saídas** | deleted=True. |
| **Regras** | Erro se não existe; erro se referenciado por tax_rule (cnt>0) ou por item_tax_template (cnt>0). Exclusão definitiva (sem cancelamento lógico). |
| **Efeitos colaterais** | DELETE em tax_template_line e em tax_template; grava audit_log; commit. |
| **Pré-condições** | Modelo existente e sem referências em tax_rule nem item_tax_template. |

## Categorias

**Objetivo.** Gerenciar categorias de imposto (tax_category) usadas como filtro em regras.

### `add-tax-category`

Cria uma categoria de imposto com nome e descrição opcional.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --description (opcional, default ''). |
| **Saídas** | status='created', tax_category_id, name. |
| **Regras** | Erro se --name ausente. Sem validações adicionais nem ciclo de status. |
| **Efeitos colaterais** | INSERT em tax_category; grava audit_log; commit. |
| **Pré-condições** | Nenhuma específica. |

### `list-tax-categories`

Lista todas as categorias de imposto com paginação.

| | |
|---|---|
| **Entradas** | --limit (def 20); --offset (def 0). |
| **Saídas** | categories[], total_count, limit, offset, has_more. |
| **Regras** | Sem filtro por empresa (tax_category é global); ordena por name. Somente leitura. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Nenhuma. |

## Regras

**Objetivo.** Gerenciar regras (tax_rule) que mapeiam filtros de parte/estado/categoria para um modelo de imposto.

### `add-tax-rule`

Cria uma regra que associa filtros a um modelo de imposto com prioridade.

| | |
|---|---|
| **Entradas** | --tax-template-id (obrigatório); --tax-type (obrigatório: sales\|purchase); --priority int (obrigatório); ao menos um filtro: --customer-id, --customer-group, --supplier-id, --shipping-state ou --tax-category-id. |
| **Saídas** | status='created', tax_rule_id. |
| **Regras** | Erro se tax_type não for sales/purchase; erro se priority ausente; erro se template não existe; erro se nenhum filtro informado. supplier_group é gravado como None; company_id herdado do template. |
| **Efeitos colaterais** | INSERT em tax_rule; grava audit_log; commit. |
| **Pré-condições** | Modelo de imposto existente. |

### `list-tax-rules`

Lista as regras de imposto de uma empresa com o nome do modelo associado.

| | |
|---|---|
| **Entradas** | --company-id ou --company (nome); --limit (def 20); --offset (def 0). |
| **Saídas** | rules[] (campos da regra + template_name), total_count, limit, offset, has_more. |
| **Regras** | Resolve company; ordena por priority e depois created_at. Somente leitura. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível. |

## Resolução

**Objetivo.** Selecionar automaticamente o modelo de imposto aplicável a uma parte/transação avaliando as regras por prioridade.

### `resolve-tax-template`

Determina o modelo de imposto para uma parte casando regras na ordem de prioridade, com fallback no padrão da empresa.

| | |
|---|---|
| **Entradas** | --party-type (obrigatório, deve estar em party_type_registry); --party-id (obrigatório); --company-id ou --company; --transaction-type (opcional; default sales p/ customer, purchase p/ supplier, senão sales); --tax-category-id (opcional); --shipping-address JSON (opcional, usa campo state). |
| **Saídas** | tax_template_id, template_name, is_exempt, item_overrides[]. |
| **Regras** | Valida party_type contra registro; para customer marca is_exempt se exempt_from_sales_tax; itera regras (tax_type igual ou template 'both') por priority asc casando customer_id, customer_group, supplier_id, shipping_state e tax_category_id; primeira regra casada vence; sem match cai no template is_default da empresa; coleta item_tax_template cujo template difere do escolhido. Somente leitura. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | party_type registrado em party_type_registry; empresa resolvível; regras/template padrão cadastrados para haver resultado. |

## Cálculo

**Objetivo.** Calcular impostos sobre itens a partir das linhas de um modelo, sem persistência.

### `calculate-tax`

Calcula impostos em cascata por linha do modelo e distribui proporcionalmente por item.

| | |
|---|---|
| **Entradas** | --tax-template-id (obrigatório); --items JSON array (obrigatório; cada item com item_id, net_amount, opcional qty); --item-overrides JSON (opcional; item_id->override_template_id, itens sobrepostos não recebem rateio). |
| **Saídas** | tax_lines[] (tax_account_id, account_name, description, rate, amount), total_tax, net_total, grand_total, per_item_tax[]. |
| **Regras** | Erro se sem template ou sem linhas; soma net_total; por linha aplica base conforme charge_type (on_net_total, on_previous_row_total, on_previous_row_amount, actual [rate vira valor], on_item_quantity [soma qty]); 'actual' usa valor direto, demais base*rate/100; add_deduct=deduct nega o valor; rateio proporcional ao net_amount do item; arredonda via round_currency. Cálculo puro. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Modelo com linhas (tax_template_line) cadastradas. |

## Impostos por Item

**Objetivo.** Definir sobreposições de modelo de imposto por item (item_tax_template).

### `add-item-tax-template`

Associa um item a um modelo de imposto (override por item) com alíquota opcional.

| | |
|---|---|
| **Entradas** | --item-id (obrigatório); --tax-template-id (obrigatório); --tax-rate (opcional). |
| **Saídas** | status='created', item_tax_template_id. |
| **Regras** | Erro se item-id ou tax-template-id ausentes; erro se template não existe. Sem verificação de existência do item nem ciclo de status. |
| **Efeitos colaterais** | INSERT em item_tax_template; grava audit_log; commit. |
| **Pré-condições** | Modelo de imposto existente. |

## Retenção na Fonte

**Objetivo.** Configurar categorias de retenção e registrar entradas de imposto retido (tax_withholding_category/group/entry).

### `add-tax-withholding-category`

Cria uma categoria de retenção (e um grupo padrão com a alíquota) vinculada ao tipo de formulário.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --rate (obrigatório, decimal); --threshold-amount (obrigatório, decimal); --form-type (obrigatório: 1099-NEC\|1099-MISC); --company-id (obrigatório). |
| **Saídas** | status='created', category_id, name. |
| **Regras** | Valida form-type em VALID_FORM_TYPES; valida rate e threshold como decimais; grava form_type em category_code e threshold em cumulative_threshold; busca primeira conta tax/payable da empresa para o grupo (group 'Default', effective_from 2020-01-01); grupo só é criado se houver conta de retenção. |
| **Efeitos colaterais** | INSERT em tax_withholding_category e (condicional) tax_withholding_group; grava audit_log; commit. |
| **Pré-condições** | Empresa existente; idealmente uma conta com account_type tax/payable para criar o grupo. |

### `get-withholding-details`

Agrega informação de retenção de um fornecedor em um ano fiscal (YTD, limite, backup withholding).

| | |
|---|---|
| **Entradas** | --supplier-id (obrigatório); --tax-year (obrigatório); --company-id ou --company. |
| **Saídas** | is_1099_vendor, withholding_category, ytd_payments, threshold_exceeded, withholding_rate, backup_withholding_rate, w9_on_file, withholding_amount. |
| **Regras** | Erro se fornecedor não existe; lê categoria do fornecedor e a alíquota do grupo mais recente (effective_from desc); soma taxable_amount em tax_withholding_entry no ano; threshold_exceeded se ytd>=cumulative_threshold; backup rate=24% se 1099 e sem W9, aplicado sobre o YTD. Somente leitura. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Fornecedor existente; empresa resolvível. |

### `record-withholding-entry`

Registra uma entrada de imposto retido (withheld_amount) de um fornecedor para um voucher.

| | |
|---|---|
| **Entradas** | --supplier-id (obrigatório); --voucher-type (obrigatório); --voucher-id (obrigatório); --withholding-amount (obrigatório); --tax-year (obrigatório). |
| **Saídas** | status='created', withholding_entry_id. |
| **Regras** | Normaliza voucher_type via canonical_voucher_type (FINDING-006); erro se fornecedor não existe; erro se fornecedor sem tax_withholding_category_id; grava taxable_amount=0 e withheld_amount=withholding-amount em withholding_voucher_type/id. |
| **Efeitos colaterais** | INSERT em tax_withholding_entry; grava audit_log; commit. Não posta em gl_entry/PLE. |
| **Pré-condições** | Fornecedor existente com categoria de retenção atribuída. |

## Relatórios 1099

**Objetivo.** Registrar pagamentos elegíveis a 1099 e gerar os dados consolidados de 1099 por fornecedor.

### `record-1099-payment`

Registra um pagamento tributável (taxable_amount) elegível a 1099 para um fornecedor e retorna o total YTD.

| | |
|---|---|
| **Entradas** | --supplier-id (obrigatório); --amount (obrigatório, mapeado para ple_amount); --tax-year (obrigatório); --voucher-type (obrigatório); --voucher-id (obrigatório). |
| **Saídas** | status='created', ytd_1099_total. |
| **Regras** | Normaliza voucher_type via canonical_voucher_type; erro se fornecedor não existe; erro se sem tax_withholding_category_id; grava taxable_amount=amount e withheld_amount=0 em taxable_voucher_type/id; recalcula soma YTD de taxable_amount. |
| **Efeitos colaterais** | INSERT em tax_withholding_entry; grava audit_log; commit. Não posta em gl_entry/PLE. |
| **Pré-condições** | Fornecedor existente com categoria de retenção atribuída. |

### `generate-1099-data`

Gera a lista de fornecedores e valores para emissão de 1099 no ano fiscal, aplicando o limite por categoria.

| | |
|---|---|
| **Entradas** | --tax-year (obrigatório); --company-id ou --company. |
| **Saídas** | vendors[] (supplier_id, name, tin, total_paid, form_type, box_1). |
| **Regras** | Soma taxable_amount por party_id/category das entries do ano cujas categorias pertencem à empresa; ignora fornecedores abaixo do cumulative_threshold da categoria; form_type vem de category_code (default 1099-NEC); box_1 = total se 1099-NEC senão 0.00. Somente leitura. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível; entradas em tax_withholding_entry para o ano. |

## Status

**Objetivo.** Resumir contagens de configuração de imposto e fornecedores 1099 do ano corrente para a empresa.

### `status`

Retorna contagens de modelos, regras, categorias de retenção e fornecedores 1099 do ano atual.

| | |
|---|---|
| **Entradas** | --company-id ou --company (resolvidos por resolve_company_id). |
| **Saídas** | templates, rules, withholding_categories, ytd_1099_vendors. |
| **Regras** | Conta tax_template, tax_rule e tax_withholding_category da empresa; conta party_id distintos em tax_withholding_entry do ano UTC atual cujas categorias são da empresa. Somente leitura. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Empresa resolvível. |

