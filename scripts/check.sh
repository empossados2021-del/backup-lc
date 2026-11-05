#!/usr/bin/env bash
# Verificação local (ADR-010): formatação, lint, tipos e testes — sem acesso à rede.
# Uso: scripts/check.sh [argumentos extras do pytest]
set -euo pipefail
cd "$(dirname "$0")/.."

# Usa o cache de build; só baixa pacotes se pyproject/uv.lock mudarem (portão G-2).
docker build --quiet --target dev --tag backuplc:dev . > /dev/null

docker run --rm --network none \
  -v "$PWD":/work -w /work \
  -e PYTHONPATH=/work/src \
  -e PYTHONDONTWRITEBYTECODE=1 \
  backuplc:dev sh -ec '
    echo "== ruff format"; ruff format --check .
    echo "== ruff check";  ruff check .
    echo "== mypy";        mypy
    echo "== pytest";      pytest -p no:cacheprovider "$@"
  ' check "$@"
