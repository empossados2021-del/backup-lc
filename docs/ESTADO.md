# Estado do projeto

**Atualizado em 2026-11-04** · Versão atual: **v0.1.0** · Próxima etapa: **E2 — Acesso e cadastro**

## 1. Resumo

As etapas E0 (especificação) e E1 (fundação e base visual) estão concluídas. O sistema sobe, valida configuração, aplica migrações, responde a health checks e exibe a casca do dashboard. Ainda não há login, cadastro de switches nem coleta.

A partir de 2026-11-05 o desenvolvimento passa para uma VM local (ADR-013). O servidor de produção só recebe versões marcadas.

## 2. Etapas

| Etapa | Situação | Referência |
| --- | --- | --- |
| E0 — Especificação base | Concluída | PRD v2.0, `PLANO.md`, ADR-001 a 013 |
| E1 — Fundação e base visual | Concluída (v0.1.0) | [`specs/E1-fundacao.md`](specs/E1-fundacao.md), evidências na seção 7 |
| E2 — Acesso e cadastro | **Próxima**: escrever a spec | Escopo no `PLANO.md` |
| E3 a E7 | Não iniciadas | `PLANO.md` |

## 3. O que existe no código (v0.1.0)

- Comandos `serve`, `migrate`, `check-config`, `init-secrets`.
- Configuração `BLC_*` com segredos em arquivo, validada na subida.
- Logs JSON com máscara de segredos; tabela `events` com detalhe mascarado.
- SQLite (WAL) + Alembic; migração `0001` (tabela `events`).
- `/health/live`, `/health/ready`; página inicial com estados de saúde (zerados) e estado da plataforma.
- CSS próprio, tema claro e escuro, nenhum JavaScript (CSP `script-src 'none'`).
- Container não root, raiz somente leitura, 512 MB; 31 testes.

## 4. Produção (situação em 2026-11-04)

| Item | Situação |
| --- | --- |
| Checkout | `/opt/backup-lc`, branch `main` em `v0.1.0` |
| Serviço | Container `backup-lc-app-1` rodando, `healthy`, publicado em `0.0.0.0:8080` (ADR-012) |
| Dados | `/var/lib/backup-lc` (uid 10001, `0700`): só o banco, sem dados de switches |
| Segredos | `/etc/backup-lc/secrets/{session_secret,master_key}` (uid 10001, `0400`) |
| Imagens Docker | `backuplc:latest`, `backuplc:dev`, `python:3.13-slim` |
| Firewall do host | Nenhum (INPUT ACCEPT, sem ufw) |

**Usos de rede já feitos em produção (para registro):** download da imagem `python:3.13-slim`; `pip` do `pypdf` dentro de um container descartável, para ler o PRD v1.1 (antes da regra R-02); `uv` e 43 pacotes do PyPI (G-2 aprovado); consultas e pushes ao GitHub (G-1 aprovado); publicação da porta 8080 (G-3 aprovado). Nenhuma conexão a switches.

## 5. Pendências do cliente

| ID | Pendência | Bloqueia |
| --- | --- | --- |
| P-01 | Fabricantes, modelos, versões de SO e quantidade de switches | E3 (drivers) |
| P-02 | Conta de serviço nos switches com privilégio mínimo | E6 |
| P-03 | Redes de origem permitidas e certificado TLS do dashboard (a porta já foi definida) | E6 |
| P-04 | Horário da coleta diária e janela permitida | E6 |
| P-06 | Retenção (proposta: 365 dias) | E7 |

## 6. Riscos e dívidas abertas

| Item | Ação recomendada | Quando |
| --- | --- | --- |
| Produção exposta em HTTP, sem login | Implantar a E2 (login obrigatório). Até lá, considerar `BLC_BIND=127.0.0.1` | E2 |
| Sem TLS | Proxy reverso ou certificado na aplicação (nova ADR) | Antes da E6 |
| Host sem firewall; Docker ignora ufw | Regras na cadeia `DOCKER-USER` ou firewall de rede (G-3) | Antes da E6 |
| Cópia da `master_key` | Guardar fora do servidor, separada dos dados | Agora |
| Servidor de produção com chave SSH de **push** no GitHub (root) | Trocar por *deploy key* somente leitura | Antes da próxima implantação |
| Aviso de depreciação `httpx` no `TestClient` (Starlette 1.9) | Avaliar `httpx2` ao atualizar dependências | Próxima atualização |

## 7. Próximos passos

1. Montar a VM de desenvolvimento ([`DESENVOLVIMENTO.md`](DESENVOLVIMENTO.md)) e rodar `scripts/check.sh`.
2. Escrever a spec da **E2**, para aprovação:
   - login com usuários locais, senha com Argon2 e política mínima;
   - sessão no servidor com expiração por inatividade e logout que a invalida;
   - bloqueio após falhas consecutivas;
   - perfis Admin e Leitura com autorização no backend (CA-09) e proteção CSRF nos formulários;
   - credenciais cifradas com Fernet (chave mestra) e cadastro de switches (F-01, F-02);
   - registro de eventos (F-11); primeiro administrador criado pelo CLI.
3. Implementar e verificar a E2 na VM; gerar `v0.2.0`.
4. Implantar a `v0.2.0` em produção pelo runbook, com aprovação.
