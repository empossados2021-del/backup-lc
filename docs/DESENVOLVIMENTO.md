# Guia de desenvolvimento (VM local)

Como montar o ambiente e trabalhar no backup-lc. Desenvolvimento acontece **somente** na VM de desenvolvimento; o servidor de produção só recebe versões marcadas (ADR-013).

## 1. Requisitos da VM

| Item | Recomendação |
| --- | --- |
| Sistema | Linux; de preferência Debian 13, igual à produção |
| Recursos | 2 vCPU, 4 GB de RAM, 20 GB de disco |
| Docker | Docker Engine com Compose v2+ (`docker compose version`) |
| Ferramentas | `git`, `python3` (usado só por `scripts/init.sh`), `curl` |
| GitHub | Chave SSH da VM cadastrada na sua conta (permite push) |

Python, `uv`, Ruff, mypy e pytest **não** precisam estar instalados na VM: rodam dentro da imagem `backuplc:dev`.

## 2. Primeira vez

```bash
git clone git@github.com:empossados2021-del/backup-lc.git
cd backup-lc

cp .env.example .env
# Edite o .env para o ambiente de desenvolvimento:
#   BLC_DATA_HOST=./data          (dados dentro do checkout; ignorado pelo git)
#   BLC_SECRETS_DIR=./secrets     (segredos de desenvolvimento; ignorado pelo git)
#   BLC_BIND=127.0.0.1            (só a própria VM acessa)

sudo scripts/init.sh              # lê o .env, cria ./data e ./secrets (dono uid 10001)
docker compose up -d --build      # primeira vez baixa a imagem base e os pacotes
docker compose ps                 # aguarde "healthy"
curl -s http://127.0.0.1:8080/health/ready
```

Para abrir o dashboard no navegador da sua máquina: `ssh -L 8080:127.0.0.1:8080 <usuario>@<vm>` e acesse `http://localhost:8080`. Outra opção é `BLC_BIND=0.0.0.0` no `.env`, se a VM estiver numa rede só sua.

Os segredos de desenvolvimento são descartáveis. **Nunca** copie segredos, banco ou configurações de produção para a VM.

## 3. Dia a dia

```bash
git switch main && git pull
git switch -c e2/acesso-e-cadastro   # uma branch por etapa ou tarefa: eN/<assunto>

scripts/fmt.sh                       # formata e corrige lint
scripts/check.sh                     # Ruff + mypy estrito + pytest, em container sem rede
scripts/check.sh -k frontend -q      # argumentos extras vão para o pytest

docker compose up -d --build         # ver a mudança rodando
docker compose logs -f app           # logs JSON
```

**Definição de pronto** (para toda tarefa):

1. Código alinhado à spec aprovada da etapa (`docs/specs/`).
2. `scripts/check.sh` passando, com testes de sucesso e de falha.
3. Nenhum segredo ou dado do cliente em código, testes, logs ou documentação (o repositório é **público**).
4. Documentação atualizada: spec (evidências), `CHANGELOG.md`, `docs/ESTADO.md` e ADR quando houver decisão nova.

**Commits:** padrão *Conventional Commits* em português (`feat(e2): ...`, `fix: ...`, `docs: ...`), citando requisitos (`Refs: F-10, CA-09`).

## 4. Ciclo SDD

Cada etapa segue `docs/PLANO.md`, seção 1:

1. **Especificar:** `docs/specs/EN-<nome>.md`, usando `E1-fundacao.md` como modelo (objetivo, escopo, fora de escopo, critérios Dado/Quando/Então, ações de rede, rastreabilidade).
2. **Aprovar:** o dono do produto aprova antes de qualquer código.
3. **Implementar:** testes primeiro, na branch da etapa.
4. **Verificar:** preencher a seção "Evidências" da spec.
5. **Entregar:** merge na `main`, tag, push (seção 10).

## 5. Estrutura e regras de dependência

```
src/backuplc/
  core/        config, logging, db, events, migrate, health — não importa nada do domínio
  web/         app, middleware, routes, templating, templates/, static/css/ — não importa sqlalchemy
  migrations/  env.py + versions/vNNNN_<assunto>.py
  cli.py       serve | migrate | check-config | init-secrets
  (próximas)   auth/, devices/, collector/, storage/, scheduler/, dashboard/
tests/         conftest.py (fixtures e canários), archrules.py (regras), test_*.py
```

As regras ficam em `tests/archrules.py` e são verificadas pelo `check.sh`:

| Módulo | Não pode importar |
| --- | --- |
| `core` | qualquer módulo de domínio, `web` ou `cli` |
| `web` | `sqlalchemy` (acesso ao banco só via serviços/`core`) |
| `collector` | `sqlalchemy`, `web`, `auth`, `storage`, `scheduler`, `dashboard` |

Ao criar um módulo novo, inclua as regras dele em `archrules.py`.

## 6. Frontend sem JavaScript (regra máxima — ADR-002)

- O navegador só recebe HTML e CSS gerados no servidor. **Nenhum** `<script>`, atributo `on*`, `javascript:` ou arquivo `.js`.
- Sem `style="..."` inline: a CSP (`style-src 'self'`) bloqueia. Use classes em `static/css/app.css`.
- Gráficos: SVG montado no servidor (template ou função Python). Atualização automática: `<meta http-equiv="refresh">`.
- Interação: formulários HTML com POST → redirecionamento → GET. Filtros, ordenação e paginação por parâmetros de URL tratados no backend.
- Cores de estado: tokens `--ok`, `--warn`, `--crit`, `--idle` (claro e escuro); sempre com texto junto, nunca só cor.
- `tests/test_frontend.py` falha se alguma regra for violada; novas páginas entram na lista `HTML_PAGES`.

## 7. Segredos e dados

- Segredos só em arquivos (`BLC_*_FILE`). Ao ler um segredo novo, chame `register_secret()` para que ele nunca apareça em log.
- Use `logging` com `extra={...}`; chaves como `password`, `token`, `secret` são mascaradas automaticamente. Nunca registre o conteúdo de configurações coletadas, só metadados.
- `record_event()` (tabela `events`) também passa os detalhes pelo filtro.
- `tests/test_canaries.py` injeta valores marcadores e procura vazamentos em logs, banco e arquivos. Fluxos novos que lidam com segredo devem ser incluídos nele.

## 8. Banco e migrações

- Modelos SQLAlchemy herdam de `backuplc.core.db.Base` (convenção de nomes já configurada).
- Nova migração: crie `src/backuplc/migrations/versions/vNNNN_<assunto>.py` seguindo `v0001_inicial.py` (`revision = "NNNN"`, `down_revision` = anterior), com `upgrade()` e `downgrade()`.
- Importe o módulo do modelo novo em `migrations/env.py`.
- `test_migracao_ida_e_volta` garante que a migração é reversível. Migrações são aplicadas automaticamente em `serve`.

## 9. Dependências

1. Adicione o pacote em `pyproject.toml` (`dependencies` ou grupo `dev`).
2. Atualize `exclude-newer` em `[tool.uv]` para cerca de 2 semanas antes da data atual (só versões já maduras).
3. `scripts/lock.sh` → `scripts/check.sh` → registre as versões no `CHANGELOG.md`.

Em produção, um build com dependências novas baixa pacotes: isso exige aprovação (G-2).

## 10. Gerar uma versão

1. Atualize a versão em `pyproject.toml` e em `src/backuplc/__init__.py`.
2. Atualize `CHANGELOG.md`, as evidências da spec e `docs/ESTADO.md`.
3. `scripts/check.sh` verde → merge na `main` → `git tag -a vX.Y.Z -m "..."` → `git push origin main vX.Y.Z`.
4. Implantação em produção: [`runbooks/instalacao.md`](runbooks/instalacao.md), seção 4.
