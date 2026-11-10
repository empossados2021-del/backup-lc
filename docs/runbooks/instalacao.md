# Runbook — Instalação, atualização e recuperação

Público: quem administra o servidor de **produção**. Todos os comandos rodam no servidor, como root, em `/opt/backup-lc`.

> Passos marcados com **[REDE]** acessam a internet ou o GitHub (portões G-1/G-2) e exigem aprovação antes.
> Em produção não se desenvolve nem se depura: só se implantam versões marcadas (`vX.Y.Z`) — ADR-013.
> Para o ambiente de desenvolvimento, veja [`../DESENVOLVIMENTO.md`](../DESENVOLVIMENTO.md).

## 1. Pré-requisitos

- Docker com Compose v2 ou superior; `git`.
- Imagem base `python:3.13-slim` disponível localmente (ou aprovação para baixá-la).
- Acesso de leitura ao repositório (de preferência uma *deploy key* somente leitura).

## 2. Primeira instalação

```bash
# [REDE] portão G-1
git clone git@github.com:empossados2021-del/backup-lc.git /opt/backup-lc
cd /opt/backup-lc
git checkout vX.Y.Z            # sempre uma versão marcada, nunca um branch em desenvolvimento

# Cria diretórios, usuário e segredos
scripts/init.sh                # cria /var/lib/backup-lc (uid 10001) e /etc/backup-lc/secrets
```

`scripts/init.sh` é idempotente e **nunca** sobrescreve segredos existentes.

**Guarde uma cópia de `/etc/backup-lc/secrets/master_key` fora do servidor, em mídia separada.** Sem ela as credenciais cadastradas não podem ser decifradas (ADR-006).

```bash
# [REDE] portão G-2 — baixa pacotes somente na primeira vez
docker compose build

docker compose up -d
docker compose ps              # aguarde STATUS "healthy"
curl -s http://127.0.0.1:8080/health/ready   # deve retornar {"status":"ok"}
```

Após subir, crie o primeiro usuário administrador:

```bash
docker compose exec app python -m backuplc create-admin
```

## 3. Variáveis de ambiente (`.env`)

Crie `.env` na raiz do repositório a partir deste modelo:

```env
BLC_SESSION_SECRET_FILE=/etc/backup-lc/secrets/session_secret
BLC_MASTER_KEY_FILE=/etc/backup-lc/secrets/master_key
BLC_DATA_DIR=/var/lib/backup-lc
BLC_ENVIRONMENT=production
BLC_TIMEZONE=America/Sao_Paulo

# Agendamento da coleta diária (cron no fuso BLC_TIMEZONE)
# Exemplo: todos os dias às 02:00
BLC_SCHEDULE_CRON=0 2 * * *

# Retenção de backups em dias (0 = sem limite)
BLC_RETENTION_DAYS=365

# Porta interna do container (publicação definida no compose.yaml)
BLC_PORT=8080
```

## 4. Acessar o dashboard

O serviço é publicado em `0.0.0.0:8080` (ADR-012): abra `http://<servidor>:8080`.

> O Docker cria regras próprias de iptables. Firewalls como ufw **não** bloqueiam esta porta automaticamente. Configure `DOCKER-USER` ou o firewall de rede para restringir o acesso antes de usar em produção.

Para restringir ao próprio servidor, adicione `BLC_BIND=127.0.0.1` ao `.env` e acesse via túnel SSH:

```bash
ssh -L 8080:127.0.0.1:8080 <usuario>@<servidor>
```

## 5. Atualizar para uma nova versão

Antes: confirme que a versão foi verificada na VM de desenvolvimento (evidências na spec) e execute o procedimento de cópia de dados (`docs/runbooks/backup-dados.md`).

```bash
cd /opt/backup-lc
git status --short             # deve estar vazio: produção não tem alterações locais
git fetch --tags               # [REDE] portão G-1
git checkout vX.Y.Z
docker compose up -d --build   # [REDE] portão G-2 — baixa pacotes somente se uv.lock mudou
docker compose ps              # aguarde "healthy"; migrações são aplicadas na subida
curl -s http://127.0.0.1:8080/health/ready
```

Para reverter à versão anterior: `git checkout <tag anterior>` + `docker compose up -d --build`. Se a nova versão aplicou migrações de banco, reverta-as antes (abaixo) ou restaure a cópia dos dados.

**Reverter a última migração de banco** (somente com cópia dos dados disponível):

```bash
docker compose run --rm app migrate --down -1
```

## 6. Diagnóstico rápido

| Sintoma | O que verificar |
| --- | --- |
| Container reiniciando | `docker compose logs app` — `configuração inválida` cita a variável com problema |
| `/health/ready` retorna 503 | JSON indica qual verificação falhou: `database`, `schema` ou `storage` |
| `storage` falso | Dono de `/var/lib/backup-lc` deve ser `10001:10001`, permissão `0700` |
| Segredo ilegível | Arquivos em `/etc/backup-lc/secrets` devem ser `10001:10001`, permissão `0400` |
| Login não funciona | Verifique `BLC_SESSION_SECRET_FILE` e se o container está `healthy` |
| Backups não são coletados | Verifique `BLC_SCHEDULE_CRON` e fuso `BLC_TIMEZONE` em Configurações |
| Retenção não remove nada | Verifique `BLC_RETENTION_DAYS` (0 = desabilitada); job roda diariamente às 03:00 no fuso configurado |

## 7. Recuperação de desastre

1. Parar o container: `docker compose down`
2. Restaurar `/var/lib/backup-lc` a partir da cópia (ver `docs/runbooks/backup-dados.md`)
3. Restaurar `/etc/backup-lc/secrets/master_key` (cópia offline)
4. Subir com a mesma tag que estava rodando: `docker compose up -d`
5. Verificar: `curl -s http://127.0.0.1:8080/health/ready`

## 8. Checklist de segurança pós-instalação

| Item | Comando de verificação |
| --- | --- |
| Container sem root | `docker compose exec app id` → deve retornar `uid=10001` |
| Sistema de arquivos do container read-only | `docker inspect backup-lc-app-1 --format '{{.HostConfig.ReadonlyRootfs}}'` → `true` |
| Arquivos de backup com permissão `0600` | `find /var/lib/backup-lc/configs -type f -exec stat -c '%a %n' {} \;` |
| Nenhum segredo em texto puro no banco | `sqlite3 /var/lib/backup-lc/backup-lc.db "SELECT encrypted_password FROM credentials LIMIT 1"` → ciphertext |
| Headers HTTP de segurança | `curl -I http://localhost:8080/` → `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` |
| Sem JavaScript nas páginas | `curl -s http://localhost:8080/ \| grep -c '<script'` → `0` |
