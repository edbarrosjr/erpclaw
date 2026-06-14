# Impostos — `erpclaw-tax`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-tax/db_query.py`. 10 funcionalidades · 18 ações.

## Modelos

**Objetivo.** Gerencia modelos de imposto (tax_template) com suas linhas de cálculo (tax_template_line), que definem contas, alíquotas e tipo de incidência para vendas, compras ou ambos.

**Ações:**
- `add-tax-template` — Cria um modelo de imposto com uma ou mais linhas (conta, alíquota, charge_type, add_deduct).
- `update-tax-template` — Atualiza nome, flag padrão e/ou substitui integralmente as linhas do modelo.
- `get-tax-template` — Retorna o modelo e suas linhas (com nome da conta), ordenadas por row_order.
- `list-tax-templates` — Lista modelos da empresa com paginação, filtrando opcionalmente por tax_type (inclui 'both').
- `delete-tax-template` — Exclui o modelo e suas linhas se nao houver referencias.

| Campo | Detalhe |
|---|---|
| **Entradas** | --name, --tax-type (sales\|purchase\|both), --company-id, --lines (array JSON: tax_account_id, rate, charge_type, add_deduct, row_order, included_in_print_rate, description), --is-default, --tax-template-id, --limit, --offset. |
| **Saídas** | Em criar/atualizar: status e tax_template_id (e line_count/updated_fields). get retorna o cabecalho mais a lista de lines com account_name. list retorna templates, total_count, limit, offset, has_more. |
| **Regras de negócio** | --name, --tax-type valido e --company-id obrigatorios; --lines obrigatorio e nao vazio. Cada linha valida rate (decimal), charge_type em (actual, on_net_total, on_previous_row_amount, on_previous_row_total, on_item_quantity) e add_deduct em (add, deduct). Empresa e todas as tax_account_id devem existir. is_default zera os demais defaults do mesmo tax_type (e 'both') da empresa. update substitui linhas apagando e reinserindo. delete bloqueia se referenciado por tax_rule ou item_tax_template. |
| **Efeitos colaterais** | Escreve em tax_template e tax_template_line (insert/update/delete). Grava trilha de auditoria via audit() para cada acao. Faz conn.commit(). Nenhuma postagem em GL, SLE de estoque ou payment_ledger_entry. |
| **Pré-condições** | Empresa (company) existente; contas (account) das linhas previamente cadastradas. Tabelas requeridas: company, account, party_type_registry. |

## Categorias

**Objetivo.** Mantem categorias de imposto (tax_category) usadas como criterio de classificacao e como filtro em regras de imposto.

**Ações:**
- `add-tax-category` — Cria uma categoria de imposto com nome e descricao opcional.
- `list-tax-categories` — Lista todas as categorias de imposto com paginacao, ordenadas por nome.

| Campo | Detalhe |
|---|---|
| **Entradas** | --name (obrigatorio), --description (opcional), --limit, --offset. |
| **Saídas** | add retorna status created e tax_category_id e name. list retorna categories, total_count, limit, offset, has_more. |
| **Regras de negócio** | --name obrigatorio. Categoria nao tem vinculo de empresa (global). Sem ciclo de vida rascunho/submit. Sem validacao de unicidade explicita no codigo. |
| **Efeitos colaterais** | Insere em tax_category e grava auditoria via audit(); faz commit. Nenhuma postagem em GL/estoque/pagamentos. |
| **Pré-condições** | Banco inicializado com tabelas requeridas (company, account, party_type_registry). |

## Regras

**Objetivo.** Define regras de imposto (tax_rule) que associam um modelo a criterios (cliente, grupo, fornecedor, estado de entrega, categoria) e uma prioridade, para selecao automatica do modelo aplicavel.

**Ações:**
- `add-tax-rule` — Cria uma regra que aponta para um modelo, com tipo, prioridade e ao menos um filtro.
- `list-tax-rules` — Lista regras da empresa com nome do modelo, ordenadas por prioridade e data, com paginacao.

| Campo | Detalhe |
|---|---|
| **Entradas** | --tax-template-id, --tax-type (sales\|purchase), --priority (int), e ao menos um filtro: --customer-id, --customer-group, --supplier-id, --shipping-state, --tax-category-id; --company-id/--company para listar; --limit, --offset. |
| **Saídas** | add retorna status created e tax_rule_id. list retorna rules (com template_name), total_count, limit, offset, has_more. |
| **Regras de negócio** | --tax-template-id, --tax-type (apenas sales ou purchase) e --priority obrigatorios. Pelo menos uma condicao de filtro e exigida. O modelo deve existir; company_id da regra herda o do modelo. supplier_group e gravado como None. Sem ciclo de vida rascunho/submit. |
| **Efeitos colaterais** | Insere em tax_rule e grava auditoria; faz commit. Nenhuma postagem contabil, de estoque ou de pagamento. |
| **Pré-condições** | Modelo de imposto (tax_template) existente; empresa resolvida para listagem; categorias/clientes/fornecedores referenciados conforme o filtro usado. |

## Resolucao

**Objetivo.** Seleciona automaticamente o modelo de imposto aplicavel para um parceiro e transacao, avaliando as regras por prioridade e caindo no modelo padrao da empresa quando nenhuma casa.

**Ações:**
- `resolve-tax-template` — Resolve o melhor tax_template para party/transacao, avalia isencao e lista overrides por item.

| Campo | Detalhe |
|---|---|
| **Entradas** | --party-type (deve estar no party_type_registry), --party-id, --company-id/--company; opcionais --transaction-type (sales\|purchase), --tax-category-id, --shipping-address (JSON com state). |
| **Saídas** | tax_template_id, template_name, is_exempt (bool) e item_overrides (itens cujo tax_template_id difere do resolvido). |
| **Regras de negócio** | party-type deve estar registrado; party-id obrigatorio. tx_type vem de --transaction-type ou inferido (customer=sales, supplier=purchase, generico=sales). Regras filtradas por empresa e tipo (inclui 'both'), avaliadas em ordem de prioridade asc; primeira correspondencia em customer_id/customer_group/supplier_id/shipping_state/tax_category_id vence. Sem match, usa template is_default da empresa do tipo. Cliente com exempt_from_sales_tax marca is_exempt=True. |
| **Efeitos colaterais** | Nenhum (somente leitura) — apenas SELECTs; nao escreve em nenhuma tabela nem em GL. |
| **Pré-condições** | party_type_registry populado; cliente/fornecedor existente; regras e/ou modelo padrao cadastrados na empresa; item_tax_template para overrides. |

## Calculo

**Objetivo.** Calcula impostos de uma lista de itens contra um modelo, aplicando linhas em cascata e distribuindo o imposto proporcionalmente por item.

**Ações:**
- `calculate-tax` — Calcula imposto por linha (cascata) e por item, retornando totais; calculo puro sem gravacao.

| Campo | Detalhe |
|---|---|
| **Entradas** | --tax-template-id, --items (array JSON: item_id, net_amount, qty), opcional --item-overrides (item_id, override_template_id). |
| **Saídas** | tax_lines (conta, nome, descricao, rate, amount), total_tax, net_total, grand_total e per_item_tax (item_id, tax_amount). |
| **Regras de negócio** | tax-template-id e --items obrigatorios; modelo deve ter linhas. Base por charge_type: on_net_total=net_total; on_previous_row_total=total da linha anterior (ou net); on_previous_row_amount=valor da linha anterior; actual=rate vira valor fixo; on_item_quantity=soma das qty. add_deduct=deduct inverte sinal. Itens em override_map nao recebem rateio. Arredondamento via round_currency. |
| **Efeitos colaterais** | Nenhum (somente leitura) — calculo puro, declarado 'no database writes'; nenhuma postagem em GL, SLE ou pagamentos. |
| **Pré-condições** | Modelo de imposto com linhas (tax_template_line) existente; contas das linhas cadastradas. |

## Impostos por Item

**Objetivo.** Associa um item a um modelo de imposto especifico (item_tax_template), permitindo sobrescrever a tributacao padrao para aquele item.

**Ações:**
- `add-item-tax-template` — Vincula um item a um tax_template com alíquota opcional, criando o override por item.

| Campo | Detalhe |
|---|---|
| **Entradas** | --item-id, --tax-template-id (obrigatorios), --tax-rate (opcional). |
| **Saídas** | status created e item_tax_template_id. |
| **Regras de negócio** | item-id e tax-template-id obrigatorios; o tax_template referenciado deve existir. Nao valida existencia do item nem unicidade do par item/modelo. Sem ciclo de vida rascunho/submit. |
| **Efeitos colaterais** | Insere em item_tax_template e grava auditoria; faz commit. Nenhuma postagem contabil, de estoque ou de pagamento. |
| **Pré-condições** | Modelo de imposto (tax_template) existente; item previamente cadastrado (nao verificado pelo codigo). |

## Retencao na Fonte

**Objetivo.** Registra lancamentos de retencao na fonte (tax_withholding_entry) para um fornecedor, vinculando-os ao voucher de origem e ao ano fiscal.

**Ações:**
- `record-withholding-entry` — Cria um lancamento de retencao com o valor retido para o fornecedor, voucher e ano fiscal.

| Campo | Detalhe |
|---|---|
| **Entradas** | --supplier-id, --voucher-type, --voucher-id, --withholding-amount, --tax-year (todos obrigatorios). |
| **Saídas** | status created e withholding_entry_id. |
| **Regras de negócio** | Todos os campos obrigatorios. voucher_type e normalizado para snake_case via canonical_voucher_type (FINDING-006). Fornecedor deve existir e ter tax_withholding_category_id atribuido. Grava withheld_amount=valor, taxable_amount=0, e armazena withholding_voucher_type/withholding_voucher_id. |
| **Efeitos colaterais** | Insere em tax_withholding_entry (somente do lado withholding) e grava auditoria; faz commit. Nao posta em GL/gl_entry nem em payment_ledger_entry; nao altera status de documento. |
| **Pré-condições** | Fornecedor (supplier) existente com tax_withholding_category_id definido; categoria de retencao cadastrada. |

## Retencao de Fornecedores

**Objetivo.** Cadastra categorias de retencao (tax_withholding_category) com alíquota e limiar, e consulta a situacao de retencao/1099 de um fornecedor em um ano fiscal.

**Ações:**
- `add-tax-withholding-category` — Cria categoria de retencao com limiar e tipo de formulario, e um grupo padrao com a alíquota.
- `get-withholding-details` — Agrega situacao de retencao do fornecedor no ano: pagamentos YTD, limiar, alíquota e backup withholding.

| Campo | Detalhe |
|---|---|
| **Entradas** | Para criar: --name, --rate, --threshold-amount, --form-type (1099-NEC\|1099-MISC), --company-id. Para consultar: --supplier-id, --tax-year, --company-id/--company. |
| **Saídas** | add retorna status created, category_id, name. get retorna is_1099_vendor, withholding_category, ytd_payments, threshold_exceeded, withholding_rate, backup_withholding_rate, w9_on_file, withholding_amount. |
| **Regras de negócio** | Criar: name, rate, threshold-amount, form-type valido e company-id obrigatorios; rate/threshold validados como decimal; form_type gravado em category_code e threshold em cumulative_threshold; cria grupo 'Default' com a alíquota e effective_from=2020-01-01 usando a primeira conta de tipo tax/payable da empresa. Consultar: soma taxable_amount YTD do twe; threshold_exceeded = ytd>=threshold; backup withholding de 24% aplicado quando is_1099_vendor e sem W9 em arquivo. |
| **Efeitos colaterais** | add insere em tax_withholding_category e (se houver conta) em tax_withholding_group, grava auditoria e faz commit. get e somente leitura (apenas SELECTs/agregacao). Nenhuma postagem em GL ou pagamentos. |
| **Pré-condições** | Empresa existente; para o grupo padrao deve haver conta com account_type tax ou payable na empresa; fornecedor existente para a consulta; lancamentos em tax_withholding_entry para haver YTD. |

## Relatorios 1099

**Objetivo.** Registra pagamentos tributaveis 1099 e gera os dados consolidados de 1099 por fornecedor/categoria para o ano fiscal, aplicando o limiar de reporte.

**Ações:**
- `record-1099-payment` — Registra um pagamento tributavel 1099 (taxable_amount) para o fornecedor e retorna o total YTD.
- `generate-1099-data` — Gera a lista de vendors 1099 da empresa no ano, filtrando os que atingiram o limiar da categoria.

| Campo | Detalhe |
|---|---|
| **Entradas** | record: --supplier-id, --amount, --tax-year, --voucher-type, --voucher-id. generate: --tax-year, --company-id/--company. |
| **Saídas** | record retorna status created e ytd_1099_total. generate retorna vendors (supplier_id, name, tin, total_paid, form_type, box_1). |
| **Regras de negócio** | record: campos obrigatorios; voucher_type normalizado (canonical_voucher_type); fornecedor deve existir e ter categoria; grava taxable_amount=valor, withheld_amount=0, e taxable_voucher_type/id; recalcula YTD. generate: soma decimal_sum(taxable_amount) por party/categoria; descarta quem ficou abaixo do cumulative_threshold da categoria; form_type vem de category_code (default 1099-NEC); box_1 = total quando 1099-NEC, senao 0.00. |
| **Efeitos colaterais** | record insere em tax_withholding_entry (lado taxable) e grava auditoria; faz commit. generate e somente leitura (agregacao). Nenhuma postagem em GL/gl_entry, SLE ou payment_ledger_entry; nao altera status de documento. |
| **Pré-condições** | Fornecedor com tax_withholding_category_id atribuido; categorias de retencao da empresa cadastradas; lancamentos taxable em tax_withholding_entry para o ano. |

## Status

**Objetivo.** Fornece um panorama do dominio de impostos da empresa: contagem de modelos, regras, categorias de retencao e fornecedores 1099 do ano corrente.

**Ações:**
- `status` — Retorna contagens agregadas de modelos, regras, categorias de retencao e vendors 1099 YTD da empresa.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id ou --company (resolve a empresa). |
| **Saídas** | templates, rules, withholding_categories e ytd_1099_vendors (distintos no ano corrente). |
| **Regras de negócio** | Empresa resolvida via resolve_company_id. Conta tax_template, tax_rule e tax_withholding_category por company_id; conta party_id distintos em tax_withholding_entry do ano corrente (UTC) cuja category pertence a empresa. |
| **Efeitos colaterais** | Nenhum (somente leitura) — apenas COUNTs e agregacoes. |
| **Pré-condições** | Empresa existente; tabelas de impostos/retencao presentes no banco. |

