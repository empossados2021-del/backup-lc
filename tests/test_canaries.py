"""E1-04: canários não aparecem em logs, banco ou arquivos gerados."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backuplc.core.config import Settings
from backuplc.core.db import Database
from backuplc.core.events import Event, record_event
from conftest import CANARIES, CANARY_SESSION

pytestmark = [pytest.mark.integration, pytest.mark.security]


def test_canarios_nao_vazam(
    log_stream: io.StringIO,
    client: TestClient,
    admin_client: TestClient,
    db: Database,
    settings: Settings,
) -> None:
    # Fluxos de sucesso e de erro.
    assert admin_client.get("/").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert admin_client.get("/nao-existe").status_code == 404
    assert admin_client.get(f"/busca?token={CANARY_SESSION}").status_code == 404

    # Evento com segredo no detalhe: deve ser mascarado antes de gravar.
    with db.session() as session:
        record_event(
            session,
            "teste",
            actor="ana",
            detail={"password": CANARY_SESSION, "nota": f"secret={CANARY_SESSION}"},
        )
    with db.session() as session:
        gravado = session.query(Event).filter_by(action="teste").one()
        assert CANARY_SESSION not in str(gravado.detail)

    db.dispose()  # descarrega o WAL no arquivo do banco

    assert log_stream.getvalue(), "nenhum log capturado"
    for canario in CANARIES:
        assert canario not in log_stream.getvalue()

    arquivos = [p for p in Path(settings.data_dir).rglob("*") if p.is_file()]
    assert arquivos, "nenhum arquivo gerado para inspecionar"
    for arquivo in arquivos:
        conteudo = arquivo.read_bytes()
        for canario in CANARIES:
            assert canario.encode() not in conteudo, f"canário encontrado em {arquivo.name}"
