# Próxima sessão

Atualizado em 2026-11-10 · Estado: **v0.7.0** · `main` e tag `v0.7.0` publicados no GitHub

---

## 1. Verificação rápida

```bash
! git log --oneline -5
! git status
! scripts/check.sh          # deve passar 222 testes
```

A URL SSH está configurada em `.git/config` como `git@github-empossados:empossados2021-del/backup-lc.git`.

---

## 2. Estado atual do projeto

| Etapa | Versão | Situação |
|---|---|---|
| E1 — Fundação e base visual | v0.1.0 | Concluída (produção: **v0.1.0** — aguarda implantação de v0.7.0) |
| E2 — Acesso e cadastro | v0.2.0 | Concluída |
| E2.1 — Usuários e perfil Operador | v0.6.0 | Concluída |
| E2.2 — Tipos de dispositivo | v0.6.0 | Concluída |
| E2.3 — Agendamento configurável | v0.6.0 | Concluída |
| E3 — Coleta de configuração | v0.3.0 | Concluída |
| E4 — Agendamento e histórico | v0.4.0 | Concluída |
| E5 — Dashboard de saúde | v0.5.0 | Concluída |
| E6 — Piloto com switch real | — | **Bloqueada** (P-01..P-04) |
| E6.1 — Driver MikroTik RouterOS | v0.6.0 | Concluída |
| E7.1 — Histórico de ciclos | v0.6.0 | Concluída |
| E7.2 — Restore por data | v0.6.0 | Concluída |
| E7.3 — Retenção automática | v0.7.0 | Concluída |
| E7.4 — Runbooks | v0.7.0 | Concluída |
| UI — Redesign denso/técnico | v0.7.0 | Concluído |

---

## 3. O que a v0.7.0 entregou

### E7.3 — Retenção automática
- `storage/retention.py`: `run_retention_cleanup(db, data_dir, retention_days)`
- Job no APScheduler: diariamente às 03:00 no fuso `BLC_TIMEZONE`
- `BLC_RETENTION_DAYS` (padrão 365, `ge=0`; `0` = desabilitado)
- Deduplicação reversa: arquivo só é removido quando nenhuma outra `ConfigVersion` referencia o mesmo `sha256_raw`
- 6 testes (total 222)

### E7.4 — Runbooks
- `docs/runbooks/instalacao.md` atualizado: `.env` com `BLC_RETENTION_DAYS`, recuperação de desastre, checklist de segurança
- `docs/runbooks/backup-dados.md` novo: `sqlite3 .backup` + `rsync`, alternativas LVM/ZFS, cron sugerido, script de referência

### UX — Redesign denso/técnico
- Login split-screen: painel escuro com branding + painel claro com formulário
- Stat cards com fundo colorido por status
- Dashboard, page-head e tabelas com visual mais denso/técnico
- Sidebar com rótulos de texto no desktop
- 9 classes CSS faltantes corrigidas (login, flash--error, flash--info, badge--error/running, form__row, etc.)

---

## 4. Próximas tarefas

### 4.1 Desbloqueadas agora
- **Implantar v0.7.0** em produção (G-1 concluído — tag no GitHub; falta G-2 e G-3 no servidor):
  ```bash
  git -C /opt/backup-lc fetch --tags
  git -C /opt/backup-lc checkout v0.7.0
  docker compose -f /opt/backup-lc/compose.yaml up -d --build   # G-2 se baixar pacotes
  curl http://localhost:8080/health/ready                         # G-3 já aberto
  ```
- Trocar chave SSH de push (root) por deploy key somente leitura

### 4.2 Bloqueadas (aguardam cliente)
- **E6 — Piloto real**: precisa de P-01 (fabricantes/modelos), P-02 (conta SSH), P-03 (rede/TLS), P-04 (horário)

### 4.3 Riscos pendentes
- Produção em v0.1.0 (HTTP, sem login) — mitigar com `BLC_BIND=127.0.0.1` até a implantação de v0.7.0
- Sem TLS — proxy reverso ou certificado antes da E6 real
- Chave SSH de push (root) no servidor de produção

---

## 5. Arquitetura rápida

```
src/backuplc/
  auth/          → login, sessões, CSRF, RBAC (admin/operator/reader)
  collector/     → driver.py (DriverSpec), runner.py, service.py, models.py
  core/          → config (BLC_*), db, migrate, settings_store
  dashboard/     → health.py, charts, spark (SVG server-side)
  devices/       → models (Device, Credential), service
  history/       → service.py (get_cycles, get_cycle_executions)
  migrations/    → v0001–v0005 (Alembic)
  scheduler/     → service.py (lifespan + run_all_devices + retention_cleanup), runner.py
  storage/       → store.py, diff.py, models.py, retention.py
  web/           → app.py, routes.py, middleware.py, templates/, static/css/app.css
```
