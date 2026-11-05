# CLAUDE.md — instruções para assistentes de IA neste repositório

backup-lc: backup diário da configuração de switches, com histórico verificável e dashboard de saúde. Python 3.13, FastAPI, Jinja2, SQLite, Docker Compose. Metodologia SDD.

Antes de qualquer tarefa, leia `docs/ESTADO.md` (onde o projeto está) e `docs/PLANO.md` (como trabalhamos).

## Regras invioláveis

1. **Zero processamento no frontend.** Nenhum JavaScript: sem `<script>`, `on*`, `javascript:`, `.js`, HTMX ou CDN. Sem `style=""` inline. Tudo (validação, filtros, diff, gráficos SVG) é feito no servidor. Ver ADR-002.
2. **SDD.** Não implemente nada sem spec aprovada em `docs/specs/`. Escreva a spec, peça aprovação e só depois codifique.
3. **Repositório público.** Nunca coloque no git IPs, hostnames, usuários, senhas, nomes de switch, configurações coletadas ou documentos do cliente. Use `<servidor>`, `<usuario>` e exemplos fictícios.
4. **Produção é intocável.** Não desenvolva, teste ou depure no servidor do cliente. Em produção, só implantação de tag pelo runbook, com aprovação explícita de cada passo que use rede (portões G-1, G-2, G-3 e G-5 em `docs/PLANO.md`).
5. **Switch real só com aprovação.** Nunca conecte a um equipamento real sem aprovação explícita (G-4), em qualquer ambiente. Testes usam o simulador local.
6. **Segredos.** Só em arquivos `BLC_*_FILE`, registrados com `register_secret()`. Nunca em log, banco em texto puro, tela, teste ou documento.

## Comandos

```bash
scripts/fmt.sh          # formata
scripts/check.sh        # Ruff + mypy estrito + pytest (container sem rede) — deve passar antes de todo commit
scripts/lock.sh         # regenera uv.lock (acessa PyPI)
docker compose up -d --build
```

## Convenções

- Código e identificadores em inglês; interface, documentação, mensagens e commits em português.
- Tipagem obrigatória (mypy `strict`). Ruff com regras `E,F,W,I,B,UP,S,SIM,RUF,N`.
- Regras de importação entre módulos em `tests/archrules.py` (`core` não importa domínio; `web` não importa `sqlalchemy`).
- Branch por etapa (`eN/<assunto>`), *Conventional Commits*, merge `--no-ff` na `main`, tag `vX.Y.Z`.
- Ao concluir uma tarefa, atualize a documentação: spec (evidências), `CHANGELOG.md`, `docs/ESTADO.md` e ADR se houver decisão nova. Depois faça o push.

## Onde está cada coisa

| Assunto | Arquivo |
| --- | --- |
| Requisitos | `docs/prd/PRD-v2.0.md` |
| Plano, ciclo SDD e portões | `docs/PLANO.md` |
| Estado atual e próximos passos | `docs/ESTADO.md` |
| Ambiente de desenvolvimento | `docs/DESENVOLVIMENTO.md` |
| Decisões | `docs/adr/` |
| Specs por etapa | `docs/specs/` |
| Instalação e implantação | `docs/runbooks/instalacao.md` |
