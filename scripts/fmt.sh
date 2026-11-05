#!/usr/bin/env bash
# Formata o código e aplica correções automáticas do Ruff — sem acesso à rede.
set -euo pipefail
cd "$(dirname "$0")/.."
docker build --quiet --target dev --tag backuplc:dev . > /dev/null
docker run --rm --network none -v "$PWD":/work -w /work backuplc:dev \
  sh -ec 'ruff format . && ruff check --fix .'
