# Próxima sessão

Atualizado em 2026-11-10 · Estado: **v0.6.1** · `main` e tag `v0.6.1` publicados no GitHub

---

## 1. Verificação rápida

```bash
! git log --oneline -5      # deve mostrar commits até e2ed14a (docs v0.6.1)
! git status                # deve estar limpo (exceto NEXT_SESSION.md)
! scripts/check.sh          # deve passar 216 testes
```

A URL SSH está configurada em `.git/config` como `git@github-empossados:empossados2021-del/backup-lc.git`.

---

## 2. Estado atual do projeto

| Etapa | Versão | Situação |
|---|---|---|
| E1 — Fundação e base visual | v0.1.0 | Concluída (produção: **v0.1.0**) |
| E2 — Acesso e cadastro | v0.2.0 | Concluída |
| E2.1 — Usuários e perfil Operador | v0.6.0 | Concluída |
| E2.2 — Tipos de dispositivo | v0.6.0 | Concluída |
| E2.3 — Agendamento configurável | v0.6.0 | Concluída |
| E3 — Coleta de configuração | v0.3.0 | Concluída |
| E4 — Agendamento e histórico | v0.4.0 | Concluída |
| E5 — Dashboard de saúde | v0.5.0 | Concluída |
| E6 — Piloto com switch real | — | **Bloqueada** (P-01..P-04) |
| E6.1 — Driver MikroTik RouterOS | v0.6.0 | Concluída |
| E7 — Operação | — | Em andamento |
| E7.1 — Histórico de ciclos | v0.6.0 | Concluída |
| E7.2 — Restore por data | v0.6.0/0.6.1 | Concluída |
| UI — Redesenho do layout | v0.6.1 | Concluída |

---

## 3. O que a v0.6.1 entregou (nesta sessão)

### Layout (redesenho completo)
- **Topbar escura** (54 px, `--chrome-bg: #0f172a`) cobrindo toda a largura
- **Sidebar estreita** (64 px) com ícones SVG, sem texto visível; item ativo com borda esquerda indigo
- **Área de conteúdo branca** (`--bg: #f1f5f9`) responsiva; sidebar colapsa para barra horizontal em <768 px
- Dashboard: 4 cards horizontais (`grid-4`) — donut, saudáveis, atenção+críticos, inativos
- CSS reescrito com todas as classes de gráfico SVG, aliases de estado e botões modificadores

### Restore unificado
- Rota `/restore` com `<select>` de dispositivo + `<input type="date">` na mesma página
- Botão "Restore" na listagem de dispositivos (`/devices`, `/mikrotik`) para todos os perfis
- Rota legada `GET /devices/{id}/restore` → redirect 301 para `/restore?device={id}`

### Documentação
- `CHANGELOG.md`: entrada `[0.6.1]`
- `docs/ESTADO.md`: versão, rota `/restore`, seção 3 e próximos passos atualizados
- `docs/specs/E7.2-restore.md`: rota, critérios e evidências revisados; critério E7.2-06 (redirect) adicionado
- `pyproject.toml` e `__init__.py`: 0.6.0 → 0.6.1

### Testes
216 testes — todos passando com `scripts/check.sh`.

---

## 4. Próximas tarefas de desenvolvimento

### 4.1 Desbloqueadas agora
- **Implantar v0.6.1** em produção pelo runbook (G-1 → G-2 → G-3) — com aprovação explícita de cada portão.
- **E7.3 — Retenção automática**: spec primeiro; job diário, `BLC_RETENTION_DAYS=365` (ou `app_settings`), preserva sempre a última versão por dispositivo; aguarda P-06.
- **E7.4 — Runbooks**: atualizar `docs/runbooks/instalacao.md`; criar `docs/runbooks/backup-dados.md`.

### 4.2 Bloqueadas (aguardam cliente)
- **E6 — Piloto real**: precisa de P-01 (fabricantes/modelos), P-02 (conta SSH), P-03 (rede/TLS), P-04 (horário da coleta)

### 4.3 Riscos pendentes
- Produção em v0.1.0 (HTTP, sem login) — mitigar com `BLC_BIND=127.0.0.1` até a implantação de v0.6.1
- Sem TLS — proxy reverso ou certificado antes da E6 real
- Chave SSH de push (root) no servidor de produção — trocar por deploy key somente leitura
- Aviso de depreciação `httpx` no TestClient — avaliar `httpx2` na próxima atualização de dependências

---

## 5. Arquitetura rápida

```
src/backuplc/
  auth/          → login, sessões, CSRF, RBAC (admin/operator/reader)
  collector/     → driver.py (DriverSpec), runner.py, service.py, models.py
  core/          → config, db, migrate, settings_store (app_settings)
  dashboard/     → health.py (compute_health), charts, spark
  devices/       → models (Device, Credential), service
  history/       → service.py (get_cycles, get_cycle_executions)
  migrations/    → v0001–v0005 (Alembic)
  scheduler/     → service.py (lifespan + AsyncIOScheduler), runner.py
  storage/       → store.py, diff.py, models.py (ConfigVersion)
  web/           → app.py, routes.py, middleware.py, templates/
    templates/
      base.html          → topbar + sidebar + main (zero JS)
      home.html          → dashboard grid-4
      restore/index.html → /restore (select + date)
      devices/list.html  → listagem com botão Restore
```

Regras de importação (`tests/archrules.py`):
- `core/` não importa domínio nem `web/`
- `collector/` não importa `web/`, `auth/`, `scheduler/`, `dashboard/`, `cli/`
- `web/` não importa `sqlalchemy` nem `cli/`

---

## 6. Commits recentes

```
e2ed14a  docs(v0.6.1): bump versão, changelog, estado e spec E7.2 atualizados
a204cd2  feat(ui): redesenho completo do layout — sidebar de ícones, topbar escura e restore unificado (v0.6.1)
00357c9  docs(specs): evidências de verificação de E2.2, E2.3 e E6.1 (v0.6.0)
62a2e67  feat(e6): perfil operador, mikrotik, agendamento configurável, histórico, restore (v0.6.0)
704f8b0  feat(e5): dashboard de saúde (v0.5.0)
```
