# ADR-010 — Verificação no servidor, sem CI externo

**Status:** Aceita · 2026-11-04

**Contexto:** Regra R-01: nada é executado fora do servidor de produção. Um CI no GitHub Actions rodaria fora dele.

**Decisão:** `scripts/check.sh` executa Ruff, mypy e pytest num container com `--network none`, no próprio servidor, antes de cada commit na `main`. O resultado é registrado na seção de evidências da spec.

**Alternativas:** GitHub Actions (fora do servidor).

**Consequências:** A disciplina de rodar o `check.sh` é do desenvolvedor; a definição de pronto exige a evidência.
