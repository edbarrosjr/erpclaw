# Configuração & Admin — `erpclaw-setup`

> Specs funcionais (enxutas) por funcionalidade. Geradas do código: `scripts/erpclaw-setup/db_query.py`. 15 funcionalidades · 61 ações.

## Gestão de Empresas

**Objetivo.** Cadastrar e administrar as empresas (entidades legais) do ERP, com criação automática de estruturas contábeis e operacionais básicas para cada nova empresa.

**Ações:**
- `setup-company` — Cria uma nova empresa e auto-provisiona ano fiscal, centro de custo padrão e armazém padrão.
- `update-company` — Atualiza campos da empresa (moeda, país, contas-padrão de AR/AP/receita/despesa, banco/caixa, inventário perpétuo, congelamento contábil).
- `get-company` — Retorna um registro de empresa (a primeira se nenhum id for passado).
- `list-companies` — Lista empresas paginadas, ordenadas por nome, com total_count.
- `set-advance-account` — Configura a sub-conta de adiantamento (advance_from_customer/advance_to_supplier) usada no roteamento de pagamentos antecipados.

| Campo | Detalhe |
|---|---|
| **Entradas** | setup-company: --name (obrigatório), --abbr, --currency, --country, --fiscal-year-start-month, --industry. update-company: --company-id + campos atualizáveis (default_*_account_id, --perpetual-inventory, --enable-negative-stock, --accounts-frozen-till-date). set-advance-account: --company-id, --account-id, --type (customer\|supplier). |
| **Saídas** | setup-company retorna company_id, abbr, fiscal_year_id, cost_center_id, warehouse_id e (se --industry) onboard_profile/profile_modules/region_module. update-company retorna updated_fields. list-companies retorna companies[], total_count, has_more. |
| **Regras de negócio** | abbr derivada das iniciais do nome se não informada (fallback 3 primeiras letras). Ano fiscal calculado a partir do fiscal_year_start_month (jan->ano calendário; outro mês->12 meses). update-company rejeita contas-padrão que sejam grupo (is_group=1), exige conta folha. set-advance-account exige conta folha e root_type correto (liability p/ customer, asset p/ supplier). update-company sem campos retorna erro. |
| **Efeitos colaterais** | INSERT em company; setup-company também INSERT em fiscal_year, cost_center, warehouse e UPDATE company (default_cost_center_id/default_warehouse_id) — criações secundárias são não-fatais (best-effort). Grava audit_log (create/update). Nenhuma postagem em gl_entry ou stock_ledger_entry. |
| **Pré-condições** | Banco inicializado (initialize-database). Para update-company com contas-padrão, as contas (account) já devem existir e ser folha. set-advance-account exige empresa e conta existentes. |

## Moedas e Câmbio

**Objetivo.** Manter o cadastro de moedas e as taxas de câmbio entre pares de moedas, com busca histórica e atualização automática via API externa.

**Ações:**
- `add-currency` — Cadastra uma moeda (code, name, symbol, decimal_places, enabled).
- `list-currencies` — Lista moedas paginadas; --enabled-only filtra apenas habilitadas.
- `add-exchange-rate` — Registra uma taxa de câmbio manual para um par/data.
- `get-exchange-rate` — Retorna a taxa vigente de um par na data (ou a mais recente anterior).
- `list-exchange-rates` — Lista taxas com filtros por par e intervalo de datas.
- `fetch-exchange-rates` — Busca taxas atuais na frankfurter.dev (base USD) e faz upsert com source='api'.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-currency: --code (obrigatório), --name, --symbol, --decimal-places, --enabled. add-exchange-rate: --from-currency, --to-currency, --rate (obrigatórios), --effective-date, --source. get/list-exchange-rates: --from-currency, --to-currency, --from-date, --to-date. |
| **Saídas** | add-currency: code, name. add-exchange-rate: exchange_rate_id, effective_date. get-exchange-rate: rate, effective_date, source. list-*: listas paginadas com total_count/has_more. fetch-exchange-rates: rates_updated, source, base, date. |
| **Regras de negócio** | code armazenado em maiúsculas; decimal_places default 2. Códigos de moeda duplicados são rejeitados. effective_date default = hoje (UTC); source default 'manual'. get-exchange-rate seleciona a taxa com effective_date <= data, ordenada desc (mais recente). fetch-exchange-rates fixa from='USD', effective_date=hoje e faz update se já existir o par+data, senão insert. |
| **Efeitos colaterais** | INSERT em currency e exchange_rate; fetch-exchange-rates faz INSERT/UPDATE em exchange_rate. Grava audit_log (create/fetch). fetch-exchange-rates realiza chamada HTTP externa (api.frankfurter.dev). Nenhuma postagem em gl_entry/SLE. |
| **Pré-condições** | Banco inicializado. fetch-exchange-rates requer conexão à internet. add-exchange-rate funciona com quaisquer códigos (não valida FK contra currency). |

## Condições de Pagamento

**Objetivo.** Cadastrar condições/prazos de pagamento (dias para vencimento, descontos por antecipação) reutilizáveis em faturas de venda e compra.

**Ações:**
- `add-payment-terms` — Cria uma condição de pagamento com prazo, percentual e dias de desconto.
- `list-payment-terms` — Lista condições paginadas, ordenadas por due_days e nome.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-payment-terms: --name (obrigatório), --due-days (default 30), --discount-percentage, --discount-days, --description. list-payment-terms: --limit, --offset. |
| **Saídas** | add-payment-terms: payment_terms_id, name. list-payment-terms: terms[], total_count, limit, offset, has_more. |
| **Regras de negócio** | Nome duplicado é rejeitado (IntegrityError). due_days default 30 quando não informado; demais campos opcionais. Somente cadastro/listagem (sem ciclo rascunho/submit). |
| **Efeitos colaterais** | INSERT em payment_terms. Grava audit_log (create). Nenhuma postagem em gl_entry/SLE. |
| **Pré-condições** | Banco inicializado. |

## Unidades de Medida

**Objetivo.** Manter unidades de medida (UoM) e fatores de conversão entre elas, opcionalmente específicos por item, para uso em estoque, vendas e compras.

**Ações:**
- `add-uom` — Cria uma unidade de medida; --must-be-whole-number força quantidades inteiras.
- `list-uoms` — Lista UoMs paginadas, ordenadas por nome.
- `add-uom-conversion` — Registra um fator de conversão entre duas UoMs, opcionalmente vinculado a um item.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-uom: --name (obrigatório), --must-be-whole-number. add-uom-conversion: --from-uom, --to-uom, --conversion-factor (obrigatórios), --item-id. |
| **Saídas** | add-uom: uom_id, name. add-uom-conversion: uom_conversion_id. list-uoms: uoms[], total_count, has_more. |
| **Regras de negócio** | Nome de UoM duplicado é rejeitado. add-uom-conversion exige os três campos; falha de integridade (duplicidade/dados inválidos) retorna erro. --item-id opcional permite conversão específica do item. |
| **Efeitos colaterais** | INSERT em uom e uom_conversion. Grava audit_log (create). Nenhuma postagem em gl_entry/SLE. |
| **Pré-condições** | Banco inicializado. As UoMs referenciadas na conversão devem existir como cadastro (não há FK forte verificada no código). |

## Usuários e Acessos (RBAC)

**Objetivo.** Gerenciar contas de usuário do ERP, seu vínculo a empresas, senha de login web e atribuição/revogação de papéis para controle de acesso.

**Ações:**
- `add-user` — Cria um usuário (username via --name), e-mail e nome completo, opcionalmente vinculado a uma empresa.
- `update-user` — Atualiza username/e-mail/nome/status e anexa empresa à lista company_ids.
- `list-users` — Lista usuários paginados, ordenados por username.
- `get-user` — Retorna um usuário com seus papéis (join user_role/role/company).
- `set-password` — Define a senha de login web do usuário (hash armazenado).
- `assign-role` — Atribui um papel a um usuário, opcionalmente com escopo de empresa.
- `revoke-role` — Remove a atribuição de um papel de um usuário (NULL-safe por empresa).

| Campo | Detalhe |
|---|---|
| **Entradas** | add-user: --name (username), --email, --full-name, --company-id. update-user: --user-id + campos + --user-status (active\|disabled\|locked). set-password: --user-id, --password (>=8). assign/revoke-role: --user-id, --role-name, --company-id (NULL=global). |
| **Saídas** | add-user/update-user: user_id, updated_fields. get-user: registro do usuário + roles[]. set-password: mensagem de sucesso. assign-role: user_role_id, role_name, company_id. revoke-role: revoked, user_id. |
| **Regras de negócio** | username único (rejeita duplicado). Formato de e-mail validado por regex. user-status restrito a active/disabled/locked. company_ids é JSON-array (append sem duplicar). set-password exige >=8 caracteres e grava password_hash. assign-role usa comparação NULL-safe (company_id IS ?) e rejeita atribuição já existente; revoke-role erra se não houver atribuição. |
| **Efeitos colaterais** | INSERT/UPDATE em erp_user; INSERT/DELETE em user_role; set-password faz UPDATE de password_hash (via passwords.hash_password). Grava audit_log (add-user/update-user/set-password/assign-role/revoke-role). Nenhuma postagem em gl_entry/SLE. O RBAC é opt-in: a criação de usuários ativa a checagem de permissões no sistema. |
| **Pré-condições** | Banco inicializado. assign-role exige usuário e papel existentes (papéis-sistema vêm seeded). set-password exige usuário existente. company_id opcional deve referenciar empresa válida. |

## Papéis e Permissões

**Objetivo.** Definir papéis (roles) e a matriz de permissões skill/ação que governa o que cada papel pode executar, incluindo o carregamento das permissões padrão.

**Ações:**
- `add-role` — Cria um papel customizado (is_system=0) com nome e descrição.
- `list-roles` — Lista papéis com contagem de usuários, papéis-sistema primeiro.
- `seed-permissions` — Popula role_permission com a matriz padrão por papel (idempotente).

| Campo | Detalhe |
|---|---|
| **Entradas** | add-role: --name (obrigatório), --description. list-roles: sem parâmetros. seed-permissions: sem parâmetros. |
| **Saídas** | add-role: role_id, name. list-roles: roles[] (com user_count), count. seed-permissions: permissions_seeded (total na tabela). |
| **Regras de negócio** | Nome de papel duplicado é rejeitado. Resolução de permissão: sem erp_user => permite tudo (RBAC inativo); papel 'System Manager' => permite tudo (padrão '*','*'); senão casa skill+action_pattern (wildcards fnmatch como list-*, submit-*, *); sem regra => nega. seed-permissions usa INSERT OR IGNORE por papel/skill/pattern, sendo idempotente. |
| **Efeitos colaterais** | INSERT em role; seed-permissions faz INSERT OR IGNORE em role_permission. add-role grava audit_log (add-role). Nenhuma postagem em gl_entry/SLE. |
| **Pré-condições** | Banco inicializado. seed-permissions depende dos papéis já existirem (papéis-sistema seeded no init_db) — pula papéis ausentes. |

## Integração Telegram

**Objetivo.** Vincular contas de usuário do ERP a IDs numéricos do Telegram e verificar permissões de ações executadas via bot do Telegram.

**Ações:**
- `link-telegram-user` — Vincula um ID numérico do Telegram a um usuário do ERP.
- `unlink-telegram-user` — Remove o vínculo de Telegram do usuário.
- `check-telegram-permission` — Verifica se o usuário Telegram tem permissão para uma skill/ação.

| Campo | Detalhe |
|---|---|
| **Entradas** | link: --user-id, --telegram-user-id (obrigatórios). unlink: --telegram-user-id. check: --telegram-user-id, --skill, --check-action (obrigatórios). |
| **Saídas** | link/unlink: user_id, telegram_user_id, linked/unlinked. check: allowed (bool), user_id, skill, action; se não vinculado retorna allowed=false com reason='not_linked'. |
| **Regras de negócio** | Um telegram_user_id não pode estar vinculado a outro usuário (rejeita conflito). unlink erra se não houver usuário vinculado. check resolve telegram_user_id->erp_user (apenas status='active') e aplica check_permission; se não vinculado, nega sem erro. |
| **Efeitos colaterais** | UPDATE em erp_user (campo telegram_user_id set/clear). Grava audit_log (link/unlink). check-telegram-permission é somente leitura. Nenhuma postagem em gl_entry/SLE. |
| **Pré-condições** | Banco inicializado. link exige usuário existente. check pressupõe RBAC povoado (papéis/permissões seeded) para resultado significativo; com RBAC inativo permite tudo. |

## Credenciais de Integração

**Objetivo.** Armazenar e gerenciar de forma criptografada as credenciais (API keys) de integrações externas, substituindo a passagem de --api-key em linha de comando.

**Ações:**
- `set-credential` — Grava uma credencial de integração no arquivo criptografado (valor via --value, --from-stdin ou --from-env).
- `get-credential` — Informa se uma credencial existe e um preview redigido; nunca retorna o valor.
- `list-credentials` — Lista apenas os nomes de integração com credencial armazenada.
- `delete-credential` — Remove uma credencial armazenada.
- `migrate-credentials` — Migra credenciais em texto puro de tabelas de add-ons (ex.: stripe_account.api_key) para o store criptografado; --dry-run pré-visualiza.

| Campo | Detalhe |
|---|---|
| **Entradas** | set-credential: --integration + (--value \| --from-stdin \| --from-env VAR). get/delete-credential: --integration. migrate-credentials: --dry-run. |
| **Saídas** | set: mensagem, integration, credentials_file. get: integration, exists, redacted_preview. list: integrations[]. delete: deleted (bool). migrate: dry_run, moved[], skipped[]. |
| **Regras de negócio** | O valor nunca é aceito via --api-key e nunca é retornado por get/list. set-credential sobrescreve entrada existente. migrate-credentials pula integrações já no store e, fora de dry-run, anula a coluna de origem após mover. get-credential exige valor com >=12 chars para mostrar preview. |
| **Efeitos colaterais** | Grava/lê o arquivo criptografado ~/.config/erpclaw/credentials.json.enc (AES-256-GCM, mode 0600), criptografado com a master key da máquina. migrate-credentials faz UPDATE nas tabelas de add-on (ex.: stripe_account.api_key=NULL) e commit. NÃO grava em audit_log. Nenhuma postagem em gl_entry/SLE. |
| **Pré-condições** | Banco inicializado. Master key disponível/gerada automaticamente (~/.config/erpclaw/master.key). migrate-credentials requer as tabelas de add-on presentes (tolerado se ausentes). |

## Campos Personalizados (UDF)

**Objetivo.** Permitir que administradores estendam tabelas-núcleo com campos definidos pelo usuário (UDF), com validação de tipo, e armazenem/recuperem seus valores por linha.

**Ações:**
- `add-custom-field` — Registra a definição de um campo personalizado em uma tabela-núcleo (tipo, label, required, default, options).
- `list-custom-fields` — Lista definições de campos personalizados, opcionalmente por --table.
- `remove-custom-field` — Remove a definição e seus valores armazenados (hard delete, exige --confirm se houver valores).
- `set-custom-field-value` — Define um valor de campo personalizado em uma linha, com validação.
- `get-custom-field-values` — Retorna os valores personalizados de uma linha (todos ou um campo).

| Campo | Detalhe |
|---|---|
| **Entradas** | add: --table, --field-name, --field-type (text\|int\|float\|date\|select\|link\|json), --label, --required, --default, --options, --skill-name. remove: --table, --field-name, --confirm. set-value: --table, --row-id, --field-name, --value. get-values: --table, --row-id, --field-name. |
| **Saídas** | add: custom_field_id, table, field_name, field_type. list: custom_fields[], count. remove: deleted_values. set-value: stored. get-values: custom_fields{}. |
| **Regras de negócio** | field-type restrito à lista válida. options: select -> JSON {values:[...]} a partir de lista por vírgula; link -> {table:...}; outros -> JSON bruto. Campo duplicado na mesma tabela é rejeitado. remove com valores existentes exige --confirm e checa owner_skill (rejeita por mismatch). set-value valida o valor (validate_custom_field_values) antes de gravar. |
| **Efeitos colaterais** | INSERT/DELETE em custom_field e INSERT/DELETE/UPSERT em custom_field_value (via lib custom_fields). add/remove gravam audit_log (create/delete); set-value não grava audit. Nenhuma postagem em gl_entry/SLE. |
| **Pré-condições** | Banco inicializado e tabelas custom_field/custom_field_value presentes. A tabela-alvo (--table) e a linha (--row-id) devem existir para set/get de valores. |

## Registros de Tipos e Status

**Objetivo.** Administrar em runtime os registros que são fonte de verdade para tipos de conta, tipos de comprovante (voucher) e validar a completude desses registros frente aos dados vivos.

**Ações:**
- `add-account-type` — Registra um novo account_type para que contas possam usá-lo.
- `list-account-types` — Lista account_types ativos (ou todos com --include-inactive).
- `deactivate-account-type` — Soft-disable de account_type (bloqueado se alguma conta o usa).
- `add-voucher-type` — Registra um voucher_type para uma tabela-alvo (gl_entry|stock_ledger_entry|payment_allocation).
- `list-voucher-types` — Lista voucher_types, opcionalmente por --target-table.
- `deactivate-voucher-type` — Soft-disable de voucher_type por tabela-alvo (bloqueado se linhas vivas o usam).
- `validate-registry-completeness` — Diagnóstico read-only: valores de tipo/status presentes em dados vivos mas não registrados+ativos.

| Campo | Detalhe |
|---|---|
| **Entradas** | add-account-type: --account-type, --label, --skill-name. add-voucher-type: --voucher-type, --target-table (lista fixa), --label, --skill-name. deactivate-*: o respectivo tipo (+ --target-table). list-*: --include-inactive, --target-table. |
| **Saídas** | add-*: result='registered' + valores. list-*: listas + count. deactivate-*: result='deactivated'. validate-registry-completeness: complete (bool), unregistered_in_use{} por categoria. |
| **Regras de negócio** | Tipo já registrado é rejeitado. target_table de voucher restrita a gl_entry/stock_ledger_entry/payment_allocation. deactivate bloqueia se houver account/linha usando o tipo (conta COUNT na tabela alvo). validate cruza valores DISTINCT em account/gl_entry/payment_entry/payment_ledger_entry/asset contra os registros ativos; novos writes com valores não registrados+ativos seriam rejeitados. |
| **Efeitos colaterais** | INSERT/UPDATE em account_type_registry e voucher_type_registry (is_active). add/deactivate gravam audit_log (create/update). validate-registry-completeness é somente leitura. Nenhuma postagem em gl_entry/SLE (apenas leitura dessas tabelas para contagem). |
| **Pré-condições** | Banco inicializado com as tabelas de registro (M0). deactivate exige que nenhuma linha viva use o valor. |

## Backup e Restauração

**Objetivo.** Criar, listar, verificar e restaurar backups da base SQLite, com suporte a criptografia AES-256, política de retenção e rollback de segurança na restauração.

**Ações:**
- `backup-database` — Cria backup da base, opcionalmente criptografado (--encrypt --passphrase) com master key embutida.
- `list-backups` — Lista arquivos de backup (.sqlite e .enc) com tamanho, data e flag de criptografia.
- `verify-backup` — Valida um backup sem restaurar (SQLite válido, assinatura ERPClaw, integrity_check).
- `restore-database` — Restaura a base de um backup, com backup de segurança prévio e rollback em caso de falha.
- `cleanup-backups` — Remove backups antigos por retenção (7 diários, 4 semanais, 12 mensais).

| Campo | Detalhe |
|---|---|
| **Entradas** | backup-database: --db-path, --backup-path, --encrypt, --passphrase. verify/restore: --backup-path, --passphrase (se .enc). cleanup-backups: sem parâmetros. |
| **Saídas** | backup: backup_path, size_bytes, encrypted, carries_master_key, timestamp. list: backups[], count, total_size_bytes. verify: valid, integrity, tables, schema_version, encrypted. restore: restored_from, safety_backup, integrity, was_encrypted. cleanup: kept, deleted, freed_bytes. |
| **Regras de negócio** | --encrypt exige --passphrase. Backups criptografados (ECRYPT02) embutem a master key envelopada para restauração cross-machine. verify exige schema_version e integrity_check='ok'. restore valida o backup, cria safety backup, copia sobre a base e reverifica; qualquer falha faz rollback para o safety backup. cleanup aplica retenção diária/semanal/mensal só a arquivos erpclaw_backup_*.sqlite. |
| **Efeitos colaterais** | Cria/copia/remove arquivos no diretório de backups (~/.openclaw/erpclaw/backups), com chmod 600. restore-database FECHA a conexão atual, SOBRESCREVE o arquivo data.sqlite e reaplica chmod nos arquivos da base (substituição total dos dados). cleanup/restore gravam audit_log (cleanup; backup/restore não gravam audit). Nenhuma postagem em gl_entry/SLE. |
| **Pré-condições** | Banco existente para backup. restore/verify exigem arquivo de backup válido e --passphrase para criptografados. Permissões de escrita no diretório de backups e na base. |

## Schema e Migrações

**Objetivo.** Inicializar/reinicializar o schema completo do banco e aplicar migrações de evolução de schema registradas em um ledger idempotente.

**Ações:**
- `initialize-database` — Cria todas as tabelas, índices e constraints (CREATE IF NOT EXISTS); --force dropa e recria.
- `migrate` — Executa migrações pendentes (migrations/NNN_*.py) registrando cada uma no ledger; --dry-run lista sem aplicar.
- `get-schema-version` — Lê a versão de schema registrada para um módulo.

| Campo | Detalhe |
|---|---|
| **Entradas** | initialize-database: --db-path, --force. migrate: --db-path, --dry-run. get-schema-version: --module (default 'erpclaw-setup'). |
| **Saídas** | initialize-database: message, db_path, tables, indexes, skills_registered, journal_mode='WAL', foreign_keys='ON', reinitialized. migrate: resultado do runner (aplicadas/pendentes). get-schema-version: module, version, updated_at. |
| **Regras de negócio** | initialize-database é seguro em base existente (IF NOT EXISTS); --force exige remoção do arquivo antes de recriar. migrate é idempotente e dialect-aware, gravando no ledger erpclaw_schema_migration; falha de uma migração aborta com detalhe. Ambas gerenciam suas próprias conexões (não usam a conexão padrão do router). |
| **Efeitos colaterais** | initialize-database cria o symlink da lib compartilhada, executa o DDL completo e aplica chmod 600 (data.sqlite, -wal, -shm); com --force REMOVE o arquivo da base existente. migrate altera estrutura de tabelas (rebuilds) e insere linhas no ledger de migração. Nenhuma postagem em gl_entry/SLE; não grava audit_log. |
| **Pré-condições** | Diretório/permissões de escrita da base. Módulo init_schema e migration_runner co-localizados. get-schema-version exige a tabela schema_version povoada. |

## Dados Padrão e Onboarding

**Objetivo.** Carregar dados-semente padrão (moedas, UoMs, condições de pagamento) e conduzir a configuração inicial via tutorial demo ou wizard interativo de onboarding.

**Ações:**
- `seed-defaults` — Carrega seeds padrão de currency/uom/payment_terms a partir dos assets JSON (idempotente).
- `tutorial` — Cria a empresa demo 'Acme Corp' com plano de contas mínimo, centro de custo e ano fiscal (idempotente).
- `onboarding-step` — Wizard interativo state-machine (nome->moeda->mês fiscal->demo) que ao final cria empresa, seeds e plano de contas.

| Campo | Detalhe |
|---|---|
| **Entradas** | seed-defaults: --company-id (default 1ª empresa). tutorial: sem parâmetros. onboarding-step: --answer (resposta do passo), --reset (reinicia do passo 1). |
| **Saídas** | seed-defaults: currencies_seeded, uoms_seeded, payment_terms_seeded. tutorial: company_id, accounts_created, fiscal_year, cost_center, next_steps[]. onboarding-step: step, completed, prompt, options, field e (no fim) results com steps_completed/steps_failed. |
| **Regras de negócio** | seed-defaults usa INSERT OR IGNORE (não duplica). tutorial é idempotente: se 'Acme Corp' existe, retorna dados existentes. onboarding valida moeda (lista fixa USD/EUR/GBP/CAD/INR/SGD/AED) e mês 1-12; persiste estado em arquivo JSON; no passo final dispara subprocessos (setup-company, seed-defaults, setup-chart-of-accounts via erpclaw-gl, seed-demo-data) registrando sucesso/falha por passo. |
| **Efeitos colaterais** | seed-defaults: INSERT OR IGNORE em currency/uom/payment_terms + audit_log (seed). tutorial: INSERT em company/account (plano de contas)/cost_center/fiscal_year + UPDATE contas-padrão + audit_log (create). onboarding: grava arquivo de estado ~/.openclaw/erpclaw/onboarding_state.json e executa db_query.py de outras skills via subprocess. Nenhuma postagem direta em gl_entry/SLE. |
| **Pré-condições** | Banco inicializado. seed-defaults exige uma empresa existente e os arquivos de assets (currencies.json, default_uom.json, default_payment_terms.json). onboarding com demo depende das skills erpclaw-gl/erpclaw presentes (passos faltantes são reportados como falhos, não fatais). |

## Config. Regionais/Avançadas

**Objetivo.** Definir configurações regionais por empresa (formato de data/número, template de imposto padrão) persistidas com upsert por chave.

**Ações:**
- `update-regional-settings` — Define/atualiza configurações regionais da empresa (date_format, number_format, default_tax_template_id) via upsert chave/valor.

| Campo | Detalhe |
|---|---|
| **Entradas** | --company-id (default 1ª empresa), --date-format, --number-format, --default-tax-template-id. |
| **Saídas** | updated: lista das chaves atualizadas. |
| **Regras de negócio** | Sem nenhuma configuração informada retorna erro. Cada par chave/valor é gravado por UPSERT em regional_settings com ON CONFLICT(company_id, key) atualizando value e updated_at. Default para a primeira empresa quando --company-id ausente. |
| **Efeitos colaterais** | INSERT/UPSERT em regional_settings. Grava audit_log (update). Nenhuma postagem em gl_entry/SLE. |
| **Pré-condições** | Banco inicializado e ao menos uma empresa existente. default_tax_template_id deve referenciar um template de imposto válido se usado por outras skills. |

## Auditoria/Status/Chave-Mestra

**Objetivo.** Consultar a trilha de auditoria, reportar o status geral do sistema e gerenciar a chave-mestra de criptografia em cenários de restauração entre máquinas.

**Ações:**
- `get-audit-log` — Consulta a trilha de auditoria com filtros por entidade, ação e período.
- `status` — Reporta contagens de empresas, moedas habilitadas, UoMs, condições de pagamento e versões de schema.
- `import-master-key-from-backup` — Extrai e instala a chave-mestra envelopada de um backup ECRYPT02 (restauração cross-machine).

| Campo | Detalhe |
|---|---|
| **Entradas** | get-audit-log: --entity-type, --entity-id, --audit-action, --from-date, --to-date, --limit (default 50). status: sem parâmetros. import-master-key-from-backup: --backup-path + passphrase (--passphrase \| --passphrase-from-stdin \| --passphrase-from-env VAR), --force. |
| **Saídas** | get-audit-log: entries[] (com old_values/new_values em JSON parseado), ordenadas desc por timestamp. status: companies, currencies, uoms, payment_terms, schema_versions{}. import-master-key: message, master_key_path, next. |
| **Regras de negócio** | get-audit-log e status são somente leitura. import-master-key exige backup formato ECRYPT02 que carregue a chave envelopada; desenvelopa com a passphrase (erra se não casar); recusa sobrescrever chave existente sem --force (overwrite invalida dados encriptados pela chave antiga). |
| **Efeitos colaterais** | get-audit-log e status: nenhum (somente leitura). import-master-key-from-backup: lê o header do backup e ESCREVE o arquivo ~/.config/erpclaw/master.key (mode 0600), opcionalmente removendo a chave existente com --force; não grava audit_log. Nenhuma postagem em gl_entry/SLE. |
| **Pré-condições** | Banco inicializado para status/audit. import-master-key exige arquivo de backup ECRYPT02 acessível com chave-mestra embutida (backups de fundação >= v4.1.3) e a passphrase usada no envelopamento. |

