# Estado do projeto

**Atualizado em 2026-11-09** · Versão atual: **v0.6.0** · Próxima etapa: **E7.3 — Retenção automática** (bloqueada até P-06)

## 1. Resumo

E2 a E6.1 e E7.1–E7.2 estão concluídas. O sistema tem login, perfis (admin/operator/reader), cadastro de switches e credenciais cifradas, coleta Netmiko (generic e MikroTik RouterOS), agendamento configurável, histórico de ciclos, restore por data e dashboard de saúde com SVG gerado no servidor.

E6 (piloto real) está bloqueada aguardando informações do cliente (P-01 a P-04).

A partir de 2026-11-05 o desenvolvimento ocorre em VM local (ADR-013). O servidor de produção ainda está em **v0.1.0** (sem login) — implantação de v0.6.0 requer aprovação explícita (portões G-1, G-2, G-3).

## 2. Etapas

| Etapa | Versão | Situação | Referência |
| --- | --- | --- | --- |
| E0 — Especificação base | — | Concluída | PRD v2.0, `PLANO.md`, ADR-001 a 013 |
| E1 — Fundação e base visual | v0.1.0 | Concluída | [`specs/E1-fundacao.md`](specs/E1-fundacao.md) |
| E2 — Acesso e cadastro | v0.2.0 | Concluída | [`specs/E2-acesso-e-cadastro.md`](specs/E2-acesso-e-cadastro.md) |
| E2.1 — Usuários e perfil Operador | v0.6.0 | Concluída | [`specs/E2-acesso-e-cadastro.md`](specs/E2-acesso-e-cadastro.md) |
| E2.2 — Tipos de dispositivo | v0.6.0 | Concluída | [`specs/E2.2-tipos-de-dispositivo.md`](specs/E2.2-tipos-de-dispositivo.md) |
| E2.3 — Agendamento configurável | v0.6.0 | Concluída | [`specs/E2.3-agendamento-configuravel.md`](specs/E2.3-agendamento-configuravel.md) |
| E3 — Coleta de configuração | v0.3.0 | Concluída | [`specs/E3-coleta.md`](specs/E3-coleta.md) |
| E4 — Agendamento e histórico | v0.4.0 | Concluída | [`specs/E4-agendamento-e-historico.md`](specs/E4-agendamento-e-historico.md) |
| E5 — Dashboard de saúde | v0.5.0 | Concluída | [`specs/E5-dashboard.md`](specs/E5-dashboard.md) |
| E6 — Piloto com switch real | — | **Bloqueada** (P-01, P-02, P-03, P-04) | [`specs/E6-piloto.md`](specs/E6-piloto.md) |
| E6.1 — Driver MikroTik RouterOS | v0.6.0 | Concluída | [`specs/E6.1-driver-mikrotik.md`](specs/E6.1-driver-mikrotik.md) |
| E7 — Operação | — | Não iniciada | [`specs/E7-operacao.md`](specs/E7-operacao.md) |
| E7.1 — Histórico de ciclos | v0.6.0 | Concluída | [`specs/E7.1-historico-coletas.md`](specs/E7.1-historico-coletas.md) |
| E7.2 — Restore por data | v0.6.0 | Concluída | [`specs/E7.2-restore.md`](specs/E7.2-restore.md) |

## 3. O que existe no código (v0.6.0)

- Comandos `serve`, `migrate`, `check-config`, `init-secrets`, `create-admin`.
- Configuração `BLC_*` com segredos em arquivo; `BLC_TIMEZONE` e `BLC_MAX_CONCURRENT`.
- Logs JSON com máscara de segredos; tabela `events` com detalhe mascarado.
- SQLite (WAL) + Alembic; migrações v0001–v0005.
- `/health/live`, `/health/ready`; dashboard com SVG, auto-refresh, sparklines.
- Login Argon2id, sessões com expiração, CSRF HMAC-SHA256, perfis admin/operator/reader.
- CRUD de switches (generic + mikrotik_routeros) e credenciais Fernet.
- Coleta Netmiko com verificação de chave SSH, validação, deduplicação SHA-256, diff.
- Agendamento APScheduler com retentativas e recuperação pós-restart.
- Agendamento configurável via UI (`/settings`).
- Histórico de ciclos (`/history`) com detalhe, filtro e paginação.
- Restore por data (`/devices/{id}/restore`).
- CSS próprio, tema claro/escuro, nenhum JavaScript (CSP `script-src 'none'`).
- Container não root, raiz somente leitura, 512 MB; 216 testes.

## 4. Produção (situação em 2026-11-04)

| Item | Situação |
| --- | --- |
| Checkout | `/opt/backup-lc`, branch `main` em `v0.1.0` |
| Serviço | Container `backup-lc-app-1` rodando, `healthy`, publicado em `0.0.0.0:8080` (ADR-012) |
| Dados | `/var/lib/backup-lc` (uid 10001, `0700`): só o banco, sem dados de switches |
| Segredos | `/etc/backup-lc/secrets/{session_secret,master_key}` (uid 10001, `0400`) |
| Imagens Docker | `backuplc:latest`, `backuplc:dev`, `python:3.13-slim` |
| Firewall do host | Nenhum (INPUT ACCEPT, sem ufw) |

**Usos de rede já feitos em produção (para registro):** download da imagem `python:3.13-slim`; `pip` do `pypdf` dentro de um container descartável, para ler o PRD v1.1 (antes da regra R-02); `uv` e 43 pacotes do PyPI (G-2 aprovado); consultas e pushes ao GitHub (G-1 aprovado); publicação da porta 8080 (G-3 aprovado). Nenhuma conexão a switches.

## 5. Pendências do cliente

| ID | Pendência | Bloqueia |
| --- | --- | --- |
| P-01 | Fabricantes, modelos, versões de SO e quantidade de switches | E3 (drivers) |
| P-02 | Conta de serviço nos switches com privilégio mínimo | E6 |
| P-03 | Redes de origem permitidas e certificado TLS do dashboard (a porta já foi definida) | E6 |
| P-04 | Horário da coleta diária e janela permitida | E6 |
| P-06 | Retenção (proposta: 365 dias) | E7 |

## 6. Riscos e dívidas abertas

| Item | Ação recomendada | Quando |
| --- | --- | --- |
| Produção em v0.1.0 (sem login, HTTP) | Implantar v0.6.0 pelo runbook (G-1, G-2, G-3) | Com aprovação |
| Sem TLS | Proxy reverso ou certificado (nova ADR) | Antes da E6 real |
| Host sem firewall; Docker ignora ufw | Regras na cadeia `DOCKER-USER` ou firewall de rede | Antes da E6 |
| Cópia da `master_key` | Guardar fora do servidor, separada dos dados | Agora |
| Chave SSH de push no GitHub (root) | Trocar por deploy key somente leitura | Antes da próxima implantação |
| Aviso de depreciação `httpx` no TestClient | Avaliar `httpx2` ao atualizar dependências | Próxima atualização |

## 7. Próximos passos

1. **Push para o GitHub** (G-1): `git push origin main --follow-tags`.
2. **Implantar v0.6.0** em produção pelo runbook (G-1, G-2, G-3) — com aprovação explícita.
3. **E7.3 — Retenção automática**: job diário, `BLC_RETENTION_DAYS=365`, preserva última versão (aguarda P-06).
4. **E7.4 — Runbooks**: `docs/runbooks/instalacao.md` atualizado; `docs/runbooks/backup-dados.md` novo.
5. **E6 real** (bloqueada): aguardar P-01 (fabricantes/modelos), P-02 (conta SSH), P-03 (rede/TLS), P-04 (horário).
