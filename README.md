# backup-lc

Backup automático e diário da configuração de switches, com histórico verificável e dashboard de saúde dos backups.

> Status: **v0.1.0 — E1 Fundação e base visual concluída** · próxima: E2 — Acesso e cadastro · detalhes em [docs/ESTADO.md](docs/ESTADO.md)

**Começando:** desenvolvimento → [docs/DESENVOLVIMENTO.md](docs/DESENVOLVIMENTO.md) · produção → [runbook](docs/runbooks/instalacao.md) · assistentes de IA → [CLAUDE.md](CLAUDE.md)

## Subir o sistema

```bash
cp .env.example .env     # opcional: ajuste caminhos, interface e porta
sudo scripts/init.sh     # diretório de dados e segredos (idempotente; lê o .env)
docker compose up -d     # build + execução; migrações aplicadas na subida
```

O dashboard responde em `http://<servidor>:8080` (ADR-012). Ainda **sem TLS e sem login** (login chega na E2).
Para restringir ao host local, defina `BLC_BIND=127.0.0.1` no `.env`.
Detalhes em [runbook de instalação](docs/runbooks/instalacao.md).

## Desenvolvimento

| Comando | O que faz | Usa a rede? |
| --- | --- | --- |
| `scripts/check.sh` | Ruff, mypy (estrito) e pytest em container `--network none` | Não* |
| `scripts/fmt.sh` | Formata e corrige o código | Não* |
| `scripts/lock.sh` | Regenera `uv.lock` | **Sim** (G-2) |

\* O primeiro build da imagem de desenvolvimento baixa os pacotes travados (G-2); depois usa cache.

Estrutura: `src/backuplc/{core,web,migrations}` · testes em `tests/` · decisões em `docs/adr/`.

## Documentação

- [Estado do projeto](docs/ESTADO.md) — onde estamos, pendências e próximos passos
- [PRD v2.0](docs/prd/PRD-v2.0.md) — o que o sistema faz e não faz
- [Plano SDD](docs/PLANO.md) — ciclo de trabalho, ambientes, etapas e portões de aprovação
- [Guia de desenvolvimento](docs/DESENVOLVIMENTO.md) — VM local, convenções, como adicionar telas, migrações e dependências
- [Decisões de arquitetura](docs/adr/README.md) — ADR-001 a ADR-013
- [Spec E1 — Fundação](docs/specs/E1-fundacao.md)
- [Runbook de instalação e implantação](docs/runbooks/instalacao.md)
- [Changelog](CHANGELOG.md)

## Regras invioláveis

1. **Produção é protegida**: desenvolvimento só na VM; produção recebe apenas versões marcadas (ADR-013).
2. No ambiente do cliente, qualquer ação com impacto mínimo na rede é informada antes e só ocorre após aprovação. Conexão a switch real sempre exige aprovação.
3. **Zero processamento no frontend**: o navegador só exibe HTML/CSS gerado pelo servidor, sem JavaScript.
4. Somente leitura nos switches; segredos nunca em texto puro; **repositório público**: nenhum dado do cliente no git.
5. SDD: nada é implementado sem especificação aprovada.
