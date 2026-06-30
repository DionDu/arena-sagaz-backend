"""Testes do endpoint de broadcast (`POST /v1/notificacoes/broadcast`).

Sem firebase: trocamos (`dependency_overrides`) o serviço por uma versão com um
**enviador fake** que só registra a chamada. Validamos o contrato HTTP (status +
corpo) e a proteção por `X-Admin-Token`.
"""
import pytest
from fastapi.testclient import TestClient

from api.configuracao import configuracoes
from api.main import app
from api.notificacoes.modelos import PreferenciaItem
from api.notificacoes.rotas import (
    obter_servico_notificacoes,
    obter_servico_preferencias,
    usuario_atual_opcional,
)
from api.notificacoes.servico import ServicoNotificacoes
from api.nucleo.dependencias import usuario_atual
from api.nucleo.seguranca_firebase import IdentidadeFirebase

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


# ── Dispositivo + preferências (tb005/tb006) ────────────────────────────────


class _FakeServicoPref:
    """Serviço fake (sem banco) que só registra as chamadas das rotas."""

    def __init__(self):
        self.dispositivos = []
        self.removidos = []
        self.prefs: list[PreferenciaItem] = []

    async def registrar_dispositivo(self, uid, co_token_fcm, sg_plataforma, co_idioma):
        self.dispositivos.append((uid, co_token_fcm, sg_plataforma, co_idioma))

    async def remover_dispositivo(self, co_token_fcm):
        self.removidos.append(co_token_fcm)

    async def definir_preferencias(self, uid, preferencias):
        self.prefs = list(preferencias)
        return self.prefs

    async def listar_preferencias(self, uid):
        return self.prefs


def _logar(uid="u1"):
    app.dependency_overrides[usuario_atual] = lambda: IdentidadeFirebase(
        uid=uid, email="a@b.com", provedor="password"
    )


def _usar_servico_pref(fake):
    app.dependency_overrides[obter_servico_preferencias] = lambda: fake


def test_registrar_dispositivo_autenticado_200(client):
    _logar()
    app.dependency_overrides[usuario_atual_opcional] = lambda: IdentidadeFirebase(
        uid="u1", email="a@b.com", provedor="password"
    )
    fake = _FakeServicoPref()
    _usar_servico_pref(fake)

    r = client.post(
        "/v1/notificacoes/dispositivo",
        json={"co_token_fcm": "tok-123", "sg_plataforma": "android", "co_idioma": "pt"},
    )
    assert r.status_code == 200
    assert fake.dispositivos == [("u1", "tok-123", "android", "pt")]


def test_registrar_dispositivo_convidado_sem_dono(client):
    # Convidado: o opcional devolve None → token sem dono.
    app.dependency_overrides[usuario_atual_opcional] = lambda: None
    fake = _FakeServicoPref()
    _usar_servico_pref(fake)

    r = client.post(
        "/v1/notificacoes/dispositivo",
        json={"co_token_fcm": "tok-x", "sg_plataforma": "ios", "co_idioma": "en"},
    )
    assert r.status_code == 200
    assert fake.dispositivos[0][0] is None  # uid nulo


def test_registrar_dispositivo_plataforma_invalida_422(client):
    app.dependency_overrides[usuario_atual_opcional] = lambda: None
    _usar_servico_pref(_FakeServicoPref())
    r = client.post(
        "/v1/notificacoes/dispositivo",
        json={"co_token_fcm": "t", "sg_plataforma": "windows", "co_idioma": "pt"},
    )
    assert r.status_code == 422


def test_remover_dispositivo_200(client):
    _logar()
    fake = _FakeServicoPref()
    _usar_servico_pref(fake)
    r = client.delete("/v1/notificacoes/dispositivo/tok-123")
    assert r.status_code == 200
    assert fake.removidos == ["tok-123"]


def test_definir_preferencias_200(client):
    _logar()
    fake = _FakeServicoPref()
    _usar_servico_pref(fake)
    r = client.put(
        "/v1/notificacoes/preferencias",
        json={
            "preferencias": [
                {"co_categoria": "novidades", "ic_ativo": False},
                {"co_categoria": "marketing", "ic_ativo": False},
            ]
        },
    )
    assert r.status_code == 200
    cats = {p["co_categoria"]: p["ic_ativo"] for p in r.json()["preferencias"]}
    assert cats == {"novidades": False, "marketing": False}


def test_definir_preferencias_categoria_invalida_422(client):
    _logar()
    _usar_servico_pref(_FakeServicoPref())
    r = client.put(
        "/v1/notificacoes/preferencias",
        json={"preferencias": [{"co_categoria": "spam", "ic_ativo": True}]},
    )
    assert r.status_code == 422


def test_obter_preferencias_200(client):
    _logar()
    fake = _FakeServicoPref()
    fake.prefs = [PreferenciaItem(co_categoria="transacional", ic_ativo=True)]
    _usar_servico_pref(fake)
    r = client.get("/v1/notificacoes/preferencias")
    assert r.status_code == 200
    assert r.json()["preferencias"][0]["co_categoria"] == "transacional"
