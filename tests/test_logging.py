"""Logs JSON com máscara de segredos (N-05)."""

from __future__ import annotations

import io
import json
import logging

import pytest

from backuplc.core.logging import MASK, redact, register_secret

pytestmark = [pytest.mark.unit, pytest.mark.security]


def test_logs_sao_json_e_mascaram_segredos(log_stream: io.StringIO) -> None:
    registrado = "valor-registrado-CANARIO-123"
    register_secret(registrado)
    log = logging.getLogger("teste")

    log.info("conectando password=%s", "pw-canario-1")
    log.info("evento", extra={"password": "pw-canario-2", "ctx": {"token": "pw-canario-3"}})
    log.info("texto livre com %s no meio", registrado)
    log.info("ok", extra={"visivel": "pode-aparecer"})
    try:
        raise RuntimeError("falha secret=pw-canario-4")
    except RuntimeError:
        log.exception("erro")

    saida = log_stream.getvalue()
    for canario in ("pw-canario-1", "pw-canario-2", "pw-canario-3", "pw-canario-4", registrado):
        assert canario not in saida
    assert MASK in saida
    assert "pode-aparecer" in saida
    linhas = [json.loads(linha) for linha in saida.splitlines()]
    assert all({"ts", "level", "logger", "msg"} <= set(linha) for linha in linhas)


def test_redact_estruturas_aninhadas() -> None:
    dados = {"user": "ana", "Password": "x1", "lista": [{"api_key": "x2"}, "token=x3"]}
    assert redact(dados) == {
        "user": "ana",
        "Password": MASK,
        "lista": [{"api_key": MASK}, f"token={MASK}"],
    }
