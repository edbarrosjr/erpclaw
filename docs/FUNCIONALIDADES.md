# Funcionalidades do Glue por módulo

> Mapa do que o ERP já faz, verificado contra o código (`scripts/*/db_query.py`) e o catálogo (`scripts/module_registry.json`).
>
> - **Parte A — Núcleo:** está fisicamente no repositório e executa hoje (15 domínios, ~469 ações).
> - **Parte B — Catálogo de expansão:** módulos do registry (46 módulos / ~3.169 ações). Neste fork **air-gapped o código dos verticais não vem junto** — é catálogo (eram baixados do upstream; ver `CHANGELOG` 4.9.0).
>
> Visual interativo (offline, SVG puro): [`catalogo-visual.html`](catalogo-visual.html) — treemap/sunburst por vertical, área = nº de ações.

---

## Parte A — Núcleo do ERP (15 domínios)

### 1. Configuração & Admin — `erpclaw-setup` · ~61 ações
Administração geral: empresas, moedas, RBAC, credenciais, backups, schema.
- **Gestão de Empresas** — empresas com moeda, país, ano fiscal, contas padrão (`setup-company`, `update-company`, `list-companies`)
- **Moedas e Câmbio** — taxas manuais ou via API (`add-currency`, `add-exchange-rate`, `fetch-exchange-rates`)
- **Condições de Pagamento** — prazos com desconto por antecipação (`add-payment-terms`)
- **Unidades de Medida** — UOMs e conversões (`add-uom`, `add-uom-conversion`)
- **Usuários e Acessos (RBAC)** — usuários, papéis, senhas web (`add-user`, `assign-role`, `set-password`)
- **Papéis e Permissões** — papéis customizados e seed (`add-role`, `seed-permissions`)
- **Integração Telegram** — vincula usuários a IDs do Telegram (`link-telegram-user`, `check-telegram-permission`)
- **Credenciais de Integração** — cifradas (Stripe/Shopify) (`set-credential`, `migrate-credentials`)
- **Campos Personalizados (UDF)** — campos extras em tabelas do núcleo (`add-custom-field`, `set-custom-field-value`)
- **Registros de Tipos/Status** — tipos de conta e voucher em runtime (`add-account-type`, `add-voucher-type`)
- **Backup e Restauração** — backups cifrados, verify, restore, retenção (`backup-database`, `restore-database`)
- **Schema e Migrações** — init do banco, migrações, versão (`initialize-database`, `migrate`)
- **Dados Padrão e Onboarding** — seed, empresa demo, tutorial (`seed-defaults`, `onboarding-step`)
- **Config. Regionais/Avançadas** — formatos regionais, conta de adiantamento (`set-advance-account`)
- **Auditoria/Status/Chave-Mestra** — log de auditoria, status, import da master-key (`get-audit-log`, `status`)

### 2. Contabilidade — `erpclaw-gl` · ~31 ações
Razão geral, plano de contas, períodos fiscais, dimensões e orçamentos.
- **Plano de Contas** — CRUD e montagem por template (`setup-chart-of-accounts`, `add-account`)
- **Congelamento de Contas** (`freeze-account`, `unfreeze-account`)
- **Lançamentos no Razão** — posta/estorna/lista (`post-gl-entries`, `reverse-gl-entries`)
- **Saldos de Conta** — saldo numa data, filtrável por parte (`get-account-balance`)
- **Anos Fiscais** — com validação de sobreposição (`add-fiscal-year`)
- **Fechamento de Período** — valida/fecha/reabre exercício (`close-fiscal-year`, `reopen-fiscal-year`)
- **Centros de Custo** — hierárquicos (`add-cost-center`)
- **Dimensões Contábeis** — multidimensional do GL (`add-dimension`, `deactivate-dimension`)
- **Orçamentos** — orçado com realizado/variação (`add-budget`)
- **Séries de Numeração** (`seed-naming-series`, `next-series`)
- **Importação** — plano de contas e saldos via CSV (`import-chart-of-accounts`, `import-opening-balances`)
- **Integridade e Câmbio** — cadeia SHA-256, reavaliação de moeda (`check-gl-integrity`, `revalue-foreign-balances`)

### 3. Lançamentos — `erpclaw-journals` · ~17 ações
Lançamentos manuais (rascunho→submissão→cancelamento), recorrência, intercompany.
- **Criação/edição** — partidas balanceadas (`add-journal-entry`, `update-journal-entry`)
- **Consulta/listagem** (`get-journal-entry`, `list-journal-entries`)
- **Ciclo de vida** — submete (posta GL) / cancela (estorna) (`submit-journal-entry`, `cancel-journal-entry`)
- **Retificação** — cancela original e cria rascunho vinculado (`amend-journal-entry`)
- **Exclusão/duplicação** (`delete-journal-entry`, `duplicate-journal-entry`)
- **Intercompany** — lançamentos pareados entre empresas (`create-intercompany-je`)
- **Modelos recorrentes** — CRUD + processamento idempotente (`add-recurring-template`, `process-recurring`)

### 4. Vendas — `erpclaw-selling` · ~60 ações
Order-to-cash: clientes → cotação → pedido → entrega → fatura → cobrança.
- **Clientes** — CRUD, importação, valores em aberto (`add-customer`, `import-customers`)
- **Cotações** — ciclo e conversão em pedido (`add-quotation`, `convert-quotation-to-so`)
- **Pedidos de Venda** — criar/confirmar/cancelar/encerrar (`submit-sales-order`, `close-sales-order`)
- **Emendas de Pedido** (`amend-sales-order`, `get-amendment-history`)
- **Notas de Entrega** — baixa de estoque ao submeter (`create-delivery-note`, `submit-delivery-note`)
- **Faturas de Venda** — lançamento GL/COGS (`create-sales-invoice`, `submit-sales-invoice`)
- **Notas de Crédito/Estorno** (`create-credit-note`, `update-invoice-outstanding`)
- **Crédito e Cobrança (Dunning)** — limite, hold, ciclos (`check-credit-limit`, `run-dunning-cycle`)
- **Parceiros de Venda** (`add-sales-partner`)
- **Faturas Recorrentes** (`generate-recurring-invoices`)
- **Pedidos Guarda-chuva (Blanket)** (`add-blanket-order`, `create-so-from-blanket`)
- **Faturamento Intercompany** (`create-intercompany-invoice`)
- **Drop Ship / Romaneio** (`create-drop-ship-order`, `add-packing-slip`)

### 5. Compras — `erpclaw-buying` · ~48 ações
Procure-to-pay: fornecedores → requisição → RFQ → pedido → recebimento → fatura.
- **Fornecedores** — CRUD, importação, dados fiscais (`add-supplier`, `import-suppliers`)
- **Requisições de Material** (`add-material-request`)
- **Cotações e RFQ** — pedir, registrar e comparar (`add-rfq`, `compare-supplier-quotations`)
- **Pedidos de Compra** — CRUD/submit/cancel/close (`submit-purchase-order`)
- **Recebimentos (GRN)** — parciais/totais com lançamento de estoque (`create-purchase-receipt`)
- **Faturas de Compra** — contas a pagar (`create-purchase-invoice`, `submit-purchase-invoice`)
- **Notas de Débito** (`create-debit-note`)
- **Custos de Importação (Landed Cost)** (`add-landed-cost-voucher`)
- **Blanket PO** (`add-blanket-po`, `create-po-from-blanket`)
- **Conversão p/ PO** — de venda ou blanket (`create-po-from-so`)
- **Contas Recorrentes** (`generate-recurring-bills`)
- **Políticas de Compra** — tolerância GRN, 3-way match, UOM (`update-three-way-match-policy`)

### 6. Estoque — `erpclaw-inventory` · ~45 ações
Itens, depósitos, movimentações, valoração FIFO, lotes/série, preços, reconciliação.
- **Itens** — CRUD, importação, busca aproximada (`add-item`, `resolve-item`, `import-items`)
- **Grupos de Itens** (`add-item-group`)
- **Depósitos** — com conta contábil (`add-warehouse`)
- **Movimentações** — recebimento/baixa/transferência/produção (SLE+GL) (`submit-stock-entry`)
- **Razão de Estoque (SLE cross-skill)** (`create-stock-ledger-entries`)
- **Saldos e Relatórios** (`stock-balance-report`, `stock-ledger-report`)
- **Lotes** (`add-batch`)
- **Números de Série** (`add-serial-number`)
- **Preços e Regras** (`add-price-list`, `add-pricing-rule`)
- **Reconciliação** — inventário físico (`add-stock-reconciliation`)
- **Revaloração** — ajuste de taxa com impacto contábil (`revalue-stock`)
- **Reposição/Projeção** (`check-reorder`, `get-projected-qty`)
- **Variantes** — cor/tamanho (`generate-item-variants`)
- **Fornecedores de Item** (`add-item-supplier`)

### 7. Faturamento por uso — `erpclaw-billing` · ~22 ações
Billing medido/usage: medidores, leituras, planos de tarifa, bill runs.
- **Medidores** (`add-meter`) · **Leituras** (`add-meter-reading`)
- **Eventos de Uso** — individual/lote idempotente (`add-usage-event`, `add-usage-events-batch`)
- **Planos de Tarifa** — flat/escalonado/volume (`add-rate-plan`)
- **Cálculo de Tarifação** (`rate-consumption`)
- **Ciclos de Faturamento** (`create-billing-period`)
- **Bill Run** — agrega, tarifa, gera faturas (`run-billing`, `generate-invoices`)
- **Ajustes** — crédito/multa/desconto (`add-billing-adjustment`)
- **Créditos Pré-pagos** (`add-prepaid-credit`, `get-prepaid-balance`)

### 8. Impostos — `erpclaw-tax` · ~18 ações
Modelos, regras, cálculo em cascata, retenção e 1099.
- **Modelos de Impostos** (`add-tax-template`) · **Categorias** (`add-tax-category`)
- **Regras de Tributação** (`add-tax-rule`) · **Resolução** (`resolve-tax-template`)
- **Cálculo** — cascata por item (`calculate-tax`) · **Impostos por Item** (`add-item-tax-template`)
- **Retenção na Fonte** (`add-tax-withholding-category`, `record-withholding-entry`)
- **Relatórios 1099** (`record-1099-payment`, `generate-1099-data`)

### 9. Pagamentos — `erpclaw-payments` · ~16 ações
Pagamentos/recebimentos, alocação, razão (PLE) e conciliação.
- **Cadastro/Listagem** (`add-payment`, `list-payments`)
- **Ciclo de Vida** — submit (GL+PLE) / cancel (`submit-payment`)
- **Alocação a Faturas** (`allocate-payment`, `apply-advance-to-invoice`)
- **Adiantamentos** (`get-unallocated-payments`, `list-open-advances`)
- **Razão de Pagamentos (PLE)** (`create-payment-ledger-entry`, `get-outstanding`)
- **Conciliação** — FIFO (`reconcile-payments`) · **Conciliação Bancária** (`bank-reconciliation`)

### 10. Relatórios — `erpclaw-reports` · ~22 ações
Relatórios financeiros (somente leitura) sobre o razão.
- **DRE** (`profit-and-loss`, `comparative-pl`) · **Balanço** (`balance-sheet`) · **Balancete** (`trial-balance`)
- **Fluxo de Caixa** (`cash-flow`) · **Razão** (`general-ledger`, `gl-summary`)
- **Razão por Parceiro** (`party-ledger`, `payment-summary`)
- **Aging AR/AP** (`ar-aging`, `ap-aging`) · **Faturas Vencidas** (`check-overdue`)
- **Orçado vs Realizado** (`budget-vs-actual`, `budget-variance`)
- **Relatórios Dimensionais** (`multi-dim-trial-balance`) · **Resumo de Impostos** (`tax-summary`)
- **Eliminações Intercompany** (`run-elimination`)

### 11. Recursos Humanos — `erpclaw-hr` · ~39 ações
Funcionários, org, férias, ponto, despesas, turnos, documentos.
- **Funcionários** (`add-employee`) · **Estrutura Org.** (`add-department`, `add-designation`)
- **Tipos/Alocação de Férias** (`add-leave-type`, `get-leave-balance`)
- **Solicitações de Férias** — fluxo de aprovação (`add-leave-application`, `approve-leave`)
- **Ponto** (`mark-attendance`, `bulk-mark-attendance`) · **Regularização** (`apply-attendance-regularization`)
- **Feriados** (`add-holiday-list`)
- **Reembolsos de Despesas** — com lançamento contábil (`submit-expense-claim`, `approve-expense-claim`)
- **Turnos** (`assign-shift`) · **Documentos** — alerta de vencimento (`check-expiring-documents`)
- **Eventos de Carreira** (`record-lifecycle-event`)

### 12. Folha de Pagamento — `erpclaw-payroll` · ~30 ações *(US payroll)*
Componentes/estruturas salariais, holerites, impostos (FICA/IR/FUTA), penhoras, W-2, ACH.
- **Componentes/Estruturas/Atribuições Salariais** (`add-salary-component`, `add-salary-structure`, `add-salary-assignment`)
- **Tabelas de IR** — federal/estadual (`add-income-tax-slab`, `add-state-tax-slab`)
- **Config. de Impostos** — FICA, FUTA/SUTA (`update-fica-config`)
- **Ciclos de Folha** (`create-payroll-run`, `submit-payroll-run`)
- **Holerites** (`generate-salary-slips`) · **W-2** (`generate-w2-data`)
- **Penhoras** (`add-garnishment`) · **Horas Extras** (`calculate-overtime`) · **Retro** (`calculate-retro-pay`)
- **ACH/NACHA** (`generate-nacha-file`)

### 13. Contabilidade Avançada — `erpclaw-accounting-adv` · ~49 ações
ASC 606 (receita), ASC 842 (leasing), intercompany e consolidação.
- **Contratos de Receita (ASC 606)** (`add-revenue-contract`, `modify-contract`)
- **Obrigações de Desempenho** (`satisfy-performance-obligation`) · **Consideração Variável** (`add-variable-consideration`)
- **Cronograma/Apropriação** (`calculate-revenue-schedule`, `recognize-schedule-entry`)
- **Relatórios de Receita** (`revenue-waterfall-report`)
- **Arrendamentos (ASC 842)** (`add-lease`, `classify-lease`) · **ROU/Passivo** (`calculate-rou-asset`, `calculate-lease-liability`)
- **Amortização/Pagamentos** (`generate-amortization-schedule`, `record-lease-payment`) · **Relatórios** (`lease-disclosure-report`)
- **Transações Intercompany** (`approve-ic-transaction`, `post-ic-transaction`) · **Preços de Transferência** (`add-transfer-price-rule`)
- **Grupos/Execução de Consolidação** (`add-consolidation-group`, `run-consolidation`) · **Dashboard de Conformidade** (`standards-compliance-dashboard`)

### 14. Meta / Transversal — `erpclaw-meta` · ~4 ações de entrada
- **Verificação de Instalação** (`check-installation`) · **Guia de Onboarding por Tiers** (`install-guide`)
- **Geração de Dados de Demo** — empresa demo ponta-a-ponta (`seed-demo-data`)
- **Setup Web Dashboard** — stub migrado p/ addon `os-engine` (`setup-web-dashboard`)

### 15. OS / Infra de Runtime — `erpclaw-os` · ~7 ações
- **Validação contra a "Constituição"** (`validate-module`) · **Artigos** (`list-articles`)
- **Registro de Propriedade de Tabelas** (`build-table-registry`)
- **Migrações** — plano/aplicar/reverter/drift (`schema-plan`, `schema-apply`, `schema-rollback`, `schema-drift`)

---

## Parte B — Catálogo de módulos de expansão (registry: 46 módulos / ~3.169 ações)

> ⚠️ Catálogo do `module_registry.json`. **O código destes módulos não está no fork air-gapped** — reconstruí-los é trabalho de "desenvolver features".

### Verticais (indústria)
| Módulo | Ações | Módulo | Ações |
|--------|------:|--------|------:|
| healthclaw · Saúde | 231 | foodclaw · Alimentos | 80 |
| educlaw · Educação | 177 | hospitalityclaw · Hotelaria | 73 |
| constructclaw · Construção | 160 | automotiveclaw · Automotivo | 70 |
| propertyclaw · Imóveis | 103 | agricultureclaw · Agro | 67 |
| legalclaw · Jurídico | 100 | nonprofitclaw · ONGs | 57 |
| retailclaw · Varejo | 88 | | |

### Sub-verticais
| Módulo | Ações | Módulo | Ações |
|--------|------:|--------|------:|
| educlaw-finaid | 116 | educlaw-lms | 26 |
| educlaw-statereport | 99 | propertyclaw-commercial | 31 |
| educlaw-k12 | 77 | healthclaw-mental | 14 |
| educlaw-highered | 62 | healthclaw-dental | 12 |
| educlaw-scheduling | 58 | healthclaw-homehealth | 12 |
| | | healthclaw-vet | 12 |

### Infraestrutura
| Módulo | Ações | Módulo | Ações |
|--------|------:|--------|------:|
| maintenance | 39 | loans | 20 |
| compliance | 38 | fleet | 15 |
| treasury | 35 | approvals | 13 |
| logistics | 34 | esign | 13 |
| planning | 30 | documents | 25 |
| pos | 28 | selfservice | 25 |
| alerts | 21 | | |

### Expansão
| Módulo | Ações | Módulo | Ações |
|--------|------:|--------|------:|
| ops | 135 | integrations-stripe | 67 |
| growth | 110 | integrations-shopify | 66 |
| integrations | 80 | os-engine (dev) | 31 |

### Regional
| Módulo | Ações | Módulo | Ações |
|--------|------:|--------|------:|
| region-ca | 30 | region-uk | 28 |
| region-in | 30 | region-eu | 26 |
