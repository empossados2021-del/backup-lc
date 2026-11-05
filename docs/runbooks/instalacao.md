# Runbook — Instalação, atualização e verificação

Público: quem administra o servidor de **produção**. Todos os comandos rodam no servidor, como root, em `/opt/backup-lc`.

> Passos marcados com **[REDE]** acessam a internet ou o GitHub (portões G-1/G-2) e exigem aprovação antes.
> Em produção não se desenvolve nem se depura: só se implantam versões marcadas (`vX.Y.Z`) — ADR-013.
> Para o ambiente de desenvolvimento, veja [`../DESENVOLVIMENTO.md`](../DESENVOLVIMENTO.md).

## 1. Pré-requisitos

- Docker com Compose v2 ou superior; `git`; `python3` (usado por `scripts/init.sh`).
- Imagem base `python:3.13-slim` disponível localmente (ou aprovação para baixá-la).
- Acesso de leitura ao repositório (de preferência uma *deploy key* somente leitura).

## 2. Primeira instalação

```bash
git clone git@github.com:empossados2021-del/backup-lc.git /opt/backup-lc   # [REDE]
cd /opt/backup-lc
git checkout vX.Y.Z            # sempre uma versão marcada, nunca um branch em desenvolvimento
scripts/init.sh                # cria /var/lib/backup-lc e os segredos em /etc/backup-lc/secrets
docker compose build           # [REDE] na primeira vez: baixa os pacotes travados no uv.lock
docker compose up -d
docker compose ps              # aguarde STATUS "healthy"
curl -s http://127.0.0.1:8080/health/ready
```

`scripts/init.sh` é idempotente e **nunca** sobrescreve segredos existentes.

**Guarde uma cópia de `/etc/backup-lc/secrets/master_key` fora do servidor.** Sem ela, as credenciais cadastradas não podem ser decifradas (ADR-006).

## 3. Acessar o dashboard

O serviço é publicado em `0.0.0.0:8080` (ADR-012): abra `http://<servidor>:8080`.

Atenção: ainda **sem TLS e sem login** (o login chega na E2). O Docker cria regras próprias de iptables, então firewalls como o ufw não bloqueiam essa porta.

Para restringir ao próprio servidor, crie `.env` com `BLC_BIND=127.0.0.1` e rode `docker compose up -d`. O acesso passa a ser por túnel:

```bash
ssh -L 8080:127.0.0.1:8080 <usuario>@<servidor>
```

## 4. Atualizar para uma nova versão

Antes: confirme que a versão foi verificada na VM de desenvolvimento (evidências na spec) e faça a cópia da seção 7.

```bash
cd /opt/backup-lc
git status --short             # deve estar vazio: produção não tem alterações locais
git fetch --tags               # [REDE] portão G-1
git checkout vX.Y.Z
docker compose up -d --build   # [REDE] baixa pacotes só se pyproject.toml/uv.lock mudarem (G-2)
docker compose ps              # aguarde "healthy"; migrações são aplicadas na subida
curl -s http://127.0.0.1:8080/health/ready
```

Voltar para a versão anterior: `git checkout <tag anterior>` e `docker compose up -d --build`. Se a nova versão aplicou migrações, primeiro reverta-as (abaixo) ou restaure a cópia do diretório de dados.

Reverter a última migração (somente com backup do diretório de dados):

```bash
docker compose run --rm app migrate --down -1
```

## 5. Verificação de qualidade

Feita na VM de desenvolvimento ([`../DESENVOLVIMENTO.md`](../DESENVOLVIMENTO.md)), não em produção.

## 6. Diagnóstico rápido

| Sintoma | Verificar |
| --- | --- |
| Container reiniciando | `docker compose logs app` — erro `configuração inválida` cita a variável com problema |
| `/health/ready` 503 | O JSON indica qual verificação falhou: `database`, `schema` ou `storage` |
| `storage` falso | Dono de `/var/lib/backup-lc` deve ser `10001:10001`, permissão `0700` |
| Segredo ilegível | Arquivos em `/etc/backup-lc/secrets` devem ser `10001:10001`, permissão `0400` |

## 7. O que copiar para backup do próprio sistema

| Item | Caminho | Observação |
| --- | --- | --- |
| Dados (banco + configurações coletadas) | `/var/lib/backup-lc` | Pare o serviço ou copie com `sqlite3 .backup` |
| Chave mestra | `/etc/backup-lc/secrets/master_key` | Guardar **separada** dos dados |
