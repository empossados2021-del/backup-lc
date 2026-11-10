# Runbook — Cópia de dados (backup do servidor)

**Versão do runbook:** v0.7.0 — 2026-11-10

---

## 1. O que precisa ser copiado

| Caminho | Conteúdo | Importância |
| --- | --- | --- |
| `/var/lib/backup-lc/backup-lc.db` | Banco SQLite: dispositivos, credenciais cifradas, histórico, execuções, configurações | Crítico |
| `/var/lib/backup-lc/configs/` | Arquivos de configuração coletados dos switches | Crítico |
| `/etc/backup-lc/secrets/session_secret` | Chave de sessão HTTP | Crítico |
| `/etc/backup-lc/secrets/master_key` | Chave Fernet de cifragem das credenciais | Crítico — ver aviso abaixo |

> **Aviso:** `master_key` **não deve ser copiada junto com o banco.** Se um atacante obtiver os dois, terá acesso às credenciais em texto puro. Guarde a `master_key` em mídia offline separada (pen drive criptografado, cofre de senhas corporativo), com controle de acesso distinto dos dados.

---

## 2. Ferramenta recomendada: `sqlite3 .backup` + `rsync`

### 2.1. Cópia atômica do banco

```bash
# Dentro do container (ou via docker compose exec):
docker compose -f /opt/backup-lc/compose.yaml exec app \
  sqlite3 /var/lib/backup-lc/backup-lc.db \
  ".backup /var/lib/backup-lc/backup-lc.db.bak"

# No host, copiar o arquivo gerado:
rsync --checksum --archive \
  /var/lib/backup-lc/backup-lc.db.bak \
  <destino>:/backup/backup-lc/backup-lc.db
```

O comando `.backup` do SQLite usa a API de backup online — funciona mesmo com o banco aberto em modo WAL, sem corromper o arquivo.

### 2.2. Cópia do diretório de configurações

```bash
rsync --checksum --archive --delete \
  /var/lib/backup-lc/configs/ \
  <destino>:/backup/backup-lc/configs/
```

### 2.3. Verificação de integridade

```bash
# Comparar sha256 do banco de origem e do destino:
sha256sum /var/lib/backup-lc/backup-lc.db
ssh <destino> sha256sum /backup/backup-lc/backup-lc.db

# Verificar integridade do banco copiado:
sqlite3 /backup/backup-lc/backup-lc.db "PRAGMA integrity_check;"
# Resultado esperado: ok
```

---

## 3. Alternativas para ambientes com LVM ou ZFS

### 3.1. Snapshot LVM

```bash
# Criar snapshot do volume que contém /var/lib/backup-lc:
lvcreate --snapshot --name backup-lc-snap --size 1G /dev/<vg>/<lv>
mount /dev/<vg>/backup-lc-snap /mnt/snap
rsync --archive /mnt/snap/ <destino>:/backup/backup-lc/
umount /mnt/snap
lvremove -f /dev/<vg>/backup-lc-snap
```

### 3.2. Snapshot ZFS

```bash
zfs snapshot <pool>/backup-lc@$(date +%Y%m%d)
zfs send <pool>/backup-lc@$(date +%Y%m%d) | \
  ssh <destino> zfs receive <pool-remoto>/backup-lc
```

Snapshots ZFS são atômicos e consistentes — não é necessário o `.backup` do SQLite neste caso.

---

## 4. Frequência recomendada

| Tipo de cópia | Frequência | Horário sugerido |
| --- | --- | --- |
| Banco + configs | Diária | 04:00 (após a janela de coleta das 03:00) |
| Retenção completa (semana anterior) | Semanal | Domingo 05:00 |
| Verificação de integridade | Semanal | Junto com a cópia semanal |

Exemplo de entrada em `/etc/cron.d/backup-lc-dados`:

```cron
0 4 * * * root /opt/backup-lc/scripts/backup-dados.sh >> /var/log/backup-lc-dados.log 2>&1
```

---

## 5. Script de referência (`scripts/backup-dados.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

DESTINO="${BACKUP_DESTINO:-<destino>:/backup/backup-lc}"
DATA=$(date +%Y%m%d-%H%M%S)

# 1. Cópia atômica do banco
docker compose -f /opt/backup-lc/compose.yaml exec -T app \
  sqlite3 /var/lib/backup-lc/backup-lc.db \
  ".backup /var/lib/backup-lc/backup-lc.db.bak"

# 2. Rsync banco + configs
rsync --checksum --archive \
  /var/lib/backup-lc/backup-lc.db.bak \
  "${DESTINO}/backup-lc-${DATA}.db"

rsync --checksum --archive --delete \
  /var/lib/backup-lc/configs/ \
  "${DESTINO}/configs/"

# 3. Log
echo "${DATA} backup concluído → ${DESTINO}"
```

---

## 6. Restauração a partir da cópia

Ver seção **C — Recuperação de desastre** em [`instalacao.md`](instalacao.md):

1. Parar o container: `docker compose down`
2. Restaurar `/var/lib/backup-lc` a partir da cópia
3. Restaurar segredos de `/etc/backup-lc/secrets` (de mídia offline)
4. Subir com a mesma tag: `docker compose up -d`
5. Verificar: `curl http://localhost:8080/health/ready`
