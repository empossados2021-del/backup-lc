# Spec E1 — Fundação e base visual

| Campo | Valor |
| --- | --- |
| Status | **Concluída** — aprovada em 2026-11-04, entregue em 2026-11-04 (v0.1.0) |
| Base | PRD v2.0 (N-03 a N-08, R-03, R-05), ADR-001 a ADR-011 |
| Data | 2026-11-04 |

## 1. Objetivo

Entregar o esqueleto executável do sistema: um container que sobe com um comando, valida a configuração, grava logs seguros, aplica migrações no SQLite, responde a health checks e exibe a casca visual (layout, tema claro/escuro, navegação) sobre a qual login, cadastro e dashboard serão construídos.

## 2. Escopo

1. Estrutura `src/backuplc/` (ver `docs/PLANO.md` seção 4) e `pyproject.toml` com dependências travadas em `uv.lock`.
2. **Configuração:** variáveis `BLC_*`; segredos lidos de arquivos (`BLC_SESSION_SECRET_FILE`, `BLC_MASTER_KEY_FILE`); validação na inicialização com mensagem que cita a variável inválida, nunca o valor.
3. **Logs:** JSON, um evento por linha, horário UTC, `request_id`; filtro central que mascara chaves sensíveis (`password`, `secret`, `token`, `key`, `authorization`, `cookie`).
4. **Banco:** SQLite em `BLC_DATA_DIR/backuplc.db`, modo WAL, `foreign_keys=ON`; SQLAlchemy 2 + Alembic; migração inicial com a tabela `events` (registro de eventos, F-11).
5. **Comandos:** `backuplc migrate`, `backuplc serve`, `backuplc check-config`, `backuplc init-secrets` (gera os arquivos de segredo com permissão 600).
6. **Web:** FastAPI + Jinja2; `GET /health/live`, `GET /health/ready` (banco acessível, migração em dia, diretório de dados gravável); página inicial com layout base e aviso "Dashboard em construção".
7. **Base visual:** `base.html` com cabeçalho, navegação e rodapé; CSS próprio com tokens de cor, tema claro e escuro por `prefers-color-scheme`, cores de estado (Saudável, Atenção, Crítico, Inativo) com contraste AA; responsivo até 360 px; **nenhum `<script>`**.
8. **Segurança HTTP:** cabeçalhos `Content-Security-Policy` com `script-src 'none'`, `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options: DENY`.
9. **Container:** Dockerfile multiestágio, usuário não root (uid 10001), sistema de arquivos somente leitura exceto `/data`, limite de memória 512 MB; `compose.yaml` com um serviço publicado **apenas em `127.0.0.1:8080`** (ADR-011).
10. **Qualidade:** `scripts/check.sh` roda Ruff, mypy e pytest em container com `--network none`; marcadores `unit`, `integration`, `security`.
11. **Documentação:** README (como subir), `CHANGELOG.md`, `docs/runbooks/instalacao.md`.

## 3. Fora do escopo

Login e usuários (E2), cadastro de switches e credenciais (E2), coleta (E3), dashboard real (E5), TLS e exposição em rede (P-03).

## 4. Critérios de aceite

| ID | Dado | Quando | Então |
| --- | --- | --- | --- |
| E1-01 | Um clone limpo no servidor | `scripts/init.sh` e `docker compose up -d` | O serviço fica saudável e `/health/ready` responde 200 |
| E1-02 | Um arquivo de segredo ausente ou vazio | A aplicação inicia | Ela recusa subir e o log cita a variável, sem o valor |
| E1-03 | A migração inicial | É revertida e reaplicada | O esquema volta igual |
| E1-04 | Valores canários como segredos e em campos de log | Fluxos de sucesso e erro rodam | Nenhum canário aparece em logs, banco ou arquivos gerados |
| E1-05 | Qualquer página HTML | É renderizada | Não contém `<script>` nem atributos `on*`; a CSP proíbe scripts |
| E1-06 | O container em execução | Seu processo é inspecionado | Roda como uid 10001, raiz somente leitura |
| E1-07 | O `compose.yaml` | É inspecionado | A porta só escuta em `127.0.0.1` |
| E1-08 | `scripts/check.sh` | Executa | Ruff, mypy e pytest passam, sem acesso à rede |
| E1-09 | Uma importação proibida (ex.: `core` importando `web`) | `check.sh` roda | O teste de dependências falha apontando o arquivo |

## 5. Ações com impacto em rede (aprovação necessária)

| Portão | Ação | Detalhe |
| --- | --- | --- |
| G-2 | Download da imagem base | `python:3.13-slim` (Docker Hub) — **já presente no servidor**, sem novo download |
| G-2 | Download de pacotes Python | De `pypi.org` / `files.pythonhosted.org`, uma vez, durante o build e a geração do `uv.lock`: `uv`, `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `sqlalchemy`, `alembic`, `pydantic-settings`, `argon2-cffi`, `cryptography`; dev: `pytest`, `httpx`, `ruff`, `mypy`. Versões registradas no `uv.lock` e informadas na entrega |
| G-1 | `git push` | Ao fim da etapa |
| — | Porta do dashboard | Não há: apenas `127.0.0.1` (acesso por túnel SSH) |

Após o build, testes e execução não acessam a rede.

## 6. Rastreabilidade

| Critério | Requisitos |
| --- | --- |
| E1-01, E1-03 | N-03, N-04, N-06 |
| E1-02, E1-04 | R-05, N-05 |
| E1-05 | R-03 |
| E1-06 | N-07 |
| E1-07 | R-02 |
| E1-08, E1-09 | R-06, ADR-009, ADR-010 |

## 7. Evidências de verificação (fase D)

Verificado em 2026-11-04 no servidor de produção, branch `e1/fundacao`.

| Critério | Resultado | Evidência |
| --- | --- | --- |
| E1-01 | Aprovado | `scripts/init.sh` + `docker compose up -d` → container `healthy`; `/health/ready` → `200 {"database":true,"schema":true,"storage":true}`; `GET /` e `HEAD /` → 200 |
| E1-02 | Aprovado | `check-config` com segredo ausente → saída 2, log `BLC_SESSION_SECRET_FILE: arquivo não encontrado`; testes `test_config.py` (8) confirmam que o valor inválido não aparece |
| E1-03 | Aprovado | `test_migracao_ida_e_volta`: upgrade → downgrade base → upgrade, esquema idêntico; `test_migrate_e_check_config` pelo CLI |
| E1-04 | Aprovado | `test_canarios_nao_vazam`: canários ausentes de logs, banco (incluindo WAL) e arquivos; `test_logs_sao_json_e_mascaram_segredos` |
| E1-05 | Aprovado | `test_frontend.py` (10): nenhum `<script>`, `on*`, `javascript:` ou `style=` nas páginas e templates; nenhum `.js` estático; CSP `script-src 'none'` confirmada também via `curl` |
| E1-06 | Aprovado | `id` no container → `uid=10001(app)`; `ReadonlyRootfs=true`, `CapDrop=[ALL]`, `no-new-privileges`, 512 MB; `touch /app/x` → `Read-only file system` |
| E1-07 | Aprovado | `docker port` → `8080/tcp -> 127.0.0.1:8080`; `ss -ltn` → escuta só em `127.0.0.1:8080` |
| E1-08 | Aprovado | `scripts/check.sh` com `--network none`: Ruff format/check OK, mypy estrito sem erros (19 arquivos), pytest 31 aprovados |
| E1-09 | Aprovado | Arquivo `core/violacao.py` importando `backuplc.web.app` (passa em Ruff e mypy) → `check.sh` falha: `backuplc/core/violacao.py:1: backuplc.core.violacao não pode importar backuplc.web.app`; arquivo removido em seguida |

**Ajustes feitos durante a verificação:**

- Imagem: código copiado com permissão do checkout (`0700`) impedia o usuário 10001 de ler o pacote; o Dockerfile agora fixa `root:root` e `go=rX` em `/app/src`.
- `umask 077` no processo: banco e arquivos de dados ficam `0600` (N-08).
- Logger do Alembic em WARNING (evita log a cada health check); campo `color_message` do uvicorn removido do JSON.

**Uso de rede (G-2, aprovado):** `uv` 0.13.7 e 43 pacotes do PyPI, uma vez, na geração do `uv.lock` e no build. Execução e testes sem rede.

**Pendência técnica registrada:** o Starlette 1.9 emite aviso de depreciação do `httpx` no `TestClient` (sugere `httpx2`). Sem impacto em produção; troca avaliada quando houver nova aprovação G-2.
