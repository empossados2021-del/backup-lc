# Spec E6 — Piloto em produção

| Campo | Valor |
| --- | --- |
| Status | **Rascunho** — 2026-11-06 |
| Base | PRD v2.0 (CA-01 a CA-06, R-01, R-02, R-04, N-04), ADR-012, ADR-013 |
| Data | 2026-11-06 |
| Depende de | E5 concluída; P-01, P-02, P-03, P-04 resolvidas pelo cliente |

## 1. Objetivo

Levar o sistema ao ar em produção com um switch real, validando o ciclo completo de coleta automática e manual em ambiente operacional. Esta etapa é predominantemente operacional: implanta as versões v0.2.0 a v0.6.0 acumuladas, configura TLS, firewall e conta de serviço, conecta ao primeiro switch com aprovação explícita (G-4) e verifica todos os critérios de aceite do PRD com hardware real.

## 2. Pré-condições (devem estar resolvidas antes de iniciar)

| ID | Pendência | O que é necessário |
| --- | --- | --- |
| P-01 | Fabricantes, modelos e versões de SO dos switches | Necessário para adicionar drivers além de `generic` nesta etapa |
| P-02 | Conta de serviço nos switches | Usuário SSH com permissão mínima de leitura |
| P-03 | Redes de origem permitidas e certificado TLS | Para configurar proxy reverso ou TLS na aplicação |
| P-04 | Horário da coleta diária e janela permitida | Para configurar `BLC_SCHEDULE_CRON` |

## 3. Escopo

### 3.1. Drivers adicionais (aguarda P-01)

Para cada fabricante/SO identificado em P-01, adicionar um `DriverSpec` em `collector/driver.py`:

- Campos: `netmiko_type`, `commands` (lista de comandos permitidos, R-04), `volatile_patterns`, `end_marker`, `min_chars`
- Testes unitários: lista de comandos permitidos é a única enviada (CA verificável sem switch real)
- Nenhum comando de escrita ou reconfiguração admitido

Enquanto P-01 não for recebida, o piloto usa `device_type="generic"` para todos os switches (Netmiko `generic`).

### 3.2. TLS e acesso seguro (aguarda P-03)

Configurar proxy reverso Nginx no mesmo host ou `uvicorn` com certificado, antes de qualquer acesso externo:

- Opção A (preferida): Nginx como container adicional no `compose.yaml`; `app` não publica mais porta diretamente; Nginx termina TLS e faz proxy para `app:8000`
- Opção B: certificado na aplicação via `uvicorn --ssl-keyfile/--ssl-certfile`

A decisão entre A e B é registrada em nova ADR antes da implementação.

HTTPS obrigatório antes do G-3 de abertura de porta (ADR-012). A porta 8080 existente passa a redirecionar para HTTPS.

### 3.3. Regras de firewall (aguarda P-03)

Adicionar regras na cadeia `DOCKER-USER` para restringir acesso à porta do dashboard às redes de origem aprovadas em P-03. Procedimento registrado no runbook.

### 3.4. Sequência de implantação (portões)

Cada portão exige aprovação explícita antes de executar. Os passos abaixo são realizados no servidor de produção com o runbook `docs/runbooks/instalacao.md` como guia.

| Passo | Portão | Ação | O que informar antes |
| --- | --- | --- | --- |
| 1 | G-1 | `git fetch` + `git checkout v0.6.0` | Tag, commits e arquivos trazidos |
| 2 | G-2 | `docker compose build` (baixa imagem base e pacotes) | Imagem base, versões de pacotes novos em relação à v0.1.0 |
| 3 | — | `docker compose up -d`; verificar `/health/ready`; testar login | Sem impacto de rede neste passo |
| 4 | G-3 | Configurar firewall (`DOCKER-USER`) e TLS; abrir porta para redes aprovadas | Porta, interface, redes de origem, certificado |
| 5 | G-4 | Primeira conexão SSH a um switch real (1 switch piloto) | Nome do switch, IP, conta, comando exato, horário |
| 6 | G-5 | Ampliar coleta para os demais switches após validar o piloto | Lista de switches, horário, concorrência configurada |

### 3.5. Validação do piloto (switch único — passo 5)

Após G-4, executar manualmente uma coleta e verificar:

1. Execução registrada com `status="ok"` e versão salva no banco
2. Arquivo de backup no caminho correto com permissão `0o600`
3. SHA-256 no banco bate com `sha256sum` do arquivo
4. Nenhum segredo em logs (`docker compose logs`)
5. Chave do host registrada em `device_host_keys`
6. Dashboard exibe o switch como `healthy`

Somente após validação do piloto: G-5 para os demais switches.

### 3.6. Testes desta etapa

Testes de código (drivers novos) rodam na VM, **sem** acesso a switch real:

| Tipo | O que cobre |
| --- | --- |
| Unit | Cada novo driver: lista de comandos == permitidos (nenhum comando de escrita) |
| Unit | Cada novo driver: `end_marker` e `volatile_patterns` corretos |
| Integration | `collect_device` com stub do tipo novo → versão criada corretamente |

Validação em produção (passo 3.5) é manual e documentada nas evidências desta spec.

## 4. Fora do escopo

- Retenção automática de backups (E7)
- Runbook de recuperação de desastre (E7)
- Múltiplos servidores ou alta disponibilidade (fora do PRD)
- MFA, LDAP ou SSO (fora do PRD)

## 5. Critérios de aceite

| ID | Dado | Quando | Então |
| --- | --- | --- | --- |
| E6-01 | Switch piloto com credencial válida | Horário configurado chega | Execução `ok`; switch `healthy` no dashboard (CA-01) |
| E6-02 | Configuração sem mudança | Segunda coleta do dia | Nenhuma nova versão; execução `ok` com `version_id=None` (CA-02) |
| E6-03 | Configuração alterada entre duas coletas | Nova coleta roda | Nova versão; aparece em "Alterações detectadas" (CA-03) |
| E6-04 | Saída truncada (simulada em teste unitário, não em produção) | — | `SAIDA_INCOMPLETA` (CA-04) |
| E6-05 | Senha errada (simulada em teste unitário) | — | `AUTENTICACAO`, sem retentativa (CA-05) |
| E6-06 | Chave SSH alterada (simulada em teste unitário) | — | `CHAVE_HOST`, nada coletado (CA-06) |
| E6-07 | Reinício durante coleta (simulado) | Sistema volta | Nenhuma execução presa em `running` (CA-07) |
| E6-08 | Usuário de Leitura tenta disparar backup | POST `/collect` | HTTP 403 (CA-09) |
| E6-09 | Navegador sem JavaScript | Acessa dashboard e histórico | Todas as funções operam (CA-10) |
| E6-10 | `scripts/check.sh` na VM | Executa | Ruff, mypy estrito e pytest passam; sem acesso à rede |

## 6. Ações com impacto em rede (aprovação necessária)

| Portão | Ação | Quando |
| --- | --- | --- |
| G-1 | `git fetch` + `git checkout v0.6.0` no servidor de produção | Passo 1 |
| G-2 | `docker compose build` (imagem base + pacotes) | Passo 2 |
| G-3 | Configurar TLS e firewall; expor porta para redes aprovadas | Passo 4 |
| G-4 | Primeira conexão SSH ao switch piloto | Passo 5 |
| G-5 | Ampliar coleta para demais switches | Passo 6 |

## 7. Rastreabilidade

| Critério | Requisitos PRD |
| --- | --- |
| E6-01 a E6-07 | CA-01 a CA-07 |
| E6-08 | CA-09 |
| E6-09 | CA-10 |
| E6-10 | R-06 |

## 8. Evidências de verificação (fase D)

_A preencher após implantação e validação do piloto._
