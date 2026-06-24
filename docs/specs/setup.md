# Configuração & Admin — `glue-setup`

> Spec funcional por ação. Gerada de `scripts/glue-setup/db_query.py`. 15 funcionalidades · 61 ações.

## Gestão de Empresas

**Objetivo.** Criar, atualizar e consultar a entidade company e seus padrões contábeis/operacionais.

### `setup-company`

Cria uma nova empresa e auto-provisiona ano fiscal, centro de custo e armazém padrão.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --abbr (default: iniciais do nome, senão 3 primeiras letras); --currency (default USD); --country (default 'United States'); --fiscal-year-start-month (default 1); --industry (opcional, resolve perfil de onboarding). |
| **Saídas** | company_id, name, abbr, fiscal_year_id, cost_center_id, warehouse_id; e opcionalmente onboard_profile, profile_modules, region_module. |
| **Regras** | name é obrigatório; IntegrityError em duplicado/dados inválidos retorna erro. Calcula período do ano fiscal a partir do mês de início vs data atual. Criação de fiscal_year/cost_center/warehouse é não-fatal (falha apenas loga em stderr). --industry mapeia perfil/região via dados locais bundled (sem rede). |
| **Efeitos colaterais** | INSERT em company; INSERT em fiscal_year; INSERT em cost_center e UPDATE company.default_cost_center_id; INSERT em warehouse e UPDATE company.default_warehouse_id; audit_log (action 'create', entity 'company'). Nenhuma postagem em gl_entry/SLE/PLE. |
| **Pré-condições** | Banco inicializado (tabelas company/fiscal_year/cost_center/warehouse existentes). |

### `update-company`

Atualiza campos editáveis de uma empresa, incluindo contas/centros padrão.

| | |
|---|---|
| **Entradas** | --company-id (default: primeira empresa); flags por campo: --name, --abbr, --currency, --country, --tax-id, contas padrão (--default-*-account-id), --default-cost-center-id, --default-warehouse-id, --round-off-account-id, --exchange-gain-loss-account-id, --perpetual-inventory, --enable-negative-stock, --accounts-frozen-till-date, --role-allowed-for-frozen-entries, --fiscal-year-start-month. |
| **Saídas** | company_id, updated_fields (lista). |
| **Regras** | Se nenhum company-id, usa a primeira empresa; erro se nenhuma existir ou id não encontrado. Erro 'No fields to update' se nada informado. Valida que contas padrão informadas não sejam contas de grupo (is_group=1), rejeitando com mensagem. |
| **Efeitos colaterais** | UPDATE company (campos informados + updated_at); audit_log (action 'update', com old/new values). Somente leitura em account para validação. Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Pelo menos uma company existente; contas referenciadas devem existir e ser folha (leaf). |

### `get-company`

Retorna o registro completo de uma empresa.

| | |
|---|---|
| **Entradas** | --company-id (default: primeira empresa). |
| **Saídas** | company (objeto com todas as colunas). |
| **Regras** | Sem id, retorna a primeira empresa; erro 'No company found' com sugestão se nenhuma existir. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Banco inicializado; idealmente ao menos uma empresa. |

### `list-companies`

Lista empresas com paginação.

| | |
|---|---|
| **Entradas** | --limit (default 20); --offset (default 0). |
| **Saídas** | companies (array), total_count, limit, offset, has_more. |
| **Regras** | Ordena por name; has_more calculado como offset+limit<total_count. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Banco inicializado. |

## Moedas e Câmbio

**Objetivo.** Cadastrar moedas e gerir taxas de câmbio manuais e via API externa.

### `add-currency`

Cadastra uma moeda no catálogo.

| | |
|---|---|
| **Entradas** | --code (obrigatório, normalizado para maiúsculas); --name (default: code); --symbol (default ''); --decimal-places (default 2); --enabled (flag, default 0/desabilitada). |
| **Saídas** | code, name. |
| **Regras** | code obrigatório; IntegrityError retorna 'Currency already exists'. |
| **Efeitos colaterais** | INSERT em currency; audit_log (action 'create', entity 'currency'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Banco inicializado (tabela currency). |

### `list-currencies`

Lista moedas, opcionalmente só as habilitadas.

| | |
|---|---|
| **Entradas** | --enabled-only (flag); --limit (default 20); --offset (default 0). |
| **Saídas** | currencies (array), total_count, limit, offset, has_more. |
| **Regras** | Com --enabled-only filtra enabled=1; ordena por code. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Banco inicializado. |

### `add-exchange-rate`

Registra uma taxa de câmbio manual para um par de moedas.

| | |
|---|---|
| **Entradas** | --from-currency (obrigatório), --to-currency (obrigatório), --rate (obrigatório); --effective-date (default: hoje UTC); --source (default 'manual'). |
| **Saídas** | exchange_rate_id, effective_date. |
| **Regras** | Os três campos são obrigatórios; moedas normalizadas para maiúsculas; IntegrityError retorna falha (duplicado/inválido). |
| **Efeitos colaterais** | INSERT em exchange_rate; audit_log (action 'create', entity 'exchange_rate'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Banco inicializado (tabela exchange_rate). |

### `get-exchange-rate`

Retorna a taxa vigente de um par na data (ou a mais recente anterior).

| | |
|---|---|
| **Entradas** | --from-currency (obrigatório), --to-currency (obrigatório); --effective-date (default: hoje UTC). |
| **Saídas** | rate, effective_date, source. |
| **Regras** | from/to obrigatórios; busca effective_date <= data, ordenado desc, limit 1; erro se nenhuma taxa encontrada. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Existir taxa para o par na/antes da data. |

### `list-exchange-rates`

Lista taxas de câmbio com filtros opcionais.

| | |
|---|---|
| **Entradas** | --from-currency, --to-currency, --from-date, --to-date (todos opcionais); --limit (default 20); --offset (default 0). |
| **Saídas** | rates (array), total_count, limit, offset, has_more. |
| **Regras** | Aplica filtros conforme flags; ordena por effective_date desc. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Banco inicializado. |

### `fetch-exchange-rates`

Busca taxas USD-base em frankfurter.dev e faz upsert no exchange_rate.

| | |
|---|---|
| **Entradas** | Nenhuma flag (base=USD fixo, effective_date=hoje, source='api'). |
| **Saídas** | rates_updated, source ('frankfurter.dev'), base ('USD'), date. |
| **Regras** | Requer rede (timeout 15s); erro de conexão/HTTP retorna falha com sugestão; erro se API retornar zero taxas. Para cada par: UPDATE se já existe (USD/to/hoje), senão INSERT. |
| **Efeitos colaterais** | INSERT ou UPDATE em exchange_rate (rate, source='api', updated_at); audit_log (action 'fetch', entity 'exchange_rate'). Sem gl_entry/SLE/PLE. Faz chamada HTTP externa. |
| **Pré-condições** | Conexão de internet; tabela exchange_rate. |

## Condições de Pagamento

**Objetivo.** Cadastrar e listar templates de prazos/descontos de pagamento.

### `add-payment-terms`

Cria um template de condição de pagamento.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --due-days (default 30); --discount-percentage (opcional); --discount-days (opcional); --description (opcional). |
| **Saídas** | payment_terms_id, name. |
| **Regras** | name obrigatório; IntegrityError retorna 'Payment terms already exists'. |
| **Efeitos colaterais** | INSERT em payment_terms; audit_log (action 'create', entity 'payment_terms'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Banco inicializado (tabela payment_terms). |

### `list-payment-terms`

Lista todas as condições de pagamento.

| | |
|---|---|
| **Entradas** | --limit (default 20); --offset (default 0). |
| **Saídas** | terms (array), total_count, limit, offset, has_more. |
| **Regras** | Ordena por due_days e name. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Banco inicializado. |

## Unidades de Medida

**Objetivo.** Gerir unidades de medida (UoM) e seus fatores de conversão.

### `add-uom`

Cadastra uma unidade de medida.

| | |
|---|---|
| **Entradas** | --name (obrigatório); --must-be-whole-number (flag, default 0). |
| **Saídas** | uom_id, name. |
| **Regras** | name obrigatório; IntegrityError retorna 'UoM already exists'. |
| **Efeitos colaterais** | INSERT em uom; audit_log (action 'create', entity 'uom'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Banco inicializado (tabela uom). |

### `list-uoms`

Lista todas as unidades de medida.

| | |
|---|---|
| **Entradas** | --limit (default 20); --offset (default 0). |
| **Saídas** | uoms (array), total_count, limit, offset, has_more. |
| **Regras** | Ordena por name. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Banco inicializado. |

### `add-uom-conversion`

Registra um fator de conversão entre duas UoMs (opcionalmente por item).

| | |
|---|---|
| **Entradas** | --from-uom (obrigatório), --to-uom (obrigatório), --conversion-factor (obrigatório); --item-id (opcional). |
| **Saídas** | uom_conversion_id. |
| **Regras** | from-uom/to-uom/conversion-factor obrigatórios; IntegrityError retorna falha (duplicado/inválido). |
| **Efeitos colaterais** | INSERT em uom_conversion; audit_log (action 'create', entity 'uom_conversion'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Banco inicializado (tabela uom_conversion); UoMs referenciadas devem existir. |

## Usuários e Acessos (RBAC)

**Objetivo.** Criar e administrar contas de usuário ERP, status, senhas web e vínculos de empresa.

### `add-user`

Cria um novo usuário ERP.

| | |
|---|---|
| **Entradas** | --name (username, obrigatório); --email (opcional, validado); --full-name (opcional); --company-id (opcional, vira lista company_ids). |
| **Saídas** | user_id, username. |
| **Regras** | username obrigatório; email validado por regex se informado; erro se username já existe. |
| **Efeitos colaterais** | INSERT em erp_user; audit_log (action 'add-user', entity 'erp_user'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Banco inicializado (tabela erp_user). |

### `update-user`

Atualiza campos de um usuário existente (username, email, nome, status, empresas).

| | |
|---|---|
| **Entradas** | --user-id (obrigatório); --name (novo username); --email; --full-name; --user-status (active\|disabled\|locked); --company-id (anexa à lista). |
| **Saídas** | user_id, updated_fields. |
| **Regras** | user-id obrigatório; erro se usuário não encontrado; user-status validado contra active/disabled/locked; company-id é anexado (sem duplicar) a company_ids; erro 'No fields to update' se nada informado. |
| **Efeitos colaterais** | UPDATE em erp_user (+ updated_at); audit_log (action 'update-user', com old/new). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Usuário existente. |

### `list-users`

Lista usuários ERP com paginação.

| | |
|---|---|
| **Entradas** | --limit (default 50); --offset (default 0). |
| **Saídas** | users (array: id, username, email, full_name, status, company_ids, created_at), count, has_more. |
| **Regras** | Busca limit+1 para detectar has_more; ordena por username. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Banco inicializado. |

### `get-user`

Retorna um usuário e seus papéis atribuídos (com escopo de empresa).

| | |
|---|---|
| **Entradas** | --user-id (obrigatório). |
| **Saídas** | todos os campos do usuário + roles (array: role_name, company_id, company_name). |
| **Regras** | user-id obrigatório; erro se usuário não encontrado; faz join user_role/role/company. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Usuário existente. |

### `set-password`

Define a senha de login web (hash) de um usuário.

| | |
|---|---|
| **Entradas** | --user-id (obrigatório); --password (obrigatório, mínimo 8 caracteres). |
| **Saídas** | user_id, username, message. |
| **Regras** | user-id e password obrigatórios; senha < 8 chars rejeitada; erro se usuário não encontrado; usa hash_password da lib. |
| **Efeitos colaterais** | UPDATE erp_user.password_hash (+ updated_at); audit_log (action 'set-password', sem valores). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Usuário existente. |

## Papéis e Permissões

**Objetivo.** Gerir papéis (roles), suas atribuições a usuários e o seed de permissões padrão RBAC.

### `add-role`

Cria um papel customizado (não-sistema).

| | |
|---|---|
| **Entradas** | --name (obrigatório); --description (opcional). |
| **Saídas** | role_id, name. |
| **Regras** | name obrigatório; erro se role já existe; gravado com is_system=0. |
| **Efeitos colaterais** | INSERT em role; audit_log (action 'add-role', entity 'role'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Banco inicializado (tabela role). |

### `list-roles`

Lista todos os papéis com contagem de usuários por papel.

| | |
|---|---|
| **Entradas** | Nenhuma. |
| **Saídas** | roles (array: id, name, description, is_system, user_count), count. |
| **Regras** | Left join com user_role; ordena por is_system desc, depois name. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Banco inicializado. |

### `assign-role`

Atribui um papel a um usuário, opcionalmente com escopo de empresa.

| | |
|---|---|
| **Entradas** | --user-id (obrigatório); --role-name (obrigatório); --company-id (opcional; None = atribuição global). |
| **Saídas** | user_role_id, role_name, company_id. |
| **Regras** | user-id e role-name obrigatórios; erro se usuário ou role não encontrado; erro se já atribuído (comparação NULL-safe via SQL IS ?). |
| **Efeitos colaterais** | INSERT em user_role; audit_log (action 'assign-role', entity 'user_role'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Usuário e role existentes. |

### `revoke-role`

Remove um papel de um usuário (no escopo de empresa informado).

| | |
|---|---|
| **Entradas** | --user-id (obrigatório); --role-name (obrigatório); --company-id (opcional, NULL-safe). |
| **Saídas** | revoked (role_name), user_id. |
| **Regras** | user-id e role-name obrigatórios; erro se role não encontrado; DELETE com IS ?; erro se não havia atribuição (rowcount 0). |
| **Efeitos colaterais** | DELETE em user_role; audit_log (action 'revoke-role', entity 'user_role', com old values). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Role existente e atribuição presente. |

### `seed-permissions`

Popula as permissões padrão de papéis a partir da lib RBAC compartilhada.

| | |
|---|---|
| **Entradas** | Nenhuma. |
| **Saídas** | permissions_seeded (contagem total de role_permission). |
| **Regras** | Chama seed_role_permissions da lib; idempotente conforme implementação da lib. |
| **Efeitos colaterais** | INSERT em role_permission (via lib seed_role_permissions). Sem audit_log direto. Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Banco inicializado (tabelas role/role_permission). |

## Integração Telegram

**Objetivo.** Vincular IDs de usuário do Telegram a contas ERP e checar permissões via Telegram.

### `link-telegram-user`

Vincula um Telegram user ID a uma conta de usuário ERP.

| | |
|---|---|
| **Entradas** | --user-id (obrigatório); --telegram-user-id (obrigatório). |
| **Saídas** | user_id, username, telegram_user_id, linked (true). |
| **Regras** | Ambos obrigatórios; erro se usuário não encontrado; erro se o telegram-user-id já está vinculado a outra conta. |
| **Efeitos colaterais** | UPDATE erp_user.telegram_user_id (+ updated_at); audit_log (action 'link-telegram-user'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Usuário ERP existente; telegram-user-id não vinculado a outro usuário. |

### `unlink-telegram-user`

Remove o vínculo de um Telegram user ID de uma conta ERP.

| | |
|---|---|
| **Entradas** | --telegram-user-id (obrigatório). |
| **Saídas** | user_id, telegram_user_id, unlinked (true). |
| **Regras** | telegram-user-id obrigatório; erro se nenhum usuário estiver vinculado a esse ID. |
| **Efeitos colaterais** | UPDATE erp_user.telegram_user_id = NULL (+ updated_at); audit_log (action 'unlink-telegram-user', com old values). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Existir usuário vinculado ao telegram-user-id. |

### `check-telegram-permission`

Verifica se um usuário Telegram tem permissão para uma ação de skill.

| | |
|---|---|
| **Entradas** | --telegram-user-id (obrigatório); --skill (obrigatório); --check-action (obrigatório). |
| **Saídas** | allowed (bool); se vinculado: user_id, skill, action, telegram_user_id; se não: reason='not_linked'. |
| **Regras** | Três campos obrigatórios; resolve user via resolve_telegram_user_id; se não vinculado retorna allowed=false reason not_linked; senão consulta check_permission da lib RBAC. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Banco inicializado; permissões seeded para resultado significativo. |

## Credenciais de Integração

**Objetivo.** Armazenar, consultar e migrar credenciais de integrações no arquivo de credenciais criptografado.

### `set-credential`

Armazena uma credencial de integração no arquivo criptografado.

| | |
|---|---|
| **Entradas** | --integration (obrigatório); valor via --value OU --from-stdin OU --from-env <VAR> (um obrigatório). |
| **Saídas** | message, integration, credentials_file (caminho). |
| **Regras** | integration obrigatório; exige fonte de valor (value/stdin/env); erro se valor vazio ou env var não setada; nunca aceita o valor via --api-key. |
| **Efeitos colaterais** | Escreve no arquivo de credenciais criptografado (glue_lib.credentials, NÃO em tabela do DB); sem audit_log; sem gl_entry/SLE/PLE. |
| **Pré-condições** | Lib de credenciais disponível; master key disponível para criptografia. |

### `get-credential`

Informa se uma credencial existe (sem expor o valor).

| | |
|---|---|
| **Entradas** | --integration (obrigatório). |
| **Saídas** | integration, exists (bool), redacted_preview (4 primeiros/4 últimos chars se len>=12, senão null). |
| **Regras** | integration obrigatório; nunca retorna o valor completo, apenas preview redigido. |
| **Efeitos colaterais** | nenhum (leitura do arquivo de credenciais). |
| **Pré-condições** | Lib de credenciais disponível. |

### `list-credentials`

Lista os nomes de integrações com credenciais armazenadas.

| | |
|---|---|
| **Entradas** | Nenhuma. |
| **Saídas** | integrations (array de nomes). |
| **Regras** | Nunca lista valores, apenas nomes. |
| **Efeitos colaterais** | nenhum (leitura do arquivo de credenciais). |
| **Pré-condições** | Lib de credenciais disponível. |

### `delete-credential`

Remove uma credencial armazenada.

| | |
|---|---|
| **Entradas** | --integration (obrigatório). |
| **Saídas** | integration, deleted (bool), message. |
| **Regras** | integration obrigatório; deleted=false se não havia credencial. |
| **Efeitos colaterais** | Remove entrada do arquivo de credenciais criptografado; sem audit_log; sem gl_entry/SLE/PLE. |
| **Pré-condições** | Lib de credenciais disponível. |

### `migrate-credentials`

Migra credenciais em texto plano de tabelas de addons para o arquivo criptografado.

| | |
|---|---|
| **Entradas** | --dry-run (flag; pré-visualiza sem gravar). |
| **Saídas** | dry_run, moved (array), skipped (array), next (orientação). |
| **Regras** | Detecta tabela stripe_account.api_key; pula se já no store criptografado; com --dry-run não grava. Falhas por tabela ausente são ignoradas (addon não instalado). |
| **Efeitos colaterais** | Sem dry-run: escreve no arquivo de credenciais e faz UPDATE stripe_account.api_key=NULL (commit). Com dry-run: nenhum. Sem gl_entry/SLE/PLE; sem audit_log. |
| **Pré-condições** | Tabela de addon (ex.: stripe_account) presente para haver o que migrar. |

## Campos Personalizados (UDF)

**Objetivo.** Definir, listar, remover e atribuir valores de campos customizados (UDF) em tabelas core.

### `add-custom-field`

Registra a definição de um campo customizado em uma tabela core (M1).

| | |
|---|---|
| **Entradas** | --table (obrigatório); --field-name (obrigatório, snake_case); --field-type (obrigatório: text\|int\|float\|date\|select\|link\|json); --label, --required (flag), --default, --options, --skill-name (default 'glue-setup'). |
| **Saídas** | result='registered', custom_field_id, table, field_name, field_type. |
| **Regras** | table/field-name obrigatórios; field-type validado contra lista; --options para select vira {values:[...]}, para link vira {table:...}, demais tipos é JSON cru; IntegrityError retorna 'já existe'. |
| **Efeitos colaterais** | INSERT em custom_field (via cf.add_custom_field); audit_log (action 'create', entity 'custom_field'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Banco inicializado com tabela custom_field (lib custom_fields). |

### `list-custom-fields`

Lista definições de campos customizados (opcionalmente por tabela).

| | |
|---|---|
| **Entradas** | --table (opcional, filtro). |
| **Saídas** | custom_fields (array), count. |
| **Regras** | Filtra por table_name se informado; ordena por table_name, field_name. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela custom_field existente. |

### `remove-custom-field`

Remove a definição de um campo customizado e seus valores armazenados.

| | |
|---|---|
| **Entradas** | --table (obrigatório); --field-name (obrigatório); --confirm (flag, exigido se houver valores). |
| **Saídas** | result='removed', table, field_name, deleted_values (contagem). |
| **Regras** | table/field-name obrigatórios; erro se campo não existe; se há valores armazenados, exige --confirm; remoção respeita owner_skill (erro 'owner mismatch'). Hard delete. |
| **Efeitos colaterais** | DELETE em custom_field e custom_field_value (via cf.remove_custom_field); audit_log (action 'delete', entity 'custom_field'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Definição de campo existente; --confirm se houver valores. |

### `set-custom-field-value`

Define o valor de um campo customizado em uma linha (validado).

| | |
|---|---|
| **Entradas** | --table (obrigatório); --row-id (obrigatório); --field-name (obrigatório); --value (obrigatório). |
| **Saídas** | result='stored', table, row_id, field_name, value. |
| **Regras** | table/row-id/field-name obrigatórios; value obrigatório (não pode ser None); valida via cf.validate_custom_field_values e aborta com erros se inválido. |
| **Efeitos colaterais** | INSERT/UPDATE em custom_field_value (via cf.store_custom_field_values, commit). Sem audit_log. Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Definição do campo registrada para a tabela. |

### `get-custom-field-values`

Lê valores de campos customizados de uma linha (todos ou um específico).

| | |
|---|---|
| **Entradas** | --table (obrigatório); --row-id (obrigatório); --field-name (opcional, filtra um campo). |
| **Saídas** | table, row_id, custom_fields (dict de valores). |
| **Regras** | table/row-id obrigatórios; se --field-name informado retorna apenas esse campo. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela custom_field_value existente. |

## Registros de Tipos e Status

**Objetivo.** Administrar em runtime os registries de account_type e voucher_type (extensão, listagem, desativação) e diagnosticar cobertura.

### `add-account-type`

Registra um novo account_type para que contas possam usá-lo (M0).

| | |
|---|---|
| **Entradas** | --account-type (obrigatório); --label (default: derivado do valor); --skill-name (default 'custom'). |
| **Saídas** | result='registered', account_type, label. |
| **Regras** | account-type obrigatório; IntegrityError retorna 'já registrado'. |
| **Efeitos colaterais** | INSERT em account_type_registry (is_active=1); audit_log (action 'create', entity 'account_type_registry'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Tabela account_type_registry existente. |

### `list-account-types`

Lista account types registrados (só ativos, salvo --include-inactive).

| | |
|---|---|
| **Entradas** | --include-inactive (flag). |
| **Saídas** | account_types (array), count. |
| **Regras** | Sem a flag, filtra is_active=1; ordena por account_type. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela account_type_registry existente. |

### `deactivate-account-type`

Soft-disable de um account_type (is_active=0), bloqueado se em uso.

| | |
|---|---|
| **Entradas** | --account-type (obrigatório). |
| **Saídas** | result='deactivated', account_type. |
| **Regras** | account-type obrigatório; bloqueia se alguma account usa o tipo (conta COUNT em account); erro se o tipo não estava registrado (nenhuma linha alterada). |
| **Efeitos colaterais** | UPDATE account_type_registry SET is_active=0; audit_log (action 'update'). Leitura em account para checar uso. Sem gl_entry/SLE/PLE. |
| **Pré-condições** | account_type registrado e não usado por nenhuma conta. |

### `add-voucher-type`

Registra um novo voucher_type para uma tabela-alvo (M0).

| | |
|---|---|
| **Entradas** | --voucher-type (obrigatório); --target-table (obrigatório: gl_entry\|stock_ledger_entry\|payment_allocation); --label (default derivado); --skill-name (default 'custom'). |
| **Saídas** | result='registered', voucher_type, target_table, label. |
| **Regras** | voucher-type obrigatório; target-table deve ser um dos três alvos válidos; IntegrityError retorna 'já registrado para o alvo'. |
| **Efeitos colaterais** | INSERT em voucher_type_registry (is_active=1); audit_log (action 'create'). Sem postagens em gl_entry/SLE/PLE. |
| **Pré-condições** | Tabela voucher_type_registry existente. |

### `list-voucher-types`

Lista voucher types registrados (opcionalmente por target-table).

| | |
|---|---|
| **Entradas** | --include-inactive (flag); --target-table (filtro opcional). |
| **Saídas** | voucher_types (array), count. |
| **Regras** | Sem a flag filtra is_active=1; filtra por target_table se informado; ordena por target_table, voucher_type. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela voucher_type_registry existente. |

### `deactivate-voucher-type`

Soft-disable de um voucher_type em uma tabela-alvo, bloqueado se há linhas vivas usando-o.

| | |
|---|---|
| **Entradas** | --voucher-type (obrigatório); --target-table (obrigatório, um dos três alvos). |
| **Saídas** | result='deactivated', voucher_type, target_table. |
| **Regras** | voucher-type obrigatório; target-table validado; bloqueia se houver linhas na tabela-alvo usando o voucher_type; erro se não registrado para o alvo. |
| **Efeitos colaterais** | UPDATE voucher_type_registry SET is_active=0 (por voucher_type+target_table); audit_log (action 'update'). Leitura na tabela-alvo para checar uso. Sem novas postagens em gl_entry/SLE/PLE. |
| **Pré-condições** | voucher_type registrado para o alvo e sem linhas vivas usando-o. |

### `validate-registry-completeness`

Diagnóstico read-only: reporta valores de tipo/status em uso nos dados que não estão registrados+ativos.

| | |
|---|---|
| **Entradas** | Nenhuma. |
| **Saídas** | complete (bool), unregistered_in_use (dict por categoria), detail (explicação). |
| **Regras** | Cobre account_type, party_type (gl_entry/payment_entry/payment_ledger_entry), voucher_type por alvo e asset_status; tolera tabelas ausentes em instalação mínima. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Banco inicializado; os registries existentes. |

## Backup e Restauração

**Objetivo.** Criar, listar, verificar, restaurar e fazer retenção de backups do banco (com cripto opcional).

### `backup-database`

Cria um backup do banco SQLite, opcionalmente criptografado AES-256.

| | |
|---|---|
| **Entradas** | --backup-path (default: BACKUP_DIR/glue_backup_<ts>.sqlite\|.enc); --encrypt (flag); --passphrase (obrigatório se --encrypt). |
| **Saídas** | backup_path, size_bytes, encrypted, timestamp; se criptografado: carries_master_key, original_size. |
| **Regras** | Erro se --encrypt sem --passphrase. Criptografado: faz backup temp, depois encrypt_file com HMAC; se existe master key local, ela é wrapped com a passphrase e embutida no header (permite restore cross-machine). Define mode 600 no arquivo. |
| **Efeitos colaterais** | Cria arquivo de backup no filesystem (usa src.backup); não escreve em tabelas do DB; sem audit_log; sem gl_entry/SLE/PLE. |
| **Pré-condições** | Banco existente; lib crypto/master_key para modo criptografado. |

### `list-backups`

Lista arquivos de backup com tamanho, data e flag de criptografia.

| | |
|---|---|
| **Entradas** | Nenhuma. |
| **Saídas** | backups (array: path, filename, size_bytes, timestamp, encrypted), count, total_size_bytes. |
| **Regras** | Casa glue_*.sqlite e glue_*.enc; parseia timestamp do nome; ordena reverso (recentes primeiro); retorna vazio se diretório não existe. |
| **Efeitos colaterais** | nenhum (leitura do filesystem). |
| **Pré-condições** | Nenhuma (diretório de backups pode não existir). |

### `verify-backup`

Valida um arquivo de backup sem restaurar (SQLite válido, schema Glue, integridade).

| | |
|---|---|
| **Entradas** | --backup-path (obrigatório); --passphrase (obrigatório se backup criptografado). |
| **Saídas** | valid, integrity, tables, schema_module, schema_version, size_bytes, encrypted (ou para .enc sem passphrase: valid=null com mensagem). |
| **Regras** | Erro se backup-path ausente ou arquivo inexistente; auto-detecta cripto; sem passphrase para .enc retorna valid=null; valida presença de schema_version, roda PRAGMA integrity_check; remove temp descriptografado ao final. |
| **Efeitos colaterais** | nenhum (leitura/validação; usa arquivo temp efêmero que é apagado). |
| **Pré-condições** | Arquivo de backup existente; passphrase para criptografados. |

### `restore-database`

Restaura o banco a partir de um backup, com backup de segurança e rollback automático.

| | |
|---|---|
| **Entradas** | --backup-path (obrigatório); --passphrase (obrigatório se criptografado); --db-path (alvo, default padrão). |
| **Saídas** | restored_from, safety_backup, size_bytes, schema_versions, integrity, was_encrypted. |
| **Regras** | Erro se backup-path ausente/inexistente; cripto exige passphrase; valida schema_version no backup; fecha a conexão atual, cria safety backup, copia backup sobre o DB, roda integrity_check; em qualquer falha faz rollback restaurando o safety backup. |
| **Efeitos colaterais** | Substitui o arquivo do DB no filesystem; cria safety backup (glue_pre_restore_<ts>.sqlite); ajusta permissões; em falha restaura estado anterior. Não escreve em tabelas via SQL; sem audit_log. |
| **Pré-condições** | Backup válido Glue; passphrase se criptografado. |

### `cleanup-backups`

Aplica política de retenção (7 diários, 4 semanais, 12 mensais) removendo o excesso.

| | |
|---|---|
| **Entradas** | Nenhuma (opera sobre glue_backup_*.sqlite no BACKUP_DIR). |
| **Saídas** | kept, deleted, freed_bytes. |
| **Regras** | Parseia timestamps do nome; mantém 7 datas diárias mais recentes, depois 4 semanais (mais antigo por semana) e 12 mensais; deleta o restante; tolera erros de remoção individual. |
| **Efeitos colaterais** | Remove arquivos de backup do filesystem; audit_log (action 'cleanup', entity 'backup'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Diretório de backups com arquivos no padrão esperado. |

## Schema e Migrações

**Objetivo.** Inicializar o schema do banco, aplicar migrações de fundação e consultar a versão de schema.

### `initialize-database`

Inicializa (ou re-inicializa com --force) todo o schema do banco Glue.

| | |
|---|---|
| **Entradas** | --db-path (default padrão); --force (flag: dropa e recria do zero). |
| **Saídas** | message, db_path, tables, indexes, skills_registered, journal_mode (WAL), foreign_keys (ON), reinitialized. |
| **Regras** | Usa CREATE TABLE IF NOT EXISTS (idempotente); com --force remove o arquivo e recria; symlinka a lib compartilhada; ajusta permissões 600; verifica recontando tabelas/índices. Gerencia sua própria conexão (não usa a conexão padrão do dispatch). |
| **Efeitos colaterais** | Cria/recria todas as tabelas e índices via init_schema.init_db; com --force remove o arquivo do DB; symlinka ~/.glue/lib; chmod nos arquivos do DB. Sem audit_log; sem gl_entry/SLE/PLE. |
| **Pré-condições** | Módulo init_schema disponível; permissão de escrita no caminho do DB. |

### `migrate`

Executa migrações pendentes da fundação (migrations/NNN_*.py), registrando-as no ledger.

| | |
|---|---|
| **Entradas** | --db-path (default padrão); --dry-run (flag: lista pendentes sem aplicar). |
| **Saídas** | Resultado do runner (ex.: migrações aplicadas/pendentes); em falha, erro com nome da migração e detalhe. |
| **Regras** | Idempotente e dialect-aware; --dry-run apenas lista; falha de migração retorna erro com suggestion. Gerencia suas próprias conexões via db_path (não usa a conexão do dispatch). |
| **Efeitos colaterais** | Aplica DDL/DML das migrações e grava em glue_schema_migration (ledger). Com --dry-run: nenhum. Sem audit_log; efeitos dependem das migrações. |
| **Pré-condições** | migration_runner.py e arquivos de migração presentes; DB existente. |

### `get-schema-version`

Lê a versão de schema registrada para um módulo.

| | |
|---|---|
| **Entradas** | --module (default 'glue-setup'). |
| **Saídas** | module, version, updated_at. |
| **Regras** | Erro se não houver versão registrada para o módulo. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela schema_version populada (via initialize-database). |

## Dados Padrão e Onboarding

**Objetivo.** Semear dados padrão, criar empresa-demo de tutorial e conduzir o assistente de onboarding passo-a-passo.

### `seed-defaults`

Carrega dados padrão (moedas, UoMs, condições de pagamento) de forma idempotente.

| | |
|---|---|
| **Entradas** | --company-id (default: primeira empresa). |
| **Saídas** | currencies_seeded, uoms_seeded, payment_terms_seeded (contagens). |
| **Regras** | Sem company-id usa a primeira; erro se nenhuma empresa existir; lê JSONs de ASSETS_DIR; usa INSERT OR IGNORE (idempotente). |
| **Efeitos colaterais** | INSERT OR IGNORE em currency, uom e payment_terms; audit_log (action 'seed', entity 'system'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Pelo menos uma empresa; arquivos de assets presentes. |

### `tutorial`

Cria a empresa-demo 'Acme Corp' com plano de contas mínimo, centro de custo e ano fiscal.

| | |
|---|---|
| **Entradas** | Nenhuma flag relevante (idempotente). |
| **Saídas** | message, company_id, accounts_created (ou accounts), fiscal_year, cost_center, next_steps; se já existe: message + accounts + next_steps. |
| **Regras** | Idempotente: se 'Acme Corp' já existe, retorna dados existentes; senão cria empresa, ~21 contas (plano fixo), define contas padrão da empresa, cost center 'Main' e fiscal year do ano corrente. |
| **Efeitos colaterais** | INSERT em company, account (várias), cost_center, fiscal_year; UPDATE company (contas e cost center padrão); audit_log (action 'create', entity 'company'). Sem postagens em gl_entry/SLE/PLE. |
| **Pré-condições** | Banco inicializado. |

### `onboarding-step`

Assistente de onboarding por estado (state-machine) que avança um passo por chamada.

| | |
|---|---|
| **Entradas** | --answer (resposta do passo atual); --reset (flag: reinicia no passo 1). |
| **Saídas** | step, completed, prompt, options, field; ao final: company_id, currency, fiscal_month, load_demo, results (steps_completed/steps_failed). |
| **Regras** | Estado persistido em ~/.glue/onboarding_state.json. Passos: 1 nome; 2 moeda (validada contra VALID_CURRENCIES); 3 mês fiscal (1-12); 4 demo (yes/no). Passo 4 executa subprocessos: setup-company, seed-defaults, setup-chart-of-accounts (glue-gl, us_gaap) e, se demo, seed-demo-data (glue meta). Falhas de subpasso vão para steps_failed sem abortar. |
| **Efeitos colaterais** | Escreve/limpa o arquivo de estado de onboarding (filesystem). Dispara subprocessos que, por sua vez, gravam em company, account, currency/uom/payment_terms e demo data, e seus próprios audit_log. Esta ação em si não escreve diretamente em tabelas. |
| **Pré-condições** | Banco inicializado; scripts glue-gl/glue para os passos C/D (opcionais). |

## Config. Regionais/Avançadas

**Objetivo.** Definir configurações regionais por empresa e configurar a conta de adiantamento (advance) de cliente/fornecedor.

### `update-regional-settings`

Define configurações regionais da empresa (formato de data/número, template fiscal padrão).

| | |
|---|---|
| **Entradas** | --company-id (default: primeira empresa); --date-format; --number-format; --default-tax-template-id (ao menos um obrigatório). |
| **Saídas** | updated (lista de chaves atualizadas). |
| **Regras** | Sem company-id usa a primeira; erro se nenhuma empresa; erro 'No settings to update' se nada informado; faz upsert por (company_id, key). |
| **Efeitos colaterais** | INSERT/UPDATE (ON CONFLICT) em regional_settings; audit_log (action 'update', entity 'regional_settings'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Pelo menos uma empresa; tabela regional_settings. |

### `set-advance-account`

Configura a sub-conta de adiantamento (advance) de cliente ou fornecedor na empresa (S2).

| | |
|---|---|
| **Entradas** | --company-id (obrigatório); --account-id (obrigatório); --type (obrigatório: customer\|supplier). |
| **Saídas** | result='set', company_id, type, column (advance_from_customer_account_id ou advance_to_supplier_account_id), account_id. |
| **Regras** | Todos obrigatórios; type validado; empresa e conta devem existir; conta não pode ser de grupo; para customer exige root_type 'liability', para supplier exige 'asset'. Quando setada, submit-payment roteia a perna de adiantamento não-alocado para esta conta. |
| **Efeitos colaterais** | UPDATE company (coluna advance_*_account_id allowlistada + updated_at, via dynamic_update); audit_log (action 'update', entity 'company'). Sem gl_entry/SLE/PLE. |
| **Pré-condições** | Empresa e conta (folha, root_type correto) existentes. |

## Auditoria/Status/Chave-Mestra

**Objetivo.** Consultar trilha de auditoria e status do sistema e importar a chave-mestra de criptografia de um backup.

### `get-audit-log`

Consulta a trilha de auditoria com filtros opcionais.

| | |
|---|---|
| **Entradas** | --entity-type, --entity-id, --audit-action, --from-date, --to-date (filtros opcionais); --limit (default 50). |
| **Saídas** | entries (array de registros de auditoria, com old_values/new_values já parseados de JSON). |
| **Regras** | Aplica filtros conforme flags; ordena por timestamp desc; faz parse dos campos JSON old_values/new_values. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Tabela audit_log existente. |

### `status`

Retorna o status geral do sistema (contagens e versões de schema).

| | |
|---|---|
| **Entradas** | Nenhuma. |
| **Saídas** | companies, currencies (habilitadas), uoms, payment_terms, schema_versions (dict módulo->versão). |
| **Regras** | Conta company, currency (enabled=1), uom, payment_terms; lê todas as linhas de schema_version. |
| **Efeitos colaterais** | nenhum (leitura). |
| **Pré-condições** | Banco inicializado. |

### `import-master-key-from-backup`

Extrai a chave-mestra de criptografia embutida em um backup e a instala localmente (restore cross-machine).

| | |
|---|---|
| **Entradas** | --backup-path (obrigatório); passphrase via --passphrase OU --passphrase-from-stdin OU --passphrase-from-env <VAR> (uma obrigatória); --force (flag: sobrescreve chave existente). |
| **Saídas** | message, master_key_path, next (orientação para restore). |
| **Regras** | backup-path obrigatório e arquivo deve existir; exige passphrase não-vazia; backup deve ser formato ECRYPT02 e carregar wrapped master key (senão erro); passphrase errada falha o unwrap; recusa sobrescrever chave existente sem --force (com aviso de perda de dados). |
| **Efeitos colaterais** | Escreve o arquivo master.key em ~/.config/glue (MASTER_KEY_PATH); com --force remove a chave existente antes. Não escreve em tabelas do DB; sem audit_log; sem gl_entry/SLE/PLE. |
| **Pré-condições** | Backup ECRYPT02 com chave embutida; passphrase de wrapping correta; ausência de master key (ou --force). |

