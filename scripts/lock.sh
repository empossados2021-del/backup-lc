#!/usr/bin/env bash
# Gera/atualiza uv.lock. ACESSA A REDE (PyPI): exige aprovação do portão G-2.
set -euo pipefail
cd "$(dirname "$0")/.."
docker run --rm -v "$PWD":/work -w /work python:3.13-slim \
  sh -ec 'pip install --quiet --disable-pip-version-check --root-user-action=ignore "uv>=0.9,<1" && uv lock'
