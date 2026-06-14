# Faturamento por Uso — `erpclaw-billing`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-billing/db_query.py`. 10 funcionalidades · 22 ações.

## Medidores

**Objetivo.** Cadastrar e gerenciar medidores (pontos de consumo) vinculados a um cliente, com tipo de serviço, ponto/endereço de serviço, plano de tarifa opcional e ciclo de vida operacional.

**Ações:**
- `add-meter` — Registra um novo medidor para um cliente, gerando meter_number sequencial; status inicial fixo 'active'.
- `update-meter` — Atualiza configuracao do medidor: ponto de servico (--name -> service_point_id), status e/ou plano de tarifa.
- `get-meter` — Retorna o medidor com a ultima leitura (latest_reading) e a contagem total de leituras.
- `list-meters` — Lista medidores com join no nome do cliente e filtros por cliente, tipo de servico e status, paginado.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-meter: --customer-id, --meter-type (obrigatorios), --unit (vira metadata.uom), --name (ponto de servico), --address, --rate-plan-id, --install-date. update-meter: --meter-id + --name/--status/--rate-plan-id. list-meters: --customer-id, --meter-type, --status, --limit, --offset. |
| **Saídas** | add-meter/update-meter/get-meter retornam {meter:{...}} (get-meter adiciona latest_reading e reading_count). list-meters retorna {meters:[...], total_count, limit, offset, has_more}. |
| **Regras de negócio** | meter-type deve estar em VALID_SERVICE_TYPES (electricity, water, gas, telecom, saas, parking, rental, waste, custom). status deve estar em VALID_METER_STATUSES (active, disconnected, removed, suspended). Cliente deve existir; se informado, rate-plan deve existir. update-meter exige ao menos um campo; --name grava em service_point_id. company_id e herdado do cliente. |
| **Efeitos colaterais** | Insere/atualiza linha em meter; add-meter consome sequencia de naming (get_next_name) e grava metadata.uom. Registra auditoria (audit) em add-meter e update-meter. Nenhuma postagem em GL, SLE de estoque ou payment_ledger. |
| **Pré-condições** | Tabela company instalada (REQUIRED_TABLES). Cliente (customer) existente com company_id. Plano de tarifa existente se --rate-plan-id for informado. |

## Leituras

**Objetivo.** Registrar leituras de medidor calculando consumo automaticamente a partir da leitura anterior, com tipo e fonte da leitura, e manter o ultimo valor/data no medidor.

**Ações:**
- `add-meter-reading` — Registra leitura com calculo automatico de consumo (delta vs leitura anterior) e tratamento de rollover.
- `list-meter-readings` — Lista leituras de um medidor com filtros de data (from/to), ordenadas por data desc, paginado.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-meter-reading: --meter-id, --reading-date, --reading-value (obrigatorios), --reading-type (default 'actual'), --source (default 'manual'), --uom. list-meter-readings: --meter-id (obrigatorio), --from-date, --to-date, --limit, --offset. |
| **Saídas** | add-meter-reading retorna {reading:{...}} com previous_reading_value e consumption. list-meter-readings retorna {readings:[...], total_count, limit, offset, has_more}. |
| **Regras de negócio** | reading-type em VALID_READING_TYPES (actual, estimated, adjusted, rollover); source em VALID_READING_SOURCES (manual, smart_meter, api, import, estimated). consumption = leitura - leitura anterior; se delta < 0 trata como rollover (consumption = valor lido) e converte reading_type 'actual' em 'rollover'. UOM resolvida do argumento ou de metadata.uom do medidor. validated gravado como 0 (nao validada). |
| **Efeitos colaterais** | Insere linha em meter_reading e atualiza meter.last_reading_date/last_reading_value/updated_at na mesma transacao. Registra auditoria. Nenhuma postagem em GL, SLE de estoque ou payment_ledger. |
| **Pré-condições** | Medidor (meter) existente. Para calculo de consumo, leitura anterior registrada no medidor (last_reading_value). |

## Eventos de Uso

**Objetivo.** Ingerir eventos de uso (quantidade por timestamp) por medidor, de forma unitaria ou em lote, com deduplicacao por idempotency_key, para posterior agregacao no bill run.

**Ações:**
- `add-usage-event` — Registra um evento de uso unico; se idempotency_key ja existir, retorna o existente marcado deduplicated.
- `add-usage-events-batch` — Ingere em lote um array JSON de eventos, deduplicando por idempotency_key e acumulando erros por indice.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-usage-event: --meter-id, --event-date, --quantity (obrigatorios), --event-type (default 'usage'), --properties (metadata), --idempotency-key. add-usage-events-batch: --events (array JSON com meter_id, event_date, quantity, opcional event_type/idempotency_key/properties). |
| **Saídas** | add-usage-event retorna {usage_event:{...}} (ou {usage_event, deduplicated:true} se duplicado). add-usage-events-batch retorna {inserted, duplicates, errors:[{index,error}], total_processed}. |
| **Regras de negócio** | customer_id e derivado do medidor. Eventos sao gravados com processed=0 (nao processados). Deduplicacao: idempotency_key existente nao gera novo registro (retorna existente / conta como duplicate). No lote, registros sem meter_id, event_date ou quantity sao reportados em errors e pulados; medidor inexistente gera erro por indice. |
| **Efeitos colaterais** | Insere linha(s) em usage_event (processed=0). add-usage-event registra auditoria; o batch NAO registra auditoria. Nenhuma postagem em GL, SLE de estoque ou payment_ledger. |
| **Pré-condições** | Medidor (meter) existente para cada evento. Cliente vinculado ao medidor. |

## Planos de Tarifa

**Objetivo.** Criar e manter planos de precificacao (rate plans) com encargos base, encargo minimo, taxa de excedente e faixas (tiers), suportando varios modelos de cobranca.

**Ações:**
- `add-rate-plan` — Cria um plano de tarifa, opcionalmente com faixas (tiers) em array JSON; moeda default USD.
- `update-rate-plan` — Atualiza campos do plano e/ou substitui integralmente as faixas (delete + reinsert).
- `get-rate-plan` — Retorna o plano com suas faixas ordenadas por sort_order.
- `list-rate-plans` — Lista planos com filtro opcional por service_type, paginado.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-rate-plan: --name, --billing-model (obrigatorios), --service-type, --base-charge, --base-charge-period, --effective-from/--effective-to, --minimum-charge, --minimum-commitment, --overage-rate, --tiers (JSON). update-rate-plan: --rate-plan-id + name/base-charge/effective-to/minimum-charge/overage-rate e/ou --tiers. list: --service-type, --limit, --offset. |
| **Saídas** | add/update/get-rate-plan retornam {rate_plan:{..., tiers:[...]}}. list-rate-plans retorna {rate_plans:[...], total_count, limit, offset, has_more}. |
| **Regras de negócio** | billing-model deve estar em VALID_PLAN_TYPES (flat, tiered, time_of_use, demand, volume_discount, prepaid_credit, hybrid). base-charge-period (se informado) em VALID_BASE_CHARGE_PERIODS (monthly, quarterly, annually). effective_from default = data atual. Tiers com tier_start/tier_end/rate/fixed_charge/time_of_use_*/demand_type e sort_order = indice. update substitui TODAS as faixas quando --tiers e enviado; exige pelo menos um campo ou tiers. |
| **Efeitos colaterais** | Insere/atualiza rate_plan e insere/recria rate_tier (update faz DELETE de todas as faixas antes de reinserir). Registra auditoria em add e update. Nenhuma postagem em GL, SLE de estoque ou payment_ledger. |
| **Pré-condições** | Tabela company instalada. Nenhuma dependencia de cliente; planos sao globais (sem company_id no insert). |

## Cálculo de Tarifação

**Objetivo.** Calcular o encargo de um consumo contra um plano de tarifa (motor de rating puro), retornando encargo de uso, encargo base, total e detalhamento por faixa, sem persistir nada.

**Ações:**
- `rate-consumption` — Calcula os encargos de um consumo informado contra um plano (flat, tiered ou volume_discount) e retorna o breakdown.

| Campo | Detalhe |
|---|---|
| **Entradas** | --rate-plan-id, --consumption (obrigatorios). |
| **Saídas** | {calculation:{usage_charge, base_charge, total_charge, breakdown:[...], rate_plan_name, plan_type, consumption}}. |
| **Regras de negócio** | plan_type deve estar em VALID_SUPPORTED_PLAN_TYPES (flat, tiered, volume_discount); demais tipos retornam erro 'not yet supported'. flat: rate da 1a faixa x consumo. tiered: soma por bandas (band_width=tier_end-tier_start) consumindo o restante. volume_discount: aplica a taxa da faixa onde o consumo se enquadra (>=start e <end). total = base + usage_charge; se < minimum_charge, eleva ao minimo. Arredondamento via round_currency (ROUND_HALF_UP). |
| **Efeitos colaterais** | Nenhum (somente leitura) — funcao pura, nao grava nem audita. |
| **Pré-condições** | Plano de tarifa existente, do tipo flat/tiered/volume_discount, com faixas cadastradas (flat exige ao menos uma faixa). |

## Ciclos de Faturamento

**Objetivo.** Criar e consultar periodos de faturamento (billing_period) por cliente/medidor, controlando datas, consumo, encargos, ajustes, impostos e total, alem de gerar faturas a partir de periodos tarifados.

**Ações:**
- `create-billing-period` — Cria um periodo de faturamento 'open' validando sobreposicao com periodos nao-void existentes do medidor.
- `generate-invoices` — Gera faturas de venda a partir de periodos com status 'rated', chamando a skill selling se disponivel, e marca o periodo como 'invoiced'.
- `list-billing-periods` — Lista periodos com nome do cliente e numero do medidor, com filtros por cliente/medidor/status/datas, paginado.
- `get-billing-period` — Retorna o periodo com nomes de cliente/medidor/plano e a lista de ajustes.

| Campo | Detalhe |
|---|---|
| **Entradas** | create-billing-period: --customer-id, --meter-id, --from-date, --to-date (obrigatorios), --rate-plan-id (senao usa o do medidor). generate-invoices: --billing-period-ids (array JSON). list: --customer-id/--meter-id/--status/--from-date/--to-date/--limit/--offset. get: --billing-period-id. |
| **Saídas** | create/get retornam {billing_period:{...}} (get inclui adjustments). generate-invoices retorna {invoiced, results:[{billing_period_id, invoice_id, status}]}. list retorna {billing_periods:[...], total_count, limit, offset, has_more}. |
| **Regras de negócio** | create exige plano (argumento ou do medidor) existente; rejeita periodo sobreposto (mesmo medidor, status != void, com interseccao de datas). Periodo nasce 'open' com totais zerados. status validos em VALID_BILLING_PERIOD_STATUSES (open, rated, invoiced, paid, disputed, void). generate-invoices so processa periodos 'rated'; demais status retornam erro no item. |
| **Efeitos colaterais** | create-billing-period insere billing_period e registra auditoria. generate-invoices INVOCA via subprocess a skill selling (add-sales-invoice) — efeito colateral real podendo criar sales_invoice no dominio de vendas (e seus efeitos a jusante) — e atualiza billing_period para 'invoiced' com invoice_id/invoiced_at. Nao posta diretamente em GL/SLE/payment_ledger nesta skill. |
| **Pré-condições** | Cliente e medidor existentes; plano de tarifa existente. Para faturar: periodo em status 'rated'; tabela sales_invoice e script da skill selling presentes (senao invoice_id fica nulo mas status vira 'invoiced'). |

## Bill Run

**Objetivo.** Executar o processamento de faturamento de uma empresa: agregar consumo de leituras e eventos nao processados, tarifar e criar/atualizar periodos de faturamento como 'rated'.

**Ações:**
- `run-billing` — Roda o faturamento de todos os medidores ativos com plano da empresa: agrega consumo, calcula encargos e gera/atualiza periodos 'rated'.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id, --billing-date (obrigatorios); --from-date (default billing-date menos 30 dias); --to-date (default billing-date). |
| **Saídas** | {periods_created, period_ids:[...], total_billed} (ou mensagem se nao houver clientes/medidores). |
| **Regras de negócio** | Processa apenas medidores com status 'active' e rate_plan_id nao nulo dos clientes da empresa. Pula medidores ja faturados no periodo (status rated/invoiced/paid). Plano deve ter plan_type suportado (flat/tiered/volume_discount). Consumo total = soma de meter_reading.consumption no periodo + soma de usage_event.quantity nao processados no periodo. subtotal = total_charge (antes de ajustes). Periodo 'open' existente e atualizado para 'rated'; senao cria novo 'rated'. |
| **Efeitos colaterais** | Insere ou atualiza linhas em billing_period (status 'rated', rated_at). Marca usage_event como processed=1 e vincula billing_period_id. Registra auditoria com periodos e total faturado. Nao posta em GL/SLE/payment_ledger (a faturacao contabil ocorre em generate-invoices). |
| **Pré-condições** | Empresa (company) existente. Clientes com medidores 'active' e plano de tarifa atribuido. Leituras com consumo e/ou eventos de uso nao processados no intervalo. |

## Ajustes

**Objetivo.** Aplicar ajustes financeiros (credito, multa, deposito, reembolso, proracao, desconto, penalidade, write-off) a um periodo de faturamento, recalculando os totais do periodo.

**Ações:**
- `add-billing-adjustment` — Registra um ajuste no periodo e recalcula adjustments_total, subtotal e grand_total.

| Campo | Detalhe |
|---|---|
| **Entradas** | --billing-period-id, --amount, --adjustment-type (obrigatorios); --reason, --approved-by. |
| **Saídas** | {adjustment:{..., updated_grand_total}}. |
| **Regras de negócio** | adjustment-type deve estar em VALID_ADJUSTMENT_TYPES (credit, late_fee, deposit, refund, proration, discount, penalty, write_off). Periodo deve existir. Recalculo: adjustments_total = soma (DecimalSum) dos ajustes do periodo; subtotal = base_charge + usage_charge + adjustments_total; grand_total = subtotal + tax_amount; tudo via round_currency. |
| **Efeitos colaterais** | Insere linha em billing_adjustment e atualiza billing_period (adjustments_total, subtotal, grand_total, updated_at). Registra auditoria. Nenhuma postagem em GL/SLE/payment_ledger. |
| **Pré-condições** | Periodo de faturamento (billing_period) existente. Tabela billing_adjustment disponivel. |

## Créditos Pré-pagos

**Objetivo.** Registrar compromissos pre-pagos (saldo de credito) de um cliente com validade e consultar o saldo remanescente agregado.

**Ações:**
- `add-prepaid-credit` — Registra um saldo pre-pago para o cliente (valor original = remanescente), status 'active'.
- `get-prepaid-balance` — Consulta os saldos pre-pagos do cliente e soma o remanescente dos creditos ativos.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-prepaid-credit: --customer-id, --amount, --valid-until (obrigatorios), --rate-plan-id (opcional). get-prepaid-balance: --customer-id. |
| **Saídas** | add-prepaid-credit retorna {prepaid_credit:{...}}. get-prepaid-balance retorna {customer_id, active_credits, total_remaining, balances:[...]}. |
| **Regras de negócio** | Cliente deve existir. Se --rate-plan-id nao informado, usa um plano com plan_type 'prepaid_credit' ou, na ausencia, o primeiro plano disponivel; se nenhum existir, erro. period_start = data atual, period_end = valid-until. original_amount = remaining_amount = amount; overage_amount=0; status 'active'. status validos em VALID_PREPAID_STATUSES (active, exhausted, expired). get soma remaining_amount apenas de creditos 'active'. |
| **Efeitos colaterais** | Insere linha em prepaid_credit_balance e registra auditoria. get-prepaid-balance e somente leitura. Nenhuma postagem em GL/SLE/payment_ledger. |
| **Pré-condições** | Cliente existente. Ao menos um rate_plan cadastrado quando nao se informa --rate-plan-id. |

## Status

**Objetivo.** Fornecer um resumo do dominio de faturamento: contagens de medidores e periodos por status, planos, eventos nao processados e saldos pre-pagos, opcionalmente filtrado por empresa.

**Ações:**
- `status` — Retorna metricas agregadas de medidores, periodos, planos, eventos nao processados e creditos pre-pagos.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id (opcional; restringe aos clientes da empresa). |
| **Saídas** | {meters:{status:cnt}, meters_total, billing_periods:{status:cnt}, billing_periods_total, rate_plans_total, unprocessed_events, prepaid_balances}. |
| **Regras de negócio** | Se --company-id informado, valida a empresa e restringe medidores/periodos/eventos/pre-pagos aos clientes daquela empresa (IN dinamico). Contagens agrupadas por status para medidores e periodos. unprocessed_events conta usage_event com processed=0. |
| **Efeitos colaterais** | Nenhum (somente leitura). |
| **Pré-condições** | Tabela company instalada. Se filtrar, empresa existente. |

