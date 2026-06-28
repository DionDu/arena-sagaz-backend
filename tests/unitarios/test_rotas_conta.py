"""Contract tests dos endpoints de conta (T031/T032/T036) — via TestClient.

Sem banco: trocamos (`dependency_overrides`) a verificação de token, os cabeçalhos
e o serviço por versões com repositório/sessão FALSOS. Assim validamos o contrato
HTTP (status + corpo) e a ligação com o serviço real.
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.conta.rotas import obter_servico_conta
from api.conta.servico import ServicoConta
from api.main import app
from api.nucleo.dependencias import (
    ContextoRequisicao,
    exigir_cabecalhos,
    usuario_atual,
)
from api.nucleo.seguranca_firebase import IdentidadeFirebase
from tests.unitarios.fakes_conta import FakeRepoUsuario, FakeSession


@pytest.fixture
def client():
    c = TestClient(app)
    yield c
    # Limpa as substituições para não vazar de um teste para outro.
    app.dependency_overrides.clear()


def _logar(identidade: IdentidadeFirebase | None = None) -> None:
    """Faz o token e os cabeçalhos passarem (usuário autenticado fake)."""
    app.dependency_overrides[usuario_atual] = lambda: identidade or IdentidadeFirebase(
        uid="u1", email="a@b.com", provedor="password"
    )
    app.dependency_overrides[exigir_cabecalhos] = lambda: ContextoRequisicao(
        versao_app="1.0.0", plataforma="android", idioma="pt"
    )


def _usar_servico(repo: FakeRepoUsuario, sessao: FakeSession) -> None:
    app.dependency_overrides[obter_servico_conta] = lambda: ServicoConta(repo, sessao)


def test_sessao_cria_conta_nova_200(client):
    repo, sessao = FakeRepoUsuario(), FakeSession()
    _logar()
    _usar_servico(repo, sessao)

    r = client.post(
        "/v1/conta/sessao",
        json={"dt_nascimento": "1990-01-01", "no_exibicao": "Fernando"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["co_provedor_principal"] == "email"
    assert body["provedores"] == ["email"]
    assert body["no_exibicao"] == "Fernando"
    assert len(body["co_usuario"]) == 8
    # A rota confirmou a transação.
    assert sessao.commits == 1


def test_sessao_nova_sem_data_responde_422(client):
    _logar()
    _usar_servico(FakeRepoUsuario(), FakeSession())
    r = client.post("/v1/conta/sessao", json={})
    assert r.status_code == 422
    assert r.json()["codigo"] == "data_nascimento_obrigatoria"


def test_sessao_menor_de_idade_responde_422(client):
    _logar()
    _usar_servico(FakeRepoUsuario(), FakeSession())
    ano = date.today().year - 10
    r = client.post("/v1/conta/sessao", json={"dt_nascimento": f"{ano}-01-01"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "idade_minima"


def test_perfil_inexistente_responde_404(client):
    _logar()
    _usar_servico(FakeRepoUsuario(), FakeSession())
    r = client.get("/v1/conta/perfil")
    assert r.status_code == 404
    assert r.json()["codigo"] == "conta_inexistente"


def test_sem_token_responde_401(client):
    # NÃO logamos: a rota exige Authorization e deve recusar.
    _usar_servico(FakeRepoUsuario(), FakeSession())
    r = client.get("/v1/conta/perfil")
    assert r.status_code == 401
    assert r.json()["codigo"] == "sem_token"


def test_cabecalhos_ausentes_responde_400(client):
    # Token OK, mas sem X-App-Version/X-Platform → 400.
    app.dependency_overrides[usuario_atual] = lambda: IdentidadeFirebase(
        uid="u1", provedor="password"
    )
    _usar_servico(FakeRepoUsuario(), FakeSession())
    r = client.get("/v1/conta/perfil")
    assert r.status_code == 400
    assert r.json()["codigo"] == "cabecalhos_ausentes"
