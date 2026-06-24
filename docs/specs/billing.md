# Faturamento por uso — `glue-billing`

> Spec funcional por ação. Gerada de `scripts/glue-billing/db_query.py`. 10 funcionalidades · 22 ações.

## Medidores

**Objetivo.** Cadastrar, atualizar, consultar e listar medidores (meters) vinculados a clientes e planos de tarifa.

### `add-meter`

Registra um novo medidor para um cliente.

| | |
|---|---|
| **Entradas** | --customer-id (obrigatório); --meter-type (obrigatório, deve estar em electricity/water/gas/telecom/saas/parking/rental/waste/custom); --rate-plan-id (opcional, validado se informado); --unit (opcional, vira metadata.uom); --name (opcional, gravado em service_point_id); --address (opcional, service_point_address); --install-date (opcional). |
| **Saídas** | meter: linha completa do medidor inserido (id, meter_number, customer_id, service_type, status, etc.). |
| **Regras** | Valida meter_type contra VALID_SERVICE_TYPES; exige cliente existente; valida rate_plan_id se informado; gera meter_number via get_next_name; status inicial fixado em 'active'. |
| **Efeitos colaterais** | INSERT em meter; conn.commit; audit_log via audit('add-meter'). Sem postagens contábeis. |
| **Pré-condições** | Cliente existente; tabela meter e (se usado) rate_plan. |

### `update-meter`

Atualiza configuração de um medidor existente.

| | |
|---|---|
| **Entradas** | --meter-id (obrigatório); --name (opcional, atualiza service_point_id); --status (opcional, deve estar em active/disconnected/removed/suspended); --rate-plan-id (opcional, validado se informado). |
| **Saídas** | meter: linha completa atualizada. |
| **Regras** | Exige medidor existente; valida status contra VALID_METER_STATUSES; valida rate_plan_id se informado; erro 'No fields to update' se nenhum campo fornecido; sempre seta updated_at. |
| **Efeitos colaterais** | UPDATE em meter; conn.commit; audit_log via audit('update-meter') com old_values. Sem postagens contábeis. |
| **Pré-condições** | Medidor existente; rate plan existente se informado. |

### `get-meter`

Retorna um medidor com sua última leitura e contagem de leituras.

| | |
|---|---|
| **Entradas** | --meter-id (obrigatório). |
| **Saídas** | meter: linha do medidor acrescida de latest_reading (última leitura por reading_date desc, ou null) e reading_count. |
| **Regras** | Exige medidor existente; leitura mais recente ordenada por reading_date desc limit 1. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Medidor existente. |

### `list-meters`

Lista medidores com filtros opcionais e nome do cliente.

| | |
|---|---|
| **Entradas** | --customer-id, --meter-type, --status (todos filtros opcionais); --limit (default 20), --offset (default 0). |
| **Saídas** | meters (com customer_name via left join), total_count, limit, offset, has_more. |
| **Regras** | Filtros aplicados em count e data query; ordena por created_at desc; paginação via limit/offset. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabelas meter e customer. |

## Leituras

**Objetivo.** Registrar leituras de medidor com cálculo automático de consumo e listar o histórico de leituras.

### `add-meter-reading`

Registra uma leitura de medidor calculando o consumo automaticamente.

| | |
|---|---|
| **Entradas** | --meter-id (obrigatório); --reading-date (obrigatório); --reading-value (obrigatório); --reading-type (opcional, default 'actual', em actual/estimated/adjusted/rollover); --source (opcional, default 'manual', em manual/smart_meter/api/import/estimated); --uom (opcional, herda de metadata.uom do medidor). |
| **Saídas** | reading: linha completa da leitura inserida (consumption, previous_reading_value, reading_type, etc.). |
| **Regras** | Exige medidor existente; valida reading_type e source; consumption = reading_value - last_reading_value; se diff<0 trata rollover (consumption=reading_value e reading_type vira 'rollover' se era 'actual'); validated gravado como 0. |
| **Efeitos colaterais** | INSERT em meter_reading; UPDATE meter (last_reading_date, last_reading_value, updated_at); conn.commit; audit_log via audit('add-meter-reading'). Sem postagens contábeis. |
| **Pré-condições** | Medidor existente. |

### `list-meter-readings`

Lista leituras de um medidor com filtros de data opcionais.

| | |
|---|---|
| **Entradas** | --meter-id (obrigatório); --from-date, --to-date (filtros opcionais sobre reading_date); --limit (default 20), --offset (default 0). |
| **Saídas** | readings, total_count, limit, offset, has_more. |
| **Regras** | Exige meter-id; aplica filtros de data; ordena por reading_date desc; paginação. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela meter_reading. |

## Eventos de Uso

**Objetivo.** Ingerir eventos de consumo individuais ou em lote, com deduplicação por chave de idempotência.

### `add-usage-event`

Registra um único evento de uso para um medidor.

| | |
|---|---|
| **Entradas** | --meter-id (obrigatório); --event-date (obrigatório, vira timestamp); --quantity (obrigatório); --event-type (opcional, default 'usage'); --properties (opcional, metadata); --idempotency-key (opcional, dedup). |
| **Saídas** | usage_event: linha completa do evento; se duplicado, retorna o evento existente com deduplicated=true. |
| **Regras** | Exige medidor existente; customer_id derivado do medidor; se idempotency_key já existir, retorna evento existente sem inserir (deduplicated); processed gravado como 0. |
| **Efeitos colaterais** | INSERT em usage_event (exceto quando deduplicado); conn.commit; audit_log via audit('add-usage-event'). Sem postagens contábeis. |
| **Pré-condições** | Medidor existente. |

### `add-usage-events-batch`

Ingere eventos de uso em massa a partir de um array JSON.

| | |
|---|---|
| **Entradas** | --events (obrigatório, array JSON; cada item: meter_id, event_date, quantity obrigatórios, event_type default 'usage', idempotency_key e properties opcionais). |
| **Saídas** | inserted, duplicates, errors (lista com index/erro), total_processed. |
| **Regras** | Valida que --events é array não vazio; por item valida campos obrigatórios e existência do medidor (erros acumulados, não abortam o lote); pula duplicados por idempotency_key; processed=0. |
| **Efeitos colaterais** | INSERT em usage_event para cada item válido; um único conn.commit ao final. NÃO grava audit_log. Sem postagens contábeis. |
| **Pré-condições** | Medidores referenciados existentes; tabela usage_event. |

## Planos de Tarifa

**Objetivo.** Criar, atualizar, consultar e listar planos de tarifa (rate plans) com suas faixas (tiers).

### `add-rate-plan`

Cria um plano de tarifa/preço com faixas opcionais.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --billing-model (obrigatório, em flat/tiered/time_of_use/demand/volume_discount/prepaid_credit/hybrid); --service-type, --base-charge, --base-charge-period (em monthly/quarterly/annually), --effective-from (default hoje), --effective-to, --minimum-charge, --minimum-commitment, --overage-rate (opcionais); --tiers (array JSON opcional). |
| **Saídas** | rate_plan: linha do plano com array tiers. |
| **Regras** | Valida billing_model contra VALID_PLAN_TYPES e base_charge_period; currency fixado em 'USD'; tiers inseridos com sort_order pela ordem do array; effective_from default = data atual. |
| **Efeitos colaterais** | INSERT em rate_plan e (se houver) rate_tier; conn.commit; audit_log via audit('add-rate-plan'). Sem postagens contábeis. |
| **Pré-condições** | Tabelas rate_plan e rate_tier. |

### `update-rate-plan`

Atualiza configuração e/ou faixas de um plano de tarifa.

| | |
|---|---|
| **Entradas** | --rate-plan-id (obrigatório); --name, --base-charge, --effective-to, --minimum-charge, --overage-rate (opcionais); --tiers (array JSON opcional — substitui todas as faixas). |
| **Saídas** | rate_plan: linha atualizada com array tiers. |
| **Regras** | Exige plano existente; erro 'No fields to update' se nenhum campo nem tiers; se --tiers fornecido, DELETE todas as faixas e reinsere; seta updated_at quando há campos escalares. |
| **Efeitos colaterais** | UPDATE em rate_plan; DELETE+INSERT em rate_tier se --tiers; conn.commit; audit_log via audit('update-rate-plan') com old_values. Sem postagens contábeis. |
| **Pré-condições** | Plano de tarifa existente. |

### `get-rate-plan`

Retorna um plano de tarifa com suas faixas.

| | |
|---|---|
| **Entradas** | --rate-plan-id (obrigatório). |
| **Saídas** | rate_plan: linha do plano com array tiers (ordenado por sort_order). |
| **Regras** | Exige plano existente. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Plano de tarifa existente. |

### `list-rate-plans`

Lista planos de tarifa com filtro opcional por tipo de serviço.

| | |
|---|---|
| **Entradas** | --service-type (filtro opcional); --limit (default 20), --offset (default 0). |
| **Saídas** | rate_plans, total_count, limit, offset, has_more. |
| **Regras** | Filtro por service_type; ordena por created_at desc; paginação. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela rate_plan. |

## Cálculo de Tarifação

**Objetivo.** Calcular o valor cobrado para um consumo contra um plano de tarifa, sem persistir nada.

### `rate-consumption`

Calcula os encargos de um consumo contra um plano de tarifa (função pura).

| | |
|---|---|
| **Entradas** | --rate-plan-id (obrigatório); --consumption (obrigatório). |
| **Saídas** | calculation: usage_charge, base_charge, total_charge, breakdown (por faixa), rate_plan_name, plan_type, consumption. |
| **Regras** | Exige plano existente; só suporta plan_type em flat/tiered/volume_discount (erro caso contrário); flat usa tiers[0]; tiered acumula por banda; volume_discount aplica a taxa da faixa correspondente; aplica minimum_charge se total < mínimo. |
| **Efeitos colaterais** | nenhum (leitura/cálculo, não persiste). |
| **Pré-condições** | Plano de tarifa existente com faixas compatíveis. |

## Ciclos de Faturamento

**Objetivo.** Criar períodos de faturamento (billing periods), consultar e listar com totais e ajustes.

### `create-billing-period`

Cria um período de faturamento para um cliente/medidor.

| | |
|---|---|
| **Entradas** | --customer-id (obrigatório); --meter-id (obrigatório); --from-date (obrigatório); --to-date (obrigatório); --rate-plan-id (opcional, senão usa o do medidor). |
| **Saídas** | billing_period: linha criada com totais zerados e status 'open'. |
| **Regras** | Exige cliente e medidor existentes; rate_plan_id = informado ou do medidor (erro se nenhum); valida plano; rejeita período sobreposto (mesmo meter, status != void, datas que se cruzam); status inicial 'open' e todos os valores em '0'. |
| **Efeitos colaterais** | INSERT em billing_period; conn.commit; audit_log via audit('create-billing-period'). Sem postagens contábeis. |
| **Pré-condições** | Cliente, medidor e plano de tarifa existentes; nenhum período sobreposto. |

### `list-billing-periods`

Lista períodos de faturamento com filtros opcionais.

| | |
|---|---|
| **Entradas** | --customer-id, --meter-id, --status, --from-date (sobre period_start), --to-date (sobre period_end) (filtros opcionais); --limit (default 20), --offset (default 0). |
| **Saídas** | billing_periods (com customer_name e meter_number), total_count, limit, offset, has_more. |
| **Regras** | Aplica filtros em count e data; ordena por created_at desc; paginação. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabelas billing_period, customer, meter. |

### `get-billing-period`

Retorna um período de faturamento com seus ajustes.

| | |
|---|---|
| **Entradas** | --billing-period-id (obrigatório). |
| **Saídas** | billing_period: linha (com customer_name, meter_number, rate_plan_name) e array adjustments. |
| **Regras** | Exige período existente; ajustes ordenados por created_at. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Período de faturamento existente. |

## Bill Run

**Objetivo.** Executar o processo de faturamento em lote (agregar consumo, tarifar, criar/atualizar períodos) e gerar faturas a partir de períodos tarifados.

### `run-billing`

Executa o bill run: agrega consumo, tarifa e cria/atualiza períodos para todos os medidores ativos da empresa.

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --billing-date (obrigatório); --from-date (opcional, default billing-date menos 30 dias); --to-date (opcional, default billing-date). |
| **Saídas** | periods_created, period_ids, total_billed (arredondado). |
| **Regras** | Exige empresa existente; processa medidores 'active' com rate_plan_id; pula medidores já com período 'rated'/'invoiced'/'paid'; só tarifa plan_type suportado (flat/tiered/volume_discount); soma consumo de meter_reading e de usage_event não processados na janela; cria período novo ou atualiza período 'open' existente para status 'rated'. |
| **Efeitos colaterais** | INSERT ou UPDATE em billing_period (status -> 'rated', seta rated_at); UPDATE em usage_event (processed=1, billing_period_id); conn.commit; audit_log via audit('run-billing'). Sem postagens contábeis. |
| **Pré-condições** | Empresa existente com clientes, medidores ativos com plano e leituras/eventos na janela. |

### `generate-invoices`

Cria faturas de venda a partir de períodos de faturamento tarifados.

| | |
|---|---|
| **Entradas** | --billing-period-ids (obrigatório, array JSON de IDs). |
| **Saídas** | invoiced (contagem), results (por período: billing_period_id, invoice_id, status ou error). |
| **Regras** | Valida array JSON; processa só períodos com status 'rated' (senão registra erro); cria sales_invoice chamando o script de selling via subprocess se a tabela sales_invoice existir (best-effort, invoice_id pode ficar null); sempre marca o período como 'invoiced'. |
| **Efeitos colaterais** | Subprocess opcional para selling (add-sales-invoice) que pode inserir sales_invoice/gl_entry no outro skill; UPDATE em billing_period (status -> 'invoiced', invoiced_at, invoice_id); conn.commit. NÃO grava audit_log próprio. |
| **Pré-condições** | Períodos de faturamento com status 'rated'; opcionalmente skill selling instalado para a fatura real. |

## Ajustes

**Objetivo.** Adicionar ajustes (crédito, multa, desconto, etc.) a um período de faturamento e recalcular seus totais.

### `add-billing-adjustment`

Adiciona um ajuste a um período de faturamento e recalcula os totais.

| | |
|---|---|
| **Entradas** | --billing-period-id (obrigatório); --amount (obrigatório); --adjustment-type (obrigatório, em credit/late_fee/deposit/refund/proration/discount/penalty/write_off); --reason, --approved-by (opcionais). |
| **Saídas** | adjustment: linha do ajuste inserido acrescida de updated_grand_total. |
| **Regras** | Valida adjustment_type contra VALID_ADJUSTMENT_TYPES; exige período existente; recalcula adjustments_total (soma via DecimalSum), subtotal = base+usage+adj_total, grand_total = subtotal+tax. |
| **Efeitos colaterais** | INSERT em billing_adjustment; UPDATE em billing_period (adjustments_total, subtotal, grand_total, updated_at); conn.commit; audit_log via audit('add-billing-adjustment'). Sem postagens contábeis. |
| **Pré-condições** | Período de faturamento existente. |

## Créditos Pré-pagos

**Objetivo.** Registrar compromissos pré-pagos (prepaid credits) e consultar o saldo remanescente do cliente.

### `add-prepaid-credit`

Registra um compromisso/saldo pré-pago para um cliente.

| | |
|---|---|
| **Entradas** | --customer-id (obrigatório); --amount (obrigatório); --valid-until (obrigatório, vira period_end); --rate-plan-id (opcional; senão usa um plano prepaid_credit ou o primeiro disponível). |
| **Saídas** | prepaid_credit: linha inserida (original_amount, remaining_amount, status 'active', etc.). |
| **Regras** | Exige cliente existente; resolve rate_plan_id (informado, ou primeiro plano prepaid_credit, ou primeiro plano; erro se nenhum existir); period_start = data atual; remaining_amount = original_amount; overage_amount '0'; status 'active'. |
| **Efeitos colaterais** | INSERT em prepaid_credit_balance; conn.commit; audit_log via audit('add-prepaid-credit'). Sem postagens contábeis. |
| **Pré-condições** | Cliente existente; pelo menos um rate plan existente. |

### `get-prepaid-balance`

Consulta os créditos pré-pagos remanescentes de um cliente.

| | |
|---|---|
| **Entradas** | --customer-id (obrigatório). |
| **Saídas** | customer_id, active_credits, total_remaining (soma dos status 'active', arredondado), balances (todos os registros). |
| **Regras** | Exige customer-id; soma remaining_amount apenas dos saldos com status 'active'; lista ordenada por created_at desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela prepaid_credit_balance. |

## Status

**Objetivo.** Fornecer um resumo geral do estado do faturamento (medidores, períodos, eventos, planos, pré-pagos).

### `status`

Retorna um resumo do faturamento, opcionalmente filtrado por empresa.

| | |
|---|---|
| **Entradas** | --company-id (opcional; se informado, valida empresa e restringe contagens aos clientes dela). |
| **Saídas** | meters (contagem por status), meters_total, billing_periods (por status), billing_periods_total, rate_plans_total, unprocessed_events, prepaid_balances. |
| **Regras** | Se company-id, exige empresa existente e filtra por seus customer_ids (IN dinâmico); conta medidores por status, períodos por status, eventos não processados (processed=0), planos e saldos pré-pagos. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabelas meter, billing_period, usage_event, rate_plan, prepaid_credit_balance; empresa existente se filtrada. |

