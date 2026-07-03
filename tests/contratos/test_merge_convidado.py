"""Contract test do POST /v1/sincronizacao/merge-convidado (US1, T024).

Valida o contrato do merge convidado→conta e sua idempotência por
`co_lote_migracao` (reenviar o mesmo lote é no-op), sem banco.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.nucleo.dependencias import ContextoRequisicao
from api.nucleo.dependencias_conta_nuvem import (
    UsuarioAutenticado,
    usuario_autenticado,
)
from api.sincronizacao.rotas import obter_servico_sync
from api.sincronizacao.servico import ServicoSincronizacao
from tests.contratos.fakes_sync import FakeRepoSincronizacao
from tests.unitarios.fakes_conta import FakeSession


@pytest.fixture
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _autenticar() -> None:
    app.dependency_overrides[usuario_autenticado] = lambda: UsuarioAutenticado(
        id_usuario="id-u1",
        co_usuario="ABC12345",
        co_anonimo="anon-1",
        dt_nascimento=None,
        contexto=ContextoRequisicao(
            versao_app="1.0.0", plataforma="android", idioma="pt"
        ),
    )


def _usar_repo(repo: FakeRepoSincronizacao, sessao: FakeSession) -> None:
    app.dependency_overrides[obter_servico_sync] = lambda: ServicoSincronizacao(
        repo, sessao
    )


def _corpo(lote: str) -> dict:
    return {
        "co_lote_migracao": lote,
        "progressao_convidado": {
            "nu_xp_total": 100,
            "nu_partidas": 5,
            "nu_vitorias": 3,
            "nu_derrotas": 1,
            "nu_empates": 1,
            "nu_sequencia_atual": 5,
            "conquistas": ["nivel_5", "primeira_vitoria"],
        },
    }


def test_merge_novo_soma_e_confirma(client):
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    r = client.post("/v1/sincronizacao/merge-convidado", json=_corpo("lote-A"))
    assert r.status_code == 200
    body = r.json()
    assert body["aplicado"] is True
    assert body["progressao"]["nu_xp_total"] == 100
    assert body["progressao"]["nu_sequencia_atual"] == 5
    assert body["progressao"]["conquistas"] == ["nivel_5", "primeira_vitoria"]
    assert sessao.commits == 1


def test_mesmo_lote_e_no_op(client):
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    client.post("/v1/sincronizacao/merge-convidado", json=_corpo("lote-A"))
    # Reenvia o MESMO lote (retry).
    r = client.post("/v1/sincronizacao/merge-convidado", json=_corpo("lote-A"))
    assert r.status_code == 200
    body = r.json()
    assert body["aplicado"] is False
    # XP NÃO dobrou.
    assert body["progressao"]["nu_xp_total"] == 100


def test_lote_diferente_soma_de_novo(client):
    repo, sessao = FakeRepoSincronizacao(), FakeSession()
    _autenticar()
    _usar_repo(repo, sessao)

    client.post("/v1/sincronizacao/merge-convidado", json=_corpo("lote-A"))
    r = client.post("/v1/sincronizacao/merge-convidado", json=_corpo("lote-B"))
    body = r.json()
    assert body["aplicado"] is True
    assert body["progressao"]["nu_xp_total"] == 200  # 100 + 100


def test_sem_lote_responde_400(client):
    _autenticar()
    _usar_repo(FakeRepoSincronizacao(), FakeSession())
    r = client.post(
        "/v1/sincronizacao/merge-convidado",
        json={"progressao_convidado": {}},
    )
    assert r.status_code == 400
    assert r.json()["codigo"] == "lote_ausente"
