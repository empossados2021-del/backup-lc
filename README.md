# backup-lc

Backup automático e diário da configuração de switches, com histórico verificável e dashboard de saúde dos backups.

> Status: **E0 — Especificação base** (nenhum código ainda).

## Documentação

- [PRD v2.0](docs/prd/PRD-v2.0.md) — o que o sistema faz e não faz
- [Plano SDD](docs/PLANO.md) — ciclo de trabalho, etapas e portões de aprovação

## Regras invioláveis

1. O servidor de implantação é **produção**: nada é executado fora dele.
2. Qualquer ação com impacto mínimo na rede é informada antes e só ocorre após aprovação.
3. **Zero processamento no frontend**: o navegador só exibe HTML/CSS gerado pelo servidor, sem JavaScript.
4. Somente leitura nos switches; segredos nunca em texto puro.
5. SDD: nada é implementado sem especificação aprovada.
