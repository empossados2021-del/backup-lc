# ADR-013 — Desenvolvimento em VM local; produção só recebe versões prontas

**Status:** Aceita · 2026-11-04 · Ajusta a regra R-01 e o alcance das ADR-010 e ADR-012

**Contexto:** As etapas E0 e E1 foram desenvolvidas diretamente no servidor de produção do cliente, com portões de aprovação para tudo que tocasse a rede. O dono do produto decidiu que errar em produção é um risco desnecessário: o desenvolvimento passa para uma VM local dele, a partir de 2026-11-05.

**Decisão:**

1. **Desenvolvimento** (código, testes, builds, downloads de pacotes) acontece só na VM de desenvolvimento.
2. **Produção** só recebe versões marcadas (`git tag vX.Y.Z`), por `git clone` ou `git pull` da tag, seguidos de `docker compose up -d --build`, conforme o runbook. Nada é desenvolvido, testado ou depurado em produção.
3. A verificação local da ADR-010 (`scripts/check.sh`, container sem rede) roda na VM; continua sem CI externo.
4. Os portões de aprovação valem para produção: G-1 (git), G-2 (downloads), G-3 (portas) e G-5 (ampliação) quando executados no servidor do cliente; G-4 (conexão a switch real) sempre, em qualquer ambiente.
5. Na VM de desenvolvimento o dashboard pode ficar em `127.0.0.1` (`BLC_BIND=127.0.0.1` no `.env`); em produção vale a ADR-012.

**Alternativas:** Continuar desenvolvendo em produção (descartada: risco ao cliente).

**Consequências:**

- O repositório é a única ponte entre os ambientes; nada de cópia manual de arquivos para produção.
- Dados de produção (banco, configurações coletadas, segredos) nunca vão para a VM nem para o git.
- O servidor de produção hoje tem uma chave SSH com permissão de push no GitHub. Ela deve ser trocada por uma *deploy key* somente leitura (ver `docs/ESTADO.md`).
