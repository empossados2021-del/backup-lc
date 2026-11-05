# ADR-011 — Dashboard só em 127.0.0.1 até a definição de acesso

**Status:** Substituída pela [ADR-012](ADR-012-publicacao-0-0-0-0.md) · 2026-11-04

**Contexto:** Ainda não está definido em que porta e para quais redes o dashboard será publicado, nem o certificado TLS (P-03). Abrir porta na rede tem impacto (R-02).

**Decisão:** O container publica apenas em `127.0.0.1:8080`. Acesso durante o desenvolvimento por túnel SSH (`ssh -L 8080:127.0.0.1:8080 <usuario>@<servidor>`).

**Consequências:** Nenhuma porta nova fica visível na rede. A exposição definitiva, com TLS, entra por nova ADR e aprovação G-3.
