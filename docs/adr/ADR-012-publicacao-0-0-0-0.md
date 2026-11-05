# ADR-012 — Dashboard publicado em 0.0.0.0:8080

**Status:** Aceita · 2026-11-04 · **Substitui** a ADR-011

**Contexto:** O dono do produto pediu acesso direto ao dashboard pela rede, sem túnel SSH. Pedido tratado como aprovação do portão G-3. Na data, o host não tinha firewall (INPUT com política ACCEPT, sem ufw) e a interface de gerenciamento estava numa rede ampla.

**Decisão:** O `compose.yaml` publica a porta em `${BLC_BIND:-0.0.0.0}:${BLC_PORT:-8080}`. O valor `BLC_BIND=127.0.0.1` volta ao comportamento da ADR-011 sem alterar o código.

**Riscos aceitos, temporariamente:**

| Risco | Mitigação |
| --- | --- |
| HTTP sem TLS: tráfego legível na rede | TLS (proxy reverso ou certificado na aplicação) entra por nova ADR antes de dados sensíveis circularem |
| Sem login até a E2: qualquer máquina com rota vê a página | Até a E2 a aplicação não exibe dados de switches nem permite ações; a E2 bloqueia todas as páginas sem login (F-10) |
| O Docker cria regras de iptables próprias e ignora firewalls como o ufw | Restringir as origens com regra na cadeia `DOCKER-USER` ou em firewall de rede, se exigido (nova aprovação G-3) |

**Consequências:** A partir da E2, login obrigatório. Antes do piloto (E6), ter TLS e definir as redes de origem permitidas (P-03).
