# ADR-008 — Docker Compose, container não root

**Status:** Aceita · 2026-11-04

**Contexto:** O servidor já tem Docker 29 e Compose v5. A instalação precisa ser reprodutível.

**Decisão:** Imagem própria a partir de `python:3.13-slim`, multiestágio. Usuário uid 10001, raiz somente leitura, `/data` como único volume gravável, `no-new-privileges`, todas as capabilities removidas, limite de 512 MB de memória. Um serviço no `compose.yaml`.

**Alternativas:** Serviço systemd nativo (depende mais da configuração do host).

**Consequências:** Atualização = build + `docker compose up -d`. Builds que baixam pacotes passam pelo portão G-2.
