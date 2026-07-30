"""Contract tests US3 (T045): aceite-legal e consentimento — via TestClient."""
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
    app.dependency_overrides.clear()


def _logar() -> None:
    app.dependency_overrides[usuario_atual] = lambda: IdentidadeFirebase(
        uid="u1", email="a@b.com", provedor="password"
    )
    app.dependency_overrides[exigir_cabecalhos] = lambda: ContextoRequisicao(
        versao_app="1.0.0", plataforma="android", idioma="pt"
    )


def _conta_existente() -> dict:
    return {
        "id_usuario": "id-u1",
        "co_usuario": "k7m3p9rt",
        "co_identidade_externa": "u1",
        "no_email": "a@b.com",
        # Retrato pós-migração 0010: sem data, com a declaração 13+.
        "dt_nascimento": None,
        "ic_idade_minima_declarada": True,
        "co_provedor_principal": "email",
        "co_idioma_preferido": "pt",
        "ic_convidado": False,
    }


def test_aceite_legal_registra_200(client):
    repo = FakeRepoUsuario(existente=_conta_existente())
    sessao = FakeSession()
    _logar()
    app.dependency_overrides[obter_servico_conta] = lambda: ServicoConta(repo, sessao)

    r = client.post(
        "/v1/conta/aceite-legal",
        json={"co_documento": "termos", "co_versao": "1.0", "co_idioma": "pt"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["co_documento"] == "termos"
    assert body["co_versao"] == "1.0"
    assert "dh_aceite" in body
    assert len(repo.aceites) == 1
    assert sessao.commits == 1


def test_aceite_legal_sem_conta_404(client):
    _logar()
    app.dependency_overrides[obter_servico_conta] = lambda: ServicoConta(
        FakeRepoUsuario(), FakeSession()
    )
    r = client.post(
        "/v1/conta/aceite-legal",
        json={"co_documento": "termos", "co_versao": "1.0", "co_idioma": "pt"},
    )
    assert r.status_code == 404
    assert r.json()["codigo"] == "conta_inexistente"


def test_consentimento_upsert_200(client):
    repo = FakeRepoUsuario(existente=_conta_existente())
    sessao = FakeSession()
    _logar()
    app.dependency_overrides[obter_servico_conta] = lambda: ServicoConta(repo, sessao)

    r = client.put(
        "/v1/conta/consentimento",
        json={"ic_rastreamento": True, "ic_marketing": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ic_rastreamento"] is True
    assert body["ic_marketing"] is False
    assert repo.consentimento is not None
    assert sessao.commits == 1


def test_consentimento_default_desligado(client):
    repo = FakeRepoUsuario(existente=_conta_existente())
    _logar()
    app.dependency_overrides[obter_servico_conta] = lambda: ServicoConta(
        repo, FakeSession()
    )
    # Corpo vazio → ambos os consentimentos vêm como False (opt-in explícito).
    r = client.put("/v1/conta/consentimento", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["ic_rastreamento"] is False
    assert body["ic_marketing"] is False


# ── co_versao_legal_aceita na resposta de perfil (item 6 do pós-publicação) ────
#
# O aceite passou a ser POR CONTA, não por aparelho. Antes, o portão do app
# comparava um pref LOCAL global com a versão vigente — e por isso uma conta NOVA
# num aparelho já usado ia direto para a Home, sem passar pelos termos.


def test_perfil_traz_a_versao_legal_aceita_pela_conta(client):
    repo = FakeRepoUsuario(existente=_conta_existente())
    sessao = FakeSession()
    _logar()
    app.dependency_overrides[obter_servico_conta] = lambda: ServicoConta(repo, sessao)

    # Aceita os DOIS documentos na 1.0 (é o que o app faz de uma vez).
    for doc in ("termos", "privacidade"):
        client.post(
            "/v1/conta/aceite-legal",
            json={"co_documento": doc, "co_versao": "1.0", "co_idioma": "pt"},
        )

    r = client.get("/v1/conta/perfil")
    assert r.status_code == 200
    assert r.json()["co_versao_legal_aceita"] == "1.0"


def test_versao_aceita_PELA_METADE_nao_conta(client):
    """Só `termos` aceito não libera o portão: a pessoa não viu a privacidade."""
    repo = FakeRepoUsuario(existente=_conta_existente())
    _logar()
    app.dependency_overrides[obter_servico_conta] = lambda: ServicoConta(
        repo, FakeSession()
    )

    client.post(
        "/v1/conta/aceite-legal",
        json={"co_documento": "termos", "co_versao": "1.0", "co_idioma": "pt"},
    )

    assert client.get("/v1/conta/perfil").json()["co_versao_legal_aceita"] is None


def test_conta_sem_aceite_nenhum_devolve_null(client):
    repo = FakeRepoUsuario(existente=_conta_existente())
    _logar()
    app.dependency_overrides[obter_servico_conta] = lambda: ServicoConta(
        repo, FakeSession()
    )
    assert client.get("/v1/conta/perfil").json()["co_versao_legal_aceita"] is None
