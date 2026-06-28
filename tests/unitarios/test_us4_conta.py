"""Testes da US4 — editar perfil e excluir (anonimizar) a conta.

Cobre o serviço (com fakes, via asyncio.run) e as rotas (TestClient +
dependency_overrides), sem banco nem Firebase reais.
"""
import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.conta.modelos import AtualizarPerfilRequest
from api.conta.rotas import obter_servico_conta
from api.conta.servico import ServicoConta
from api.main import app
from api.nucleo.dependencias import (
    ContextoRequisicao,
    exigir_cabecalhos,
    usuario_atual,
)
from api.nucleo.excecoes import ErroNegocio, ErroNaoEncontrado
from api.nucleo.seguranca_firebase import AdminUsuariosFake, IdentidadeFirebase
from tests.unitarios.fakes_conta import FakeRepoUsuario, FakeSession


def _identidade(uid="u1"):
    return IdentidadeFirebase(uid=uid, email="a@b.com", provedor="password")


def _conta_existente(uid="u1") -> dict:
    return {
        "id_usuario": f"id-{uid}",
        "co_usuario": "k7m3p9rt",
        "co_identidade_externa": uid,
        "no_exibicao": "Antigo",
        "no_email": "a@b.com",
        "dt_nascimento": date(1990, 1, 1),
        "co_provedor_principal": "email",
        "co_idioma_preferido": "pt",
        "ic_convidado": False,
    }


# ── serviço: excluir_conta ───────────────────────────────────────────────────


def test_excluir_conta_anonimiza_e_apaga_no_firebase():
    repo = FakeRepoUsuario(existente=_conta_existente())
    admin = AdminUsuariosFake()
    servico = ServicoConta(repo=repo, sessao=FakeSession(), admin=admin)

    resp = asyncio.run(servico.excluir_conta(_identidade()))

    assert resp.ic_anonimizado is True
    # A linha foi anonimizada (PII zerada) e o uid foi apagado no Firebase.
    linha = repo._por_uid.get("u1")
    # Após anonimizar, a busca por uid não acha mais (co_identidade_externa nulo).
    assert linha is None or linha.get("no_email") is None
    assert admin.excluidos == ["u1"]
    assert getattr(repo, "dados_removidos", None) == "id-u1"


def test_excluir_conta_sem_conta_404():
    servico = ServicoConta(
        repo=FakeRepoUsuario(), sessao=FakeSession(), admin=AdminUsuariosFake()
    )
    with pytest.raises(ErroNaoEncontrado):
        asyncio.run(servico.excluir_conta(_identidade()))


def test_excluir_conta_firebase_falha_nao_derruba():
    # Best-effort: se o Firebase falhar, a anonimização local ainda vale.
    repo = FakeRepoUsuario(existente=_conta_existente())
    admin = AdminUsuariosFake()
    admin.falhar = True
    servico = ServicoConta(repo=repo, sessao=FakeSession(), admin=admin)

    resp = asyncio.run(servico.excluir_conta(_identidade()))
    assert resp.ic_anonimizado is True


# ── serviço: atualizar_perfil_usuario ────────────────────────────────────────


def test_atualizar_perfil_muda_nome_moderado_e_idioma():
    repo = FakeRepoUsuario(existente=_conta_existente())
    servico = ServicoConta(repo=repo, sessao=FakeSession())

    perfil = asyncio.run(
        servico.atualizar_perfil_usuario(
            _identidade(),
            AtualizarPerfilRequest(no_exibicao="  Novo  Nome ", co_idioma_preferido="en"),
        )
    )
    # Nome normalizado (espaços colapsados) e idioma trocado.
    assert perfil.no_exibicao == "Novo Nome"
    assert perfil.co_idioma_preferido == "en"


def test_atualizar_perfil_nome_invalido_422():
    repo = FakeRepoUsuario(existente=_conta_existente())
    servico = ServicoConta(repo=repo, sessao=FakeSession())
    with pytest.raises(ErroNegocio) as exc:
        asyncio.run(
            servico.atualizar_perfil_usuario(
                _identidade(), AtualizarPerfilRequest(no_exibicao="a")
            )
        )
    assert exc.value.status_http == 422


# ── rotas (TestClient) ───────────────────────────────────────────────────────


@pytest.fixture
def client():
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _logar() -> None:
    app.dependency_overrides[usuario_atual] = lambda: _identidade()
    app.dependency_overrides[exigir_cabecalhos] = lambda: ContextoRequisicao(
        versao_app="1.0.0", plataforma="android", idioma="pt"
    )


def test_rota_delete_conta_200(client):
    repo = FakeRepoUsuario(existente=_conta_existente())
    sessao = FakeSession()
    admin = AdminUsuariosFake()
    _logar()
    app.dependency_overrides[obter_servico_conta] = lambda: ServicoConta(
        repo=repo, sessao=sessao, admin=admin
    )

    r = client.delete("/v1/conta")
    assert r.status_code == 200
    assert r.json()["ic_anonimizado"] is True
    assert admin.excluidos == ["u1"]
    assert sessao.commits == 1


def test_rota_patch_perfil_200(client):
    repo = FakeRepoUsuario(existente=_conta_existente())
    sessao = FakeSession()
    _logar()
    app.dependency_overrides[obter_servico_conta] = lambda: ServicoConta(
        repo=repo, sessao=sessao
    )

    r = client.patch("/v1/conta/perfil", json={"no_exibicao": "Magno"})
    assert r.status_code == 200
    assert r.json()["no_exibicao"] == "Magno"
    assert sessao.commits == 1


def test_rota_patch_perfil_nome_invalido_422(client):
    repo = FakeRepoUsuario(existente=_conta_existente())
    _logar()
    app.dependency_overrides[obter_servico_conta] = lambda: ServicoConta(
        repo=repo, sessao=FakeSession()
    )
    r = client.patch("/v1/conta/perfil", json={"no_exibicao": "Admin"})
    assert r.status_code == 422
    assert r.json()["codigo"] == "nome_nao_permitido"
