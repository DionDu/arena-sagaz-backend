"""Testa o middleware que descomprime requisições ``Content-Encoding: gzip``.

O app (spec 006) envia o lote de sincronização comprimido; sem este middleware o
servidor receberia os bytes gzip crus e falharia ao ler o JSON — e o evento
ficaria "pendente" para sempre na outbox do app.
"""
import gzip
import json

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.nucleo.middleware_gzip import GzipRequestMiddleware


def _app_eco() -> FastAPI:
    """App mínimo com o middleware + uma rota que devolve o JSON recebido."""
    app = FastAPI()
    app.add_middleware(GzipRequestMiddleware)

    @app.post("/eco")
    async def eco(request: Request):
        # Se o corpo não tiver sido descomprimido, `request.json()` estoura.
        return await request.json()

    return app


def test_corpo_gzip_e_descomprimido():
    cliente = TestClient(_app_eco())
    dados = {"eventos": [{"co_evento": "abc", "payload": {"x": 1}}]}
    corpo = gzip.compress(json.dumps(dados).encode("utf-8"))
    r = cliente.post(
        "/eco",
        content=corpo,
        headers={
            "Content-Encoding": "gzip",
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 200
    assert r.json() == dados


def test_corpo_normal_passa_intacto():
    """Requisição SEM gzip não é afetada pelo middleware."""
    cliente = TestClient(_app_eco())
    dados = {"ola": "mundo"}
    r = cliente.post("/eco", json=dados)
    assert r.status_code == 200
    assert r.json() == dados
