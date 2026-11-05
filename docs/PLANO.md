# Plano do projeto — backup-lc (SDD)

Base: `docs/prd/PRD-v2.0.md` · Atualizado em 2026-11-04 · Estado atual: [`ESTADO.md`](ESTADO.md)

## 1. Como trabalhamos (ciclo SDD)

Cada etapa passa pelo mesmo ciclo. Nenhuma fase começa antes da anterior estar concluída.

| Fase | O que acontece | Saída | Quem decide |
| --- | --- | --- | --- |
| A. Especificar | Escrever `docs/specs/EN-<nome>.md`: objetivo, escopo, fora de escopo, critérios de aceite (Dado/Quando/Então), testes previstos e ações com impacto em rede | Spec em rascunho | Desenvolvedor |
| B. Aprovar | Revisar a spec; ajustar ou aprovar | Spec marcada "Aprovada" | Dono do produto |
| C. Implementar | Testes primeiro, depois código, numa branch `eN/<nome>` | Código + testes | Desenvolvedor |
| D. Verificar | Rodar testes, lint e tipos; demonstrar cada critério de aceite | Evidência na spec | Dono do produto |
| E. Entregar | Atualizar docs (README, spec, CHANGELOG, `ESTADO.md`), commit, merge na `main`, tag `vX.Y.Z`, push | Versão marcada | Ambos |
| F. Implantar | Em produção: pull da tag e `docker compose up -d --build`, com aprovação (portões G-1/G-2) | Versão em produção | Dono do produto |

**Definição de pronto:** critérios de aceite demonstrados, testes passando, nenhum segredo em código ou logs, documentação atualizada.

## 2. Ambientes (ADR-013)

| Ambiente | Para quê | Regras |
| --- | --- | --- |
| VM de desenvolvimento (local) | Código, testes, builds, downloads de pacotes, protótipos | Livre, exceto conexão a switch real (G-4). Guia: [`DESENVOLVIMENTO.md`](DESENVOLVIMENTO.md) |
| Servidor de produção (cliente) | Executar versões marcadas (`vX.Y.Z`) | Só `git clone`/`pull` de tag + `docker compose up -d --build`, com os portões abaixo. Runbook: [`runbooks/instalacao.md`](runbooks/instalacao.md) |

Fluxo de uma entrega: VM (branch → `check.sh` → merge → tag → push) → produção (pull da tag → build → subir → conferir `/health/ready`).

## 3. Portões de aprovação (impacto em rede — regra R-02)

No servidor de produção, nenhum destes itens é executado sem aviso prévio e aprovação explícita, a cada vez. O G-4 vale em qualquer ambiente.

| Portão | Ação | Quando aparece | O que será informado antes |
| --- | --- | --- | --- |
| G-1 | `git push` / `git fetch` para o GitHub | Fim de cada etapa | Branch, commits e arquivos enviados |
| G-2 | Baixar imagem base e pacotes Python | E1 e quando dependências mudarem | Imagem, versões e lista de pacotes |
| G-3 | Publicar a porta do dashboard no servidor | E1 | Porta, interface e regra de acesso |
| G-4 | Primeira conexão SSH a um switch real | E6 | Switch, IP, comando exato, horário, conta |
| G-5 | Ampliar coleta para mais switches, mudar horário ou concorrência | E6 em diante | Lista de switches, horário, concorrência |

Testes de desenvolvimento usam um servidor SSH simulado, em rede Docker interna sem saída, portanto sem impacto em nenhuma rede.

## 4. Etapas

| Etapa | Entrega | Critérios principais | Portões | Depende de |
| --- | --- | --- | --- | --- |
| **E0 — Especificação base** ✔ | PRD v2.0, este plano, ADR-001 a 011 em `docs/adr/`, spec da E1 | PRD e ADRs aprovados | G-1 | — |
| **E1 — Fundação e base visual** ✔ v0.1.0 | Estrutura do projeto, configuração por arquivo, logs JSON com máscara, SQLite + migrações, `/health`, layout e CSS (tema claro/escuro), Dockerfile, Compose, scripts de verificação, testes base — spec: [`specs/E1-fundacao.md`](specs/E1-fundacao.md) | E1-01 a E1-09 | G-1, G-2 | E0, P-07 |
| **E2 — Acesso e cadastro** | Login, perfis Admin/Leitura, credenciais cifradas, cadastro de switches, registro de eventos | CA-09, F-01, F-02, F-10, F-11 | G-1 | E1 |
| **E3 — Coleta** | Coletor Netmiko por tipo, lista de comandos permitidos, validação, armazenamento com SHA-256, versões, verificação de chave SSH; tudo testado contra o simulador local | CA-02, CA-04, CA-05, CA-06, CA-08 | G-1 | E2, P-01 |
| **E4 — Agendamento e histórico** | Coleta diária, backup manual, retentativas, recuperação após reinício, histórico, diff e download | CA-01, CA-03, CA-07 (no simulador) | G-1 | E3 |
| **E5 — Dashboard de saúde** | Protótipo estático aprovado primeiro; depois dashboard real com SVG no servidor, tema claro/escuro, sem JS | Seção 5 do PRD; CA-10 | G-1 | E4 |
| **E6 — Piloto em produção** | Um switch real, depois ampliação em lotes aprovados | CA-01 a CA-06 em switch real | G-1, G-4, G-5 | E5, P-02, P-04 |
| **E7 — Operação** | Retenção, runbook de instalação/atualização/recuperação, cópia do diretório de dados, revisão de segurança | Terceiro instala seguindo o runbook | G-1 | E6, P-06 |

O dashboard (E5) só pode ser desenvolvido com dados reais de execuções. Até lá, um gerador local de dados de exemplo alimenta o protótipo.

## 5. Estrutura prevista do repositório

```
backup-lc/
  README.md  CHANGELOG.md  pyproject.toml  uv.lock
  Dockerfile  compose.yaml  .env.example  scripts/
  docs/
    PLANO.md
    prd/PRD-v2.0.md
    adr/            # uma decisão por arquivo
    specs/          # uma spec por etapa (E0..E7)
    runbooks/
  src/backuplc/
    core/           # config, logs, segurança, banco
    auth/           # usuários, sessão, perfis
    devices/        # switches e credenciais
    collector/      # Netmiko, tipos suportados, validação
    storage/        # arquivos, SHA-256, versões, diff
    scheduler/      # agendamento, retentativas
    dashboard/      # cálculo de saúde e SVG
    web/            # rotas, templates, CSS
  tests/            # unit, integration (simulador SSH), security
```

## 6. Riscos

| Risco | Mitigação |
| --- | --- |
| Tipos de switch desconhecidos (P-01) | E1 a E2 não dependem disso; E3 começa pelos tipos informados |
| Coleta causar carga ou bloqueio no switch | Somente leitura, concorrência baixa, sem retentar autenticação, portões G-4 e G-5 |
| Repositório público expor dados do cliente | Nada de IPs, nomes de switch, configurações ou PRD do cliente no git; resolver P-05 |
| Servidor único de produção com 3,8 GiB de RAM | Um serviço só, SQLite, limite de memória no container |
| Erro de desenvolvimento afetar o cliente | Desenvolvimento só na VM; produção recebe apenas tags verificadas (ADR-013) |
| Escopo crescer | Tudo fora da seção 8 do PRD exige nova spec |
