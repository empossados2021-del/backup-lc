#!/usr/bin/env bash
# Prepara diretórios e segredos no host. Idempotente: nunca sobrescreve segredos.
# Uso (como root): scripts/init.sh
set -euo pipefail

SECRETS_DIR="${BLC_SECRETS_DIR:-/etc/backup-lc/secrets}"
DATA_DIR="${BLC_DATA_HOST:-/var/lib/backup-lc}"
APP_UID=10001

if [ "$(id -u)" -ne 0 ]; then
  echo "execute como root" >&2
  exit 1
fi

install -d -m 0700 -o "$APP_UID" -g "$APP_UID" "$DATA_DIR"
install -d -m 0700 -o root -g root "$SECRETS_DIR"

gen() {
  local file="$SECRETS_DIR/$1" code="$2"
  if [ -s "$file" ]; then
    echo "mantido: $file"
    return
  fi
  (umask 077 && python3 -c "$code" > "$file")
  chown "$APP_UID:$APP_UID" "$file"
  chmod 0400 "$file"
  echo "criado:  $file"
}

gen session_secret 'import secrets; print(secrets.token_urlsafe(48))'
gen master_key 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'

echo "dados:   $DATA_DIR"
echo "IMPORTANTE: guarde uma cópia de $SECRETS_DIR/master_key fora deste servidor (ADR-006)."
