# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões seguem SemVer.

## [Não lançado]

### Adicionado
- `docs/ESTADO.md` (estado do projeto e próximos passos), `docs/DESENVOLVIMENTO.md` (guia da VM de desenvolvimento) e `CLAUDE.md` (regras para assistentes de IA).
- ADR-013: desenvolvimento em VM local; produção só recebe versões marcadas.

### Alterado
- Regras R-01/R-02 do PRD, plano (seção de ambientes e fase F de implantação) e runbook (implantação por tag) refletem a ADR-013.
- `scripts/init.sh` lê o `.env` do repositório, permitindo caminhos de desenvolvimento.
- Removido o nome de usuário do servidor dos exemplos da documentação.

## [0.6.1] — 2026-11-10 — Redesenho do layout e Restore unificado

### Adicionado
- **Rota `/restore` unificada**: seleção de dispositivo via `<select>` + filtro por data em uma única página; substitui o `/devices/{id}/restore` por rota.
- **Botão Restore na listagem de dispositivos** (`/devices`, `/mikrotik`): todos os perfis autenticados veem o link direto para o restore do dispositivo.

### Alterado
- **Layout completo redesenhado**: topbar escura de 54 px cobrindo toda a largura + sidebar estreita de 64 px com ícones SVG (sem texto visível) + área de conteúdo branca; elimina o overflow de itens no nav.
- **CSS reescrito** (`app.css`): variáveis `--chrome-bg`, `--sidenav-w`, `--topbar-h`; classes `grid-4`, `dash-health`, `card--stacked`; conjunto completo de classes para gráficos SVG do dashboard; aliases `stat--healthy/attention/critical/inactive`; botões `.button--ghost/--danger/--sm`; responsivo para mobile (<768 px sidebar horizontal).
- **Dashboard** (`/`): quatro cards horizontais (`grid-4`) com donut, saudáveis, atenção+críticos e inativos.
- Rota antiga `/devices/{id}/restore` → redirect 301 para `/restore?device={id}`.
- Versão `0.6.0 → 0.6.1`; cache-bust do CSS atualizado.

### Removido
- Nenhum comportamento removido; a rota antiga redireciona para a nova.

## [0.6.0] — 2026-11-09 — E2.1, E2.2, E2.3, E6.1, E7.1, E7.2

### Adicionado
- **Perfil Operador** (`operator`): 3 papéis (admin/operator/reader); gestão de usuários pela UI (`/users`).
- **Tipos de dispositivo**: `generic` e `mikrotik_routeros`; página `/mikrotik` separada na nav.
- **Driver MikroTik RouterOS**: Netmiko `mikrotik_routeros`; pré-comando desabilita paginação; `/export`; captura `ReadTimeout`.
- **Agendamento configurável** (`/settings`): UI hora/minuto; reprograma APScheduler em tempo real; fuso configurável via `BLC_TIMEZONE` (padrão `America/Sao_Paulo`).
- **Histórico de ciclos** (`/history`): ciclos por minuto, filtro por origem (manual/agendado), detalhe com badges de estado.
- **Restore por data** (`/devices/{id}/restore`): busca versão por data UTC, download direto.
- **Migração v0005**: tabela `app_settings` para configurações persistentes.
- 185 testes novos (total 216: unit, integration, security).

### Corrigido
- `triggered_by` passava username em vez de user ID (FK para `users.id`).
- Validação de username vazio no formulário de novo usuário.
- Proteção contra auto-desativação de conta no formulário de edição.

## [0.5.0] — 2026-11-08 — E5 Dashboard de saúde

### Adicionado
- Módulo `backuplc.dashboard`: cálculo de saúde por dispositivo, sparkline SVG e donut SVG gerados no servidor.
- Dashboard real em `/` com 4 cards de estado, tabela de dispositivos, gráficos SVG e auto-refresh a cada 60 s.

## [0.4.0] — 2026-11-08 — E4 Agendamento e histórico

### Adicionado
- Módulo `backuplc.scheduler`: `AsyncIOScheduler` (APScheduler) com lifespan, retentativas automáticas (máx. 3), semáforo de concorrência, recuperação de execuções travadas na subida.
- Coleta de todos os dispositivos ativos (`/devices/collect-all`, `/mikrotik/collect-all`) com fire-and-forget assíncrono.
- Histórico de execuções; detalhe por ciclo com duração e badges de estado.

## [0.3.0] — 2026-11-07 — E3 Coleta de configuração

### Adicionado
- Módulo `backuplc.collector`: driver genérico e MikroTik (`DriverSpec`), runner (`collect_device`), verificação de chave de host SSH, validação de saída (tamanho mínimo, padrões de erro, marcador de fim).
- Módulo `backuplc.storage`: `save_config` com deduplicação por SHA-256, diff unificado no servidor, download de versões.
- Migração `v0004`: tabelas `config_versions`, `device_host_keys`, `executions`.
- Rota `/devices/{id}/collect` (POST); endpoint de download e diff de versões.

## [0.2.0] — 2026-11-06 — E2 Acesso e cadastro

### Adicionado
- Módulo `backuplc.auth`: usuários locais com Argon2id, sessões no banco com expiração por inatividade, CSRF por HMAC-SHA256, perfis admin/reader, bloqueio após falhas consecutivas.
- Módulo `backuplc.devices`: cadastro de switches (Device) e credenciais cifradas com Fernet (Credential).
- Migrações `v0002` (usuários e sessões) e `v0003` (credenciais e dispositivos).
- Login (`/login`), logout e proteção de todas as rotas por `AuthMiddleware`.
- CRUD de switches (`/devices`) e credenciais (`/credentials`).
- Comando CLI `create-admin` para criar o primeiro administrador.
- Cabeçalho `Cache-Control: no-store` em respostas HTML.

## [0.1.0] — 2026-11-04 — E1 Fundação e base visual

### Adicionado
- Pacote `backuplc` com comandos `serve`, `migrate`, `check-config` e `init-secrets`.
- Configuração por variáveis `BLC_*`; segredos lidos de arquivo e validados na subida, sem expor valores.
- Logs JSON com identificador de requisição e máscara central de segredos (chaves sensíveis, `chave=valor` e valores registrados).
- SQLite em modo WAL com SQLAlchemy 2 e Alembic; migração inicial com a tabela `events`.
- `/health/live` e `/health/ready` (banco, migrações, armazenamento).
- Base visual sem JavaScript: layout, tema claro/escuro, cores de estado e página inicial com o estado da plataforma.
- Cabeçalhos de segurança (CSP `script-src 'none'`, `X-Frame-Options`, `nosniff`, `no-referrer`).
- Dockerfile multiestágio (uid 10001, raiz somente leitura) e `compose.yaml` publicado em `0.0.0.0:8080` (ADR-012, substitui a ADR-011; configurável por `BLC_BIND`/`BLC_PORT`). Sem TLS e sem login até a E2.
- `scripts/init.sh`, `check.sh`, `fmt.sh`, `lock.sh`; 31 testes (unit, integration, security).
- Runbook de instalação.

### Dependências (travadas em `uv.lock`)
fastapi 0.156.4, starlette 1.9.0, uvicorn 0.54.0, jinja2 3.1.6, python-multipart 0.0.32, sqlalchemy 2.1.5, alembic 1.20.0, pydantic 2.14.1, pydantic-settings 2.16.1, argon2-cffi 25.1.0, cryptography 50.0.2 · dev: pytest 9.1.1, httpx 0.28.1, ruff 0.17.1, mypy 2.4.0 · uv 0.13.7.

## [E0] — 2026-11-04

### Adicionado
- PRD v2.0 simplificado, plano SDD com portões de aprovação, ADR-001 a ADR-011 e spec da E1.
