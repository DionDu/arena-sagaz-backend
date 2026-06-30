"""Testes do endpoint de broadcast (`POST /v1/notificacoes/broadcast`).

Sem firebase: trocamos (`dependency_overrides`) o serviço por uma versão com um
**enviador fake** que só registra a chamada. Validamos o contrato HTTP (status +
corpo) e a proteção por `X-Admin-Token`.
"""
import pytest
from fastapi.testclient import TestClient

from api.configuracao import configuracoes
from api.main import app
from api.notificacoes.rotas import obter_servico_notificacoes
from api.notificacoes.servico import ServicoNotificacoes

SEGREDO = "segredo-de-teste"


@pytest.fixture
def client(monkeypatch):
    # Habilita o endpoint definindo o segredo administrativo.
    monkeypatch.setattr(configuracoes, "ADMIN_BROADCAST_TOKEN", SEGREDO)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _usar_enviador_fake(registro: list) -> None:
    """Injeta um serviço cujo enviador só registra (titulo, corpo, dados, topico)."""

    def enviador(titulo, corpo, dados, topico):
        registro.append((titulo, corpo, dados, topico))
        return "fake-msg-id"

    app.dependency_overrides[obter_servico_notificacoes] = (
        lambda: ServicoNotificacoes(enviador=enviador)
    )


def test_broadcast_com_token_valido_200(client):
    registro: list = []
    _usar_enviador_fake(registro)

    r = client.post(
        "/v1/notificacoes/broadcast",
        headers={"X-Admin-Token": SEGREDO},
        json={"titulo": "Novidade!", "corpo": "Chegou um jogo novo."},
    )

    assert r.status_code == 200
    body = r.json()
    assert body["id_mensagem"] == "fake-msg-id"
    assert body["topico"] == "todos"
    # O serviço chamou o enviador uma vez, com o tópico "todos".
    assert len(registro) == 1
    assert registro[0][0] == "Novidade!"
    assert registro[0][3] == "todos"


def test_broadcast_sem_token_401(client):
    _usar_enviador_fake([])
    r = client.post(
        "/v1/notificacoes/broadcast",
        json={"titulo": "x", "corpo": "y"},
    )
    assert r.status_code == 401
    assert r.json()["codigo"] == "admin_token_invalido"


def test_broadcast_token_errado_401(client):
    _usar_enviador_fake([])
    r = client.post(
        "/v1/notificacoes/broadcast",
        headers={"X-Admin-Token": "errado"},
        json={"titulo": "x", "corpo": "y"},
    )
    assert r.status_code == 401
    assert r.json()["codigo"] == "admin_token_invalido"


def test_broadcast_desabilitado_sem_segredo_401(monkeypatch):
    # Sem ADMIN_BROADCAST_TOKEN configurado, o endpoint fica desabilitado.
    monkeypatch.setattr(configuracoes, "ADMIN_BROADCAST_TOKEN", "")
    c = TestClient(app)
    r = c.post(
        "/v1/notificacoes/broadcast",
        headers={"X-Admin-Token": "qualquer"},
        json={"titulo": "x", "corpo": "y"},
    )
    assert r.status_code == 401
    assert r.json()["codigo"] == "broadcast_desabilitado"


def test_broadcast_corpo_invalido_422(client):
    _usar_enviador_fake([])
    # Título vazio viola o min_length → 422 de validação do Pydantic.
    r = client.post(
        "/v1/notificacoes/broadcast",
        headers={"X-Admin-Token": SEGREDO},
        json={"titulo": "", "corpo": "y"},
    )
    assert r.status_code == 422
