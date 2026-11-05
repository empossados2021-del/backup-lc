# backup-lc (ADR-008). Builds que baixam pacotes passam pelo portão G-2.
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# ---- dependências (única etapa com acesso à rede) ----
FROM base AS builder
RUN pip install "uv>=0.9,<1"
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ---- ferramentas de verificação (scripts/check.sh) ----
FROM builder AS dev
RUN uv sync --frozen --no-install-project
ENV PATH=/app/.venv/bin:$PATH

# ---- imagem de execução ----
FROM base AS runtime
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent \
       --shell /usr/sbin/nologin app \
    && install -d -o 10001 -g 10001 -m 0700 /data
COPY --from=builder /app/.venv /app/.venv
COPY src/ /app/src/
# Código pertence ao root e é só leitura para o usuário da aplicação,
# independentemente das permissões do checkout no host.
RUN chown -R root:root /app/src && chmod -R u=rwX,go=rX /app/src
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app/src \
    BLC_DATA_DIR=/data
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["python", "-m", "backuplc"]
CMD ["serve"]
